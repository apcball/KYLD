# -*- coding: utf-8 -*-
"""Document trigger overrides — sync budget.transaction alongside budget.move.

Each document model (MR, PR, PO, bill) already rebuilds budget.move
records via biz_weekly_budget's ``_update_budget_moves``.  This module
hooks into the same trigger points and advances the event-sourced
budget.transaction ledger in parallel.

Design: the sync methods are **idempotent** — calling them multiple
times in the same document state is a no-op.  They check the
transaction's current stage before advancing it.
"""
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════
# Material Requisition — reserve on submit/approve, release on cancel
# ════════════════════════════════════════════════════════════════════
class MaterialRequisition(models.Model):
    _inherit = 'material.requisition'

    def _update_budget_moves(self):
        """Extend biz_weekly_budget's rebuild to also sync transactions."""
        super()._update_budget_moves()
        self._sync_budget_transactions()

    def _sync_budget_transactions(self):
        Transaction = self.env['budget.transaction'].sudo()
        POLine = self.env['purchase.order.line'].sudo()
        for req in self:
            if req.state in ('draft', 'cancelled'):
                # Release transactions for all MR lines
                for line in req.line_ids:
                    tx = Transaction.find_for_source_line(
                        'material.requisition.line', line.id)
                    if tx and tx.state != 'closed' and tx.active_amount > 0:
                        tx.release(reason=_('MR %s state: %s') % (
                            req.name, req.state))
                continue

            budget_date = req.payment_date
            if not budget_date:
                continue

            for line in req.line_ids:
                mr_cost = line.total_cost
                po_lines = POLine.search([
                    ('material_requisition_line_id', '=', line.id),
                    ('order_id.state', 'in', ['purchase', 'done']),
                ])
                po_covered = sum(po_lines.mapped('price_subtotal'))
                uncovered = max(0.0, mr_cost - po_covered)

                tx = Transaction.find_for_source_line(
                    'material.requisition.line', line.id)

                if uncovered <= 0:
                    # Fully covered by PO — release reservation
                    if tx and tx.reserved_amount > 0 \
                            and tx.committed_amount == 0 \
                            and tx.used_amount == 0:
                        tx.release(
                            amount=tx.reserved_amount,
                            reason=_('MR line covered by PO'))
                    continue

                dept = req.department_id
                if tx:
                    # Update reserved if nothing committed yet
                    if tx.committed_amount == 0 and tx.used_amount == 0:
                        if abs(tx.reserved_amount - uncovered) > 0.01:
                            tx.write({'reserved_amount': uncovered})
                else:
                    tx_vals = {
                        'origin_type': 'mr_line',
                        'source_line_model': 'material.requisition.line',
                        'source_line_id': line.id,
                        'source_doc_model': 'material.requisition',
                        'source_doc_id': req.id,
                        'source_doc_name': req.name,
                        'raw_date': budget_date,
                        'raw_dept_id': dept.id if dept else False,
                        'raw_company_id': req.company_id.id,
                        'product_id': (
                            line.product_id.id if line.product_id else False),
                        'reserved_amount': uncovered,
                    }
                    Transaction.create(tx_vals)


