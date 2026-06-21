# -*- coding: utf-8 -*-
"""Post-migration: re-sync budget.transactions from budget.moves.

This version adds document triggers (MR/PR/PO/bill) and views. The
existing transactions from 1.0.2 are still valid — this migration
re-syncs them against the current budget.move state to catch any
drift since the initial migration.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.buz_budget_core.hooks import run_migration

_logger = logging.getLogger(__name__)


def migrate(cr, installed_version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Re-run migration only if no transactions exist (fresh install path).
    # For existing installs, transactions are already populated — the
    # new document triggers will keep them in sync going forward.
    Transaction = env['budget.transaction']
    existing = Transaction.search_count([])
    if existing > 0:
        _logger.info(
            'budget.transaction already has %d records — skipping migration, '
            'document triggers will sync going forward.',
            existing,
        )
        return
    run_migration(env)
