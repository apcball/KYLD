# -*- coding: utf-8 -*-
import logging

from odoo import models
from odoo.exceptions import AccessDenied
from odoo.http import request, SessionExpiredException

_logger = logging.getLogger(__name__)

API_PATH_PREFIX = '/api/buz-dashboard/'
# Rule registered by controllers/dashboard_api.py for CORS preflight.
API_PREFLIGHT_RULE = API_PATH_PREFIX + '<path:subpath>'

# Core Odoo JSON-RPC endpoints used by the web dashboard login/session
# flow. Browsers need CORS headers here too or the cross-origin login
# never succeeds.
_WEB_SESSION_PREFIX = '/web/session/'
_WEB_DATASET_PREFIX = '/web/dataset/'
CORS_PATH_PREFIXES = (
    API_PATH_PREFIX,
    _WEB_SESSION_PREFIX,
    _WEB_DATASET_PREFIX,
)
# OPTIONS preflight rules registered in controllers/dashboard_api.py,
# keyed by their path prefix.
PREFLIGHT_RULES = {
    API_PATH_PREFIX: API_PREFLIGHT_RULE,
    _WEB_SESSION_PREFIX: _WEB_SESSION_PREFIX + '<path:subpath>',
    _WEB_DATASET_PREFIX: _WEB_DATASET_PREFIX + '<path:subpath>',
}


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _auth_method_buz_dashboard(cls):
        """Session auth first; falls back to an Odoo API key via the
        X-Odoo-Api-Key header so server-side/Next.js callers with no
        browser session can still authenticate."""
        try:
            cls._auth_method_user()
            return
        except (AccessDenied, SessionExpiredException):
            pass

        key = request.httprequest.headers.get('X-Odoo-Api-Key')
        if not key:
            raise AccessDenied()

        # sudo: res.users.apikeys is a credentials store not readable by a
        # normal user by design. Only the resolved uid escapes this call.
        uid = request.env['res.users.apikeys'].sudo()._check_credentials(
            scope='rpc', key=key)
        if not uid:
            raise AccessDenied()
        request.update_env(user=uid)

    @classmethod
    def _match(cls, path_info):
        """Odoo 17 auto-adds OPTIONS to every route's methods, so the
        type='json' endpoints always shadow the dedicated OPTIONS preflight
        route (and then BadRequest because an OPTIONS request infers as
        type='http'). For this API prefix, locate the preflight rule
        directly instead of relying on route ordering."""
        if request.httprequest.method == 'OPTIONS':
            try:
                # website's IrHttp._match normally initializes this before
                # anything touches routing_map(); replicate that here.
                if not hasattr(request, 'website_routing') \
                        and 'website' in request.env:
                    request.website_routing = (
                        request.env['website'].get_current_website().id)
                router = request.env['ir.http'].routing_map()
                for prefix, rule_pattern in PREFLIGHT_RULES.items():
                    if not (path_info or '').startswith(prefix):
                        continue
                    for rule in router.iter_rules():
                        if rule.rule == rule_pattern:
                            # http_routing's _match normally sets these from
                            # the matched rule's endpoint routing; replicate.
                            routing = rule.endpoint.routing
                            request.is_frontend = routing.get(
                                'website', False)
                            request.is_frontend_multilang = (
                                request.is_frontend
                                and routing.get(
                                    'multilang',
                                    routing['type'] == 'http'))
                            return rule, {'subpath': path_info[len(prefix):]}
            except Exception:
                _logger.exception(
                    "buz_dashboard: OPTIONS preflight match failed for %s",
                    path_info)
        return super()._match(path_info)

    @classmethod
    def _post_dispatch(cls, response):
        """Inject CORS headers here rather than in _dispatch: for
        type='json' routes, _dispatch returns the raw endpoint value
        (a dict), while _post_dispatch always receives the final
        HTTP Response object."""
        super()._post_dispatch(response)
        cls._buz_dashboard_add_cors_headers(response)

    @classmethod
    def _buz_dashboard_add_cors_headers(cls, response):
        path = request.httprequest.path or ''
        if not any(path.startswith(p) for p in CORS_PATH_PREFIXES):
            return
        origin = request.httprequest.headers.get('Origin')
        if not origin:
            return

        allowed = request.env['ir.config_parameter'].sudo().get_param(
            'buz_dashboard.cors_origins', '')
        allowed_origins = {o.strip() for o in allowed.split(',') if o.strip()}
        if origin not in allowed_origins:
            return

        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Headers'] = (
            'Content-Type, X-Odoo-Api-Key')