# ════════════════════════════════════════════════════════════════════
# Employee Purchase Requisition — reserve on approve, release on cancel
# ════════════════════════════════════════════════════════════════════
class EmployeePurchaseRequisition(models.Model):
    _inherit = 'employee.purchase.requisition'

    def _update_budget_moves(self):
        """Extend biz_weekly_budget's rebuild to also sync transactions."""
        super()._update_budget_moves()
        self._sync_budget_transactions()

    def _sync_budget_transactions(self):
        Transaction = self.env['budget.transaction'].sudo()
        for req in self:
            if req.state == 'draft' or req.state == 'cancelled':
                for line in req.requisition_order_ids:
                    tx = Transaction.find_for_source_line(
                        'requisition.order', line.id)
                    if tx and tx.state != 'closed' and tx.active_amount > 0:
                        tx.release(reason=_('PR %s state: %s') % (
                            req.name, req.state))
                continue

            budget_date = req.payment_date
            if not budget_date:
                continue

            # Skip if linked to a confirmed PO (PO holds the commitment)
            confirmed_pos = self.env['purchase.order'].sudo().search([
                ('state', 'in', ('purchase', 'done')),
                '|', ('requisition_order', '=', req.name),
                     ('pr_number', '=', req.name)
            ], limit=1)
            if confirmed_pos:
                # PO holds the budget — release PR reservation
                for line in req.requisition_order_ids:
                    tx = Transaction.find_for_source_line(
                        'requisition.order', line.id)
                    if tx and tx.reserved_amount > 0 \
                            and tx.committed_amount == 0:
                        tx.release(
                            amount=tx.reserved_amount,
                            reason=_('PR covered by confirmed PO'))
                continue

            for line in req.requisition_order_ids:
                amount = line.price_subtotal
                if amount <= 0:
                    continue

                dept = getattr(req, 'dept_id', False) or \
                    getattr(req, 'department_id', False)
                tx = Transaction.find_for_source_line(
                    'requisition.order', line.id)
                if tx:
                    if tx.committed_amount == 0 and tx.used_amount == 0:
                        if abs(tx.reserved_amount - amount) > 0.01:
                            tx.write({'reserved_amount': amount})
                else:
                    tx_vals = {
                        'origin_type': 'pr_line',
                        'source_line_model': 'requisition.order',
                        'source_line_id': line.id,
                        'source_doc_model': 'employee.purchase.requisition',
                        'source_doc_id': req.id,
                        'source_doc_name': req.name,
                        'raw_date': budget_date,
                        'raw_dept_id': dept.id if dept else False,
                        'raw_company_id': req.company_id.id,
                        'product_id': (
                            line.product_id.id if line.product_id else False),
                        'reserved_amount': amount,
                    }
                    Transaction.create(tx_vals)


# ════════════════════════════════════════════════════════════════════
# Purchase Order — commit on confirm, release on cancel, adjust on change
# ════════════════════════════════════════════════════════════════════
class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    def _update_budget_moves(self):
        """Extend biz_weekly_budget's rebuild to also sync transactions."""
        super()._update_budget_moves()
        self._sync_budget_transactions()

    def _sync_budget_transactions(self):
        Transaction = self.env['budget.transaction'].sudo()
        for po in self:
            if po.state == 'cancel':
                # Release all transactions linked to this PO's lines
                for line in po.order_line:
                    txs = Transaction.find_for_po_line(line.id)
                    for tx in txs:
                        if tx.state != 'closed' and tx.active_amount > 0:
                            tx.release(reason=_('PO %s cancelled') % po.name)
                continue

            if po.state not in ('purchase', 'done'):
                continue

            budget_date = po.payment_date or fields.Date.to_date(po.date_order)
            if not budget_date:
                continue

            for line in po.order_line:
                if line.display_type not in (False, 'product', ''):
                    continue
                coverage = line.price_subtotal
                if coverage <= 0:
                    continue

                mr_line = getattr(line, 'material_requisition_line_id', False)
                if mr_line and mr_line.exists():
                    tx = Transaction.find_for_source_line(
                        'material.requisition.line', mr_line.id)
                    if not tx:
                        continue
                    if not tx.po_line_id:
                        # First commit — move reserved → committed
                        tx.commit_from_po(line, coverage)
                    elif tx.po_line_id.id == line.id:
                        # Already committed by this PO line — adjust
                        # committed to reflect (coverage - used)
                        expected_committed = max(
                            0.0, coverage - tx.used_amount)
                        if abs(tx.committed_amount - expected_committed) > 0.01:
                            tx.write({'committed_amount': expected_committed})
                else:
                    # Direct PO — find or create a direct_po transaction
                    tx = Transaction.find_for_source_line(
                        'purchase.order.line', line.id)
                    if not tx:
                        dept = po.department_id
                        tx_vals = {
                            'origin_type': 'direct_po',
                            'source_line_model': 'purchase.order.line',
                            'source_line_id': line.id,
                            'source_doc_model': 'purchase.order',
                            'source_doc_id': po.id,
                            'source_doc_name': po.name,
                            'raw_date': budget_date,
                            'raw_dept_id': dept.id if dept else False,
                            'raw_company_id': po.company_id.id,
                            'product_id': (
                                line.product_id.id
                                if line.product_id else False),
                            'reserved_amount': 0.0,
                        }
                        tx = Transaction.create(tx_vals)
                    if not tx.po_line_id:
                        tx.commit_from_po(line, coverage)
                    elif tx.po_line_id.id == line.id:
                        expected_committed = max(
                            0.0, coverage - tx.used_amount)
                        if abs(tx.committed_amount - expected_committed) > 0.01:
                            tx.write({'committed_amount': expected_committed})


