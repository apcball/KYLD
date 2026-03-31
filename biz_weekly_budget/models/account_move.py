# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        """Override to write budget moves when vendor bill is posted."""
        res = super().action_post()
        self._update_budget_moves()
        return res

    def button_cancel(self):
        """Override to clear budget moves when vendor bill is canceled."""
        res = super().button_cancel()
        self._clear_budget_moves()
        self._trigger_linked_po_recompute() # Cancelled bill un-bills the PO
        return res

    def button_draft(self):
        """Override to clear budget moves when vendor bill is reset to draft."""
        res = super().button_draft()
        self._clear_budget_moves()
        self._trigger_linked_po_recompute()
        return res

    def write(self, vals):
        """Update budget moves if due date changes on a posted bill."""
        res = super().write(vals)
        if 'invoice_date_due' in vals or 'amount_total' in vals or 'state' in vals:
            self.filtered(lambda m: m.state == 'posted' and m.move_type in ('in_invoice', 'in_refund'))._update_budget_moves()
            self.filtered(lambda m: m.state != 'posted')._clear_budget_moves()
        return res

    def _clear_budget_moves(self):
        BudgetMove = self.env['budget.move'].sudo()
        for bill in self:
            moves = BudgetMove.search([('source_model', '=', 'account.move'), ('source_id', '=', bill.id)])
            if moves:
                moves.unlink()

    def _trigger_linked_po_recompute(self):
        """When a bill is cancelled or draft, the PO might need to re-reserve its unbilled amount."""
        for bill in self:
            for line in bill.invoice_line_ids:
                po_line = getattr(line, 'purchase_line_id', False)
                if po_line and po_line.order_id:
                    po = po_line.order_id
                    po._update_budget_moves()

    def _update_budget_moves(self):
        """Generate budget.move entries for posted Vendor Bills AND Vendor Credit Notes."""
        BudgetMove = self.env['budget.move'].sudo()
        BudgetLine = self.env['weekly.budget.line'].sudo()
        
        self._clear_budget_moves() # Clear existing to rebuild

        for bill in self.filtered(lambda m: m.move_type in ('in_invoice', 'in_refund') and m.state == 'posted'):
            budget_date = bill.invoice_date_due or bill.date
            if not budget_date:
                continue

            # Need to figure out the budget line
            # It must match date, company (if plan is specific). 
            # We'll map each invoice_line to a budget move
            for line in bill.invoice_line_ids:
                if line.display_type not in (False, 'product'):
                    continue
                
                amount = line.price_subtotal
                if bill.move_type == 'in_refund':
                    amount = -amount
                
                # Fetch distributions
                dists = BudgetMove.extract_analytic_distribution(line)
                
                for dist in dists:
                    dist_amount = amount * dist['percentage']
                    if dist_amount == 0:
                        continue
                        
                    acc_id = dist['analytic_account_id']
                    dept_id = dist['department_id']
                    
                    # Find budget line
                    domain = [
                        ('plan_state', '=', 'confirmed'),
                        ('date_from', '<=', budget_date),
                        ('date_to', '>=', budget_date),
                        ('analytic_account_id', '=', acc_id),
                        ('department_id', '=', dept_id),
                        '|',
                        ('all_companies', '=', True),
                        ('company_id', '=', bill.company_id.id),
                    ]
                    bline = BudgetLine.search(domain, limit=1)
                    if not bline:
                        # Fallback to general line for that date without analytic account constraint if strictly needed
                        # But analytic budget engine requires precise matching
                        bline = BudgetLine.search([
                            ('plan_state', '=', 'confirmed'),
                            ('date_from', '<=', budget_date),
                            ('date_to', '>=', budget_date),
                            ('analytic_account_id', '=', False),
                            ('department_id', '=', False),
                            '|',
                            ('all_companies', '=', True),
                            ('company_id', '=', bill.company_id.id),
                        ], limit=1)
                        
                    if bline:
                        BudgetMove.create({
                            'name': f"{bill.name} - {line.name or 'Line'}",
                            'line_id': bline.id,
                            'source_model': 'account.move',
                            'source_id': bill.id,
                            'source_line_id': line.id,
                            'analytic_account_id': acc_id,
                            'department_id': dept_id,
                            'amount': dist_amount,
                            'move_type': 'used',
                            'date': budget_date,
                        })

            # Also update the POs reserved amount since this bill changes their 'unbilled' amount
            self._trigger_linked_po_recompute()
