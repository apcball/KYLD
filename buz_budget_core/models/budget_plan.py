# -*- coding: utf-8 -*-
"""Extend monthly.budget.plan with transaction-based totals and
auto-resolve trigger on confirmation.

When a plan is confirmed, all pending transactions within the plan's
date range are automatically resolved to their allocations.  This
eliminates the need for the manual "Recompute" button.
"""
import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class MonthlyBudgetPlan(models.Model):
    _inherit = 'monthly.budget.plan'

    # ──────────────────────────────────────────────────────────────
    # Transaction-based totals
    # ──────────────────────────────────────────────────────────────
    tx_total_used = fields.Float(
        string='Used (Tx)', compute='_compute_tx_plan_totals', store=True,
    )
    tx_total_reserved = fields.Float(
        string='Reserved (Tx)', compute='_compute_tx_plan_totals', store=True,
    )
    tx_total_committed = fields.Float(
        string='Committed (Tx)', compute='_compute_tx_plan_totals', store=True,
    )
    tx_total_remaining = fields.Float(
        string='Available (Tx)', compute='_compute_tx_plan_totals', store=True,
    )
    tx_usage_pct = fields.Float(
        string='Usage % (Tx)', compute='_compute_tx_plan_totals', store=True,
    )

    @api.depends(
        'allocation_ids.tx_used',
        'allocation_ids.tx_reserved',
        'allocation_ids.tx_committed',
        'total_budget',
    )
    def _compute_tx_plan_totals(self):
        for plan in self:
            used = sum(plan.allocation_ids.mapped('tx_used'))
            reserved = sum(plan.allocation_ids.mapped('tx_reserved'))
            committed = sum(plan.allocation_ids.mapped('tx_committed'))
            plan.tx_total_used = used
            plan.tx_total_reserved = reserved
            plan.tx_total_committed = committed
            plan.tx_total_remaining = (
                plan.total_budget - used - reserved - committed
            )
            total_active = used + reserved + committed
            plan.tx_usage_pct = (
                (total_active / plan.total_budget * 100)
                if plan.total_budget else 0.0
            )

    # ──────────────────────────────────────────────────────────────
    # Auto-resolve on confirm
    # ──────────────────────────────────────────────────────────────
    def action_confirm(self):
        """On confirmation, resolve all pending transactions in range."""
        res = super().action_confirm()
        Transaction = self.env['budget.transaction']
        for plan in self:
            count = Transaction.resolve_pending_for_plan(plan)
            if count:
                plan.message_post(
                    body=_(
                        '<b>Budget plan confirmed.</b><br/>'
                        'Resolved %d pending transactions to allocations.'
                    ) % count,
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
        return res