# ════════════════════════════════════════════════════════════════════
# Vendor Bill (account.move) — use on post, unuse on cancel/draft
# ════════════════════════════════════════════════════════════════════
class AccountMove(models.Model):
    _inherit = 'account.move'

    def _update_budget_moves(self):
        """Extend biz_weekly_budget's rebuild to also sync transactions."""
        super()._update_budget_moves()
        self._sync_budget_transactions()

    def _clear_budget_moves(self):
        """When bill moves are cleared, also reverse used amounts."""
        super()._clear_budget_moves()
        self._unuse_budget_transactions()

    def _sync_budget_transactions(self):
        Transaction = self.env['budget.transaction'].sudo()
        for bill in self:
            if bill.move_type not in ('in_invoice', 'in_refund'):
                continue
            if bill.state not in ('draft', 'posted'):
                # Bill cancelled — reverse used amounts
                self._unuse_budget_transactions_for_bill(bill)
                continue

            budget_date = (
                bill.invoice_date_due or bill.invoice_date or bill.date
                or fields.Date.today()
            )

            for line in bill.invoice_line_ids:
                if line.display_type not in (False, 'product'):
                    continue

                po_line = getattr(line, 'purchase_line_id', False)
                if not po_line:
                    continue

                amount = line.price_subtotal
                if bill.move_type == 'in_refund':
                    amount = -amount
                if amount == 0:
                    continue

                # Find transactions linked to this PO line
                txs = Transaction.find_for_po_line(po_line.id)
                if not txs:
                    # Try demand-line lookup via MR line
                    mr_line = getattr(po_line, 'material_requisition_line_id', False)
                    if mr_line and mr_line.exists():
                        tx = Transaction.find_for_source_line(
                            'material.requisition.line', mr_line.id)
                        if tx:
                            txs = tx
                    if not txs:
                        continue

                # Check if this bill line is already linked
                already_linked = Transaction.search_count([
                    ('bill_line_ids', 'in', line.id),
                ])
                if already_linked:
                    continue

                # Use the first active transaction
                tx = txs[0]
                tx.use_from_bill(line, abs(amount))

    def _unuse_budget_transactions_for_bill(self, bill):
        """Reverse used amounts for a single bill's lines."""
        Transaction = self.env['budget.transaction'].sudo()
        for line in bill.invoice_line_ids:
            if line.display_type not in (False, 'product'):
                continue
            # Find transactions linked to this bill line
            txs = Transaction.search([
                ('bill_line_ids', 'in', line.id),
            ])
            amount = line.price_subtotal
            if bill.move_type == 'in_refund':
                amount = -amount
            for tx in txs:
                tx.unuse_from_bill(line, abs(amount))

    def _unuse_budget_transactions(self):
        """Reverse used amounts for all bills in recordset."""
        for bill in self:
            if bill.move_type not in ('in_invoice', 'in_refund'):
                continue
            self._unuse_budget_transactions_for_bill(bill)
