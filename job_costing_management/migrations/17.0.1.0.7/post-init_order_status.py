# -*- coding: utf-8 -*-
"""Populate material.requisition.order_status and re-sync MR state.

order_status is a new stored computed field; Odoo computes it for existing
rows on module update, but PO lines are a cross-model dependency, so recompute
explicitly, then align state (Ordered / Done) with RFQ coverage.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    requisitions = env['material.requisition'].search(
        [('state', 'in', ('approved', 'ordered'))])
    before = {r.id: r.state for r in requisitions}
    requisitions._sync_order_state()
    changed = [r for r in requisitions if before[r.id] != r.state]
    _logger.info('material.requisition order_status migration: %d checked, %d state changed: %s',
                 len(requisitions), len(changed), [(r.name, before[r.id], r.state) for r in changed])
