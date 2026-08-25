# -*- coding: utf-8 -*-
"""Cache abstraction. Default backend is DB-backed (buz.dashboard.cache),
not an in-process dict: Odoo runs multi-worker, so a per-process cache
would give different workers different answers. Swapping to Redis later
means adding one new backend class here; no service-layer code changes.
"""
import json
from abc import ABC, abstractmethod
from datetime import timedelta

from odoo import fields


class DashboardCacheService(ABC):

    @abstractmethod
    def get(self, key):
        ...

    @abstractmethod
    def set(self, key, value, ttl=60):
        ...

    @abstractmethod
    def invalidate(self, key):
        ...

    @abstractmethod
    def invalidate_prefix(self, prefix):
        ...


class NoopCacheService(DashboardCacheService):

    def get(self, key):
        return None

    def set(self, key, value, ttl=60):
        return None

    def invalidate(self, key):
        return None

    def invalidate_prefix(self, prefix):
        return None


class DbCacheService(DashboardCacheService):

    def __init__(self, env):
        self.env = env

    def get(self, key):
        # sudo: the cache row belongs to no specific user; the key itself is
        # already uid/company-scoped by the caller (see key format below),
        # so reading another row's payload can never happen.
        record = self.env['buz.dashboard.cache'].sudo().search(
            [('key', '=', key), ('expires_at', '>', fields.Datetime.now())],
            limit=1)
        if not record:
            return None
        try:
            return json.loads(record.payload)
        except ValueError:
            return None

    def set(self, key, value, ttl=60):
        if ttl <= 0:
            return
        expires_at = fields.Datetime.now() + timedelta(seconds=ttl)
        Cache = self.env['buz.dashboard.cache'].sudo()
        existing = Cache.search([('key', '=', key)], limit=1)
        vals = {
            'key': key,
            'payload': json.dumps(value, default=str),
            'expires_at': expires_at,
            'company_id': self.env.company.id,
        }
        if existing:
            existing.write(vals)
        else:
            Cache.create(vals)

    def invalidate(self, key):
        self.env['buz.dashboard.cache'].sudo().search([('key', '=', key)]).unlink()

    def invalidate_prefix(self, prefix):
        self.env['buz.dashboard.cache'].sudo().search(
            [('key', 'like', '%s%%' % prefix)]).unlink()


def get_cache_backend(env):
    backend = env['ir.config_parameter'].sudo().get_param(
        'buz_dashboard.cache_backend', 'db')
    if backend == 'none':
        return NoopCacheService()
    # 'db' is the default and current fallback for any unrecognised value
    # (including a future 'redis' not yet implemented).
    return DbCacheService(env)


def get_cache_ttl(env):
    try:
        return int(env['ir.config_parameter'].sudo().get_param(
            'buz_dashboard.cache_ttl', 60))
    except (TypeError, ValueError):
        return 60


def cache_key(endpoint, env, filters):
    return 'buz_dashboard:%s:db=%s:uid=%s:companies=%s:cur=%s:%s' % (
        endpoint,
        env.cr.dbname,
        env.uid,
        '-'.join(str(c) for c in sorted(filters.company_ids)),
        filters.currency_id or 0,
        filters.cache_signature(),
    )
