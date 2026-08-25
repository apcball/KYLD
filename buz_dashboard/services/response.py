# -*- coding: utf-8 -*-
"""Standard JSON response envelope for all buz_dashboard API endpoints.

Success: {'success': True, 'data': ..., 'meta': {...}}
Error:   {'success': False, 'error': {'code': ..., 'message': ...}}

No traceback or internal detail is ever placed in an error response.
"""
from odoo import fields


class ErrorCode:
    INVALID_REQUEST = 'INVALID_REQUEST'
    FORBIDDEN = 'FORBIDDEN'
    PROJECT_NOT_FOUND = 'PROJECT_NOT_FOUND'
    NOT_FOUND = 'NOT_FOUND'
    INTERNAL_ERROR = 'INTERNAL_ERROR'


class DashboardApiError(Exception):
    """Raised by services to produce a specific error envelope."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def ok(data, company_id=None, currency=None, warnings=None):
    meta = {
        'generated_at': fields.Datetime.to_string(fields.Datetime.now()),
    }
    if company_id is not None:
        meta['company_id'] = company_id
    if currency is not None:
        meta['currency'] = currency
    if warnings:
        meta['warnings'] = warnings
    return {
        'success': True,
        'data': data,
        'meta': meta,
    }


def err(code, message):
    return {
        'success': False,
        'error': {
            'code': code,
            'message': message,
        },
    }


def kpi(value, currency=None, formatted_value=None, trend=None):
    """Canonical KPI shape: `value` is always the raw number; the rest is
    convenience for the frontend, never authoritative."""
    result = {
        'value': value,
        'currency': currency,
    }
    if formatted_value is not None:
        result['formatted_value'] = formatted_value
    if trend is not None:
        result['trend'] = trend
    return result
