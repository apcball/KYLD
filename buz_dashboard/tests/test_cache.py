# -*- coding: utf-8 -*-
from odoo.tests import tagged

from ..services.cache import DbCacheService, NoopCacheService, cache_key
from ..services.filters import DashboardFilter
from .common import DashboardTestCase


@tagged('post_install', '-at_install')
class TestDashboardCache(DashboardTestCase):

    def test_db_cache_roundtrip(self):
        cache = DbCacheService(self.env)
        key = 'buz_dashboard:test:unit'
        self.assertIsNone(cache.get(key))
        cache.set(key, {'value': 42}, ttl=60)
        self.assertEqual(cache.get(key), {'value': 42})
        cache.invalidate(key)
        self.assertIsNone(cache.get(key))

    def test_db_cache_expiry(self):
        cache = DbCacheService(self.env)
        key = 'buz_dashboard:test:expiry'
        cache.set(key, {'value': 1}, ttl=0)
        # ttl=0 means "don't cache" in DbCacheService.set
        self.assertIsNone(cache.get(key))

    def test_noop_cache_never_stores(self):
        cache = NoopCacheService()
        cache.set('k', {'value': 1}, ttl=60)
        self.assertIsNone(cache.get('k'))

    def test_cache_key_scoped_by_uid_and_company(self):
        filters = DashboardFilter.from_payload(self.env, {})
        key = cache_key('job_costing.overview', self.env, filters)
        self.assertIn('uid=%s' % self.env.uid, key)
        self.assertIn('companies=', key)

    def test_cache_invalidate_prefix(self):
        cache = DbCacheService(self.env)
        cache.set('buz_dashboard:overview:a', {'v': 1}, ttl=60)
        cache.set('buz_dashboard:overview:b', {'v': 2}, ttl=60)
        cache.set('buz_dashboard:projects:a', {'v': 3}, ttl=60)
        cache.invalidate_prefix('buz_dashboard:overview:')
        self.assertIsNone(cache.get('buz_dashboard:overview:a'))
        self.assertIsNone(cache.get('buz_dashboard:overview:b'))
        self.assertEqual(cache.get('buz_dashboard:projects:a'), {'v': 3})
