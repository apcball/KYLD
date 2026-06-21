# -*- coding: utf-8 -*-
"""Extend monthly.budget.allocation with transaction-based totals.

The allocation now derives its summary fields directly from
budget.transaction stage amounts via GROUP BY aggregation.  This
replaces the old budget.move-based computes that required delete-
rebuild cycles.

These new fields coexist with the legacy amount_used / amount_reserved
during the transition period.  Once budget.move is fully retired,
the legacy fields can be removed.
"""
from odoo import api, fields, models


class MonthlyBudgetAllocation(models.Model):
    _inherit = 'monthly.budget.allocation'

    # ──────────────────────────────────────────────────────────────
    # Transaction-based stage totals (read from budget.transaction)
    # ──────────────────────────────────────────────────────────────
    tx_reserved = fields.Float(
        string='Reserved (Tx)',
        compute='_compute_tx_totals', store=True,
        help='Sum of reserved_amount from linked transactions.',
    )
    tx_committed = fields.Float(
        string='Committed (Tx)',
        compute='_compute_tx_totals', store=True,
        help='Sum of committed_amount from linked transactions.',
    )
    tx_used = fields.Float(
        string='Used (Tx)',
        compute='_compute_tx_totals', store=True,
        help='Sum of used_amount from linked transactions.',
    )
    tx_forecast = fields.Float(
        string='Forecast (Tx)',
        compute='_compute_tx_totals', store=True,
        help='Reserved + Committed (total not-yet-billed demand).',
    )
    tx_remaining = fields.Float(
        string='Available (Tx)',
        compute='_compute_tx_totals', store=True,
        help='Allocation amount minus all active stage amounts.',
    )
    tx_usage_pct = fields.Float(
        string='Usage % (Tx)',
        compute='_compute_tx_totals', store=True,
    )
    transaction_count = fields.Integer(
        string='Tx Count',
        compute='_compute_tx_totals', store=True,
    )

    @api.depends(
        'transaction_ids.reserved_amount',
        'transaction_ids.committed_amount',
        'transaction_ids.used_amount',
        'transaction_ids.released_amount',
        'transaction_ids.state',
        'amount',
    )
    def _compute_tx_totals(self):
        for alloc in self:
            txs = alloc.transaction_ids
            alloc.tx_reserved = sum(txs.mapped('reserved_amount'))
            alloc.tx_committed = sum(txs.mapped('committed_amount'))
            alloc.tx_used = sum(txs.mapped('used_amount'))
            alloc.tx_forecast = alloc.tx_reserved + alloc.tx_committed
            total_active = alloc.tx_reserved + alloc.tx_committed + alloc.tx_used
            alloc.tx_remaining = alloc.amount - total_active
            alloc.tx_usage_pct = (
                (total_active / alloc.amount * 100) if alloc.amount else 0.0
            )
            alloc.transaction_count = len(txs)

    # One2many to transactions (read-only view)
    transaction_ids = fields.One2many(
        'budget.transaction', 'allocation_id', string='Transactions',
    )
