# -*- coding: utf-8 -*-
"""Thin JSON routing only. All business logic lives in services/."""
import logging

from odoo import http
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request

from ..services.base_service import SERVICE_REGISTRY
from ..services.filters import DashboardFilter
from ..services.response import DashboardApiError, ErrorCode, err, ok

_logger = logging.getLogger(__name__)

BASE = '/api/buz-dashboard/job-costing'


class DashboardApiController(http.Controller):

    def _dispatch(self, service_code, payload, **extra_kwargs):
        env = request.env
        try:
            filters = DashboardFilter.from_payload(env, payload)
            service_cls = SERVICE_REGISTRY[service_code]
            service = service_cls(env, filters)
            data = service.run(**extra_kwargs)
            return ok(
                data,
                company_id=env.company.id,
                currency=service.currency.base_currency.name,
                warnings=service.currency.warnings,
            )
        except DashboardApiError as exc:
            return err(exc.code, exc.message)
        except MissingError:
            return err(ErrorCode.NOT_FOUND, "Record not found")
        except AccessError:
            return err(ErrorCode.FORBIDDEN, "You do not have access to this data")
        except ValidationError as exc:
            return err(ErrorCode.INVALID_REQUEST, str(exc))
        except ValueError as exc:
            return err(ErrorCode.INVALID_REQUEST, str(exc))
        except Exception:
            _logger.exception(
                "buz_dashboard: unhandled error in endpoint %s", service_code)
            return err(ErrorCode.INTERNAL_ERROR, "An internal error occurred")

    @http.route(BASE + '/overview', type='json', auth='buz_dashboard',
                methods=['POST'], csrf=False)
    def overview(self, **payload):
        return self._dispatch('job_costing.overview', payload)

    @http.route(BASE + '/projects', type='json', auth='buz_dashboard',
                methods=['POST'], csrf=False)
    def projects(self, **payload):
        return self._dispatch('job_costing.projects', payload)

    @http.route(BASE + '/project-detail', type='json', auth='buz_dashboard',
                methods=['POST'], csrf=False)
    def project_detail(self, **payload):
        return self._dispatch(
            'job_costing.project_detail', payload,
            project_id=payload.get('project_id'))

    @http.route(BASE + '/cost-breakdown', type='json', auth='buz_dashboard',
                methods=['POST'], csrf=False)
    def cost_breakdown(self, **payload):
        return self._dispatch('job_costing.cost_breakdown', payload)

    @http.route(BASE + '/materials', type='json', auth='buz_dashboard',
                methods=['POST'], csrf=False)
    def materials(self, **payload):
        return self._dispatch('job_costing.materials', payload)

    @http.route(BASE + '/labour', type='json', auth='buz_dashboard',
                methods=['POST'], csrf=False)
    def labour(self, **payload):
        return self._dispatch('job_costing.labour', payload)

    @http.route(BASE + '/overheads', type='json', auth='buz_dashboard',
                methods=['POST'], csrf=False)
    def overheads(self, **payload):
        return self._dispatch('job_costing.overheads', payload)

    @http.route(BASE + '/profitability', type='json', auth='buz_dashboard',
                methods=['POST'], csrf=False)
    def profitability(self, **payload):
        return self._dispatch('job_costing.profitability', payload)

    @http.route(BASE + '/variance', type='json', auth='buz_dashboard',
                methods=['POST'], csrf=False)
    def variance(self, **payload):
        return self._dispatch('job_costing.variance', payload)

    @http.route(BASE + '/trends', type='json', auth='buz_dashboard',
                methods=['POST'], csrf=False)
    def trends(self, **payload):
        return self._dispatch(
            'job_costing.trends', payload,
            group_by=payload.get('group_by', 'month'))

    @http.route('/api/buz-dashboard/<path:subpath>', type='http',
                auth='none', methods=['OPTIONS'], csrf=False)
    def preflight(self, subpath, **kwargs):
        return request.make_response('', headers=[])
