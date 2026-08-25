# -*- coding: utf-8 -*-
import hashlib
import json
from dataclasses import dataclass, field
from typing import List, Optional

from odoo import fields as odoo_fields

from .response import DashboardApiError, ErrorCode

MAX_LIMIT = 500
DEFAULT_LIMIT = 50

JOB_COST_SHEET_STATES = {'draft', 'approved', 'done', 'cancelled'}


@dataclass
class DashboardFilter:
    env: object
    date_from: Optional[object] = None
    date_to: Optional[object] = None
    company_ids: List[int] = field(default_factory=list)
    project_ids: List[int] = field(default_factory=list)
    manager_ids: List[int] = field(default_factory=list)
    states: List[str] = field(default_factory=list)
    limit: int = DEFAULT_LIMIT
    offset: int = 0
    currency_id: Optional[int] = None
    group_by: Optional[str] = None

    @classmethod
    def from_payload(cls, env, payload):
        payload = payload or {}

        date_from = _parse_date(payload.get('date_from'))
        date_to = _parse_date(payload.get('date_to'))
        if date_from and date_to and date_from > date_to:
            raise DashboardApiError(
                ErrorCode.INVALID_REQUEST, "date_from must not be after date_to")

        company_ids = _to_int_list(payload.get('company_id'), payload.get('company_ids'))
        accessible_company_ids = set(env.companies.ids)
        for cid in company_ids:
            if cid not in accessible_company_ids:
                raise DashboardApiError(
                    ErrorCode.FORBIDDEN,
                    "You do not have access to company %s" % cid)
        if not company_ids:
            company_ids = [env.company.id]

        project_ids = _to_int_list(payload.get('project_id'), payload.get('project_ids'))
        manager_ids = _to_int_list(payload.get('manager_id'), payload.get('manager_ids'))

        states = payload.get('state') or payload.get('states') or []
        if isinstance(states, str):
            states = [states]
        for state in states:
            if state not in JOB_COST_SHEET_STATES:
                raise DashboardApiError(
                    ErrorCode.INVALID_REQUEST,
                    "Unknown state '%s'. Allowed: %s" % (
                        state, ', '.join(sorted(JOB_COST_SHEET_STATES))))

        limit = payload.get('limit', DEFAULT_LIMIT)
        try:
            limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise DashboardApiError(ErrorCode.INVALID_REQUEST, "limit must be an integer") from exc
        limit = max(1, min(limit, MAX_LIMIT))

        offset = payload.get('offset', 0)
        try:
            offset = int(offset)
        except (TypeError, ValueError) as exc:
            raise DashboardApiError(ErrorCode.INVALID_REQUEST, "offset must be an integer") from exc
        offset = max(0, offset)

        currency_id = payload.get('currency_id')
        if currency_id is not None:
            try:
                currency_id = int(currency_id)
            except (TypeError, ValueError) as exc:
                raise DashboardApiError(ErrorCode.INVALID_REQUEST, "currency_id must be an integer") from exc
            if not env['res.currency'].browse(currency_id).exists():
                raise DashboardApiError(ErrorCode.INVALID_REQUEST, "Unknown currency_id")

        return cls(
            env=env,
            date_from=date_from,
            date_to=date_to,
            company_ids=company_ids,
            project_ids=project_ids,
            manager_ids=manager_ids,
            states=states,
            limit=limit,
            offset=offset,
            currency_id=currency_id,
            group_by=payload.get('group_by'),
        )

    def cost_sheet_domain(self, date_field='date_start'):
        domain = [('company_id', 'in', self.company_ids)]
        if self.date_from:
            domain.append((date_field, '>=', self.date_from))
        if self.date_to:
            domain.append((date_field, '<=', self.date_to))
        if self.project_ids:
            domain.append(('project_id', 'in', self.project_ids))
        if self.states:
            domain.append(('state', 'in', self.states))
        return domain

    def project_domain(self):
        domain = [('company_id', 'in', self.company_ids)]
        if self.project_ids:
            domain.append(('id', 'in', self.project_ids))
        if self.manager_ids:
            domain.append(('project_manager_id', 'in', self.manager_ids))
        return domain

    def cache_signature(self):
        payload = {
            'date_from': str(self.date_from) if self.date_from else None,
            'date_to': str(self.date_to) if self.date_to else None,
            'company_ids': sorted(self.company_ids),
            'project_ids': sorted(self.project_ids),
            'manager_ids': sorted(self.manager_ids),
            'states': sorted(self.states),
            'limit': self.limit,
            'offset': self.offset,
            'currency_id': self.currency_id,
            'group_by': self.group_by,
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]


def _parse_date(value):
    if not value:
        return None
    try:
        return odoo_fields.Date.to_date(value)
    except ValueError as exc:
        raise DashboardApiError(ErrorCode.INVALID_REQUEST, "Invalid date: %r" % value) from exc


def _to_int_list(*values):
    result = []
    for value in values:
        if not value:
            continue
        if isinstance(value, (list, tuple)):
            result.extend(int(v) for v in value)
        else:
            result.append(int(value))
    return result
