# -*- coding: utf-8 -*-
import logging

from odoo import models
from odoo.exceptions import AccessDenied
from odoo.http import request, SessionExpiredException

_logger = logging.getLogger(__name__)

API_PATH_PREFIX = '/api/buz-dashboard/'


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
    def _dispatch(cls, endpoint):
        response = super()._dispatch(endpoint)
        cls._buz_dashboard_add_cors_headers(response)
        return response

    @classmethod
    def _buz_dashboard_add_cors_headers(cls, response):
        path = request.httprequest.path or ''
        if not path.startswith(API_PATH_PREFIX):
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
