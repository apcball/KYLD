# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _get_default_department(self):
        if hasattr(self.env.user, 'employee_id') and self.env.user.employee_id:
            return self.env.user.employee_id.department_id
        if hasattr(self.env.company, 'default_department_id'):
            return self.env.company.default_department_id
        return False

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        store=True,
        default=_get_default_department,
    )

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        moves.filtered(lambda m: m.state in ('draft', 'posted') and m.move_type in ('in_invoice', 'in_refund'))._update_budget_moves()
        return moves

    def action_post(self):
        """Override to write budget moves when vendor bill is posted."""
        res = super().action_post()
        self._update_budget_moves()
        return res

    def button_cancel(self):
        """Override to clear budget moves when vendor bill is canceled."""
        # Fix: Call super first, then clear budget moves to ensure proper rollback
        res = super().button_cancel()
        self._clear_budget_moves()
        self._trigger_linked_po_recompute()  # Cancelled bill un-bills the PO
        return res

    def button_draft(self):
        """Override to clear budget moves when vendor bill is reset to draft."""
        res = super().button_draft()
        self._clear_budget_moves()
        self._trigger_linked_po_recompute()
        return res

    def write(self, vals):
        """Update budget moves if dates, amounts, or state changes on a bill."""
        res = super().write(vals)
        check_fields = {'invoice_date_due', 'amount_total', 'state', 'invoice_date', 'date', 'invoice_line_ids', 'line_ids'}
        if any(f in vals for f in check_fields):
            self.filtered(lambda m: m.state in ('draft', 'posted') and m.move_type in ('in_invoice', 'in_refund'))._update_budget_moves()
            self.filtered(lambda m: m.state not in ('draft', 'posted'))._clear_budget_moves()
        return res

    def unlink(self):
        """Override to clear budget moves and recompute PO when vendor bill is deleted."""
        self._clear_budget_moves()
        
        # Collect linked POs before deleting the bill lines
        linked_pos = self.env['purchase.order']
        for bill in self:
            for line in bill.invoice_line_ids:
                po_line = getattr(line, 'purchase_line_id', False)
                if po_line and po_line.order_id:
                    linked_pos |= po_line.order_id
                    
        res = super().unlink()
        
        # Recompute POs after bill is completely deleted
        for po in linked_pos:
            po._update_budget_moves()
            
        return res

    def _clear_budget_moves(self):
        BudgetMove = self.env['budget.move'].sudo()
        for bill in self:
            moves = BudgetMove.search([('source_model', '=', 'account.move'), ('source_id', '=', bill.id)])
            if moves:
                moves.unlink()

    def _trigger_linked_po_recompute(self):
        """When a bill is cancelled or draft, the PO might need to re-reserve its unbilled amount."""
        linked_pos = self.env['purchase.order']
        for bill in self:
            for line in bill.invoice_line_ids:
                po_line = getattr(line, 'purchase_line_id', False)
                if po_line and po_line.order_id:
                    linked_pos |= po_line.order_id
        if linked_pos:
            linked_pos._update_budget_moves()

    def _convert_bill_amount_to_budget(self, amount, budget_line, budget_date):
        """Convert a bill-currency amount into the allocation's currency."""
        self.ensure_one()
        if self.currency_id == budget_line.currency_id:
            return amount
        return self.currency_id._convert(
            amount,
            budget_line.currency_id,
            self.company_id,
            budget_date,
        )

    def _update_budget_moves(self):
        """Generate budget.move entries for Vendor Bills (draft or posted).

        When a draft bill is created from a PO, the billed lines are recorded as
        'used' budget moves immediately.  The linked PO is then recomputed so that
        its 'reserved' moves cover only the *remaining unbilled* quantity, causing
        the reserved amount to drop by exactly the bill amount.
        """
        # Recursion guard: avoid bill → PO → bill loops
        if self.env.context.get('_budget_bill_updating'):
            return
        self = self.with_context(_budget_bill_updating=True)

        BudgetMove = self.env['budget.move'].sudo()
        BudgetAllocation = self.env['monthly.budget.allocation'].sudo()

        self._clear_budget_moves()  # Clear existing to rebuild

        for bill in self.filtered(
            lambda m: m.move_type in ('in_invoice', 'in_refund')
            and m.state in ('draft', 'posted')
        ):
            budget_date = (
                bill.invoice_date_due
                or bill.invoice_date
                or bill.date
                or fields.Date.today()
            )

            for line in bill.invoice_line_ids:
                if line.display_type not in (False, 'product'):
                    continue

                amount = line.price_subtotal
                if bill.move_type == 'in_refund':
                    amount = -amount

                dists = BudgetMove.extract_analytic_distribution(line)

                for dist in dists:
                    dist_amount = amount * dist['percentage']
                    if dist_amount == 0:
                        continue

                    acc_id = dist['analytic_account_id']
                    dept_id = dist['department_id']

                    # Last-resort fallback: use the bill header's department
                    if not dept_id and bill.department_id:
                        dept_id = bill.department_id.id

                    if not dept_id:
                        message = _(
                            "Cannot record budget usage for vendor bill %(bill)s, "
                            "line %(line)s because no department was found."
                        ) % {
                            'bill': bill.name or '/',
                            'line': line.name or line.id,
                        }
                        if self.env.context.get('_skip_trigger_linked'):
                            _logger.warning(message)
                            continue
                        raise UserError(message)

                    # Use centralized _get_allocation() for consistent
                    # multi-company priority logic (same as PR/MR/PO)
                    dept_obj = self.env['hr.department'].browse(dept_id) if dept_id else False
                    bline = BudgetAllocation._get_allocation(
                        budget_date, dept_obj, bill.company_id
                    )

                    if bline:
                        budget_amount = bill._convert_bill_amount_to_budget(
                            dist_amount, bline, budget_date
                        )
                        BudgetMove.create({
                            'name': f"{bill.name} - {line.name or 'Line'}",
                            'allocation_id': bline.id,
                            'source_model': 'account.move',
                            'source_id': bill.id,
                            'source_line_id': line.id,
                            'analytic_account_id': acc_id,
                            'department_id': dept_id,
                            'amount': budget_amount,
                            'move_type': 'used',
                            'date': budget_date,
                        })
                    else:
                        if self.env.context.get('_skip_trigger_linked'):
                            _logger.warning(
                                "Budget recompute: no confirmed allocation for bill %s, "
                                "department %s, date %s",
                                bill.name,
                                dept_id,
                                budget_date,
                            )
                            continue
                        raise UserError(_(
                            "No confirmed budget allocation found for vendor bill %(bill)s, "
                            "department %(dept)s, date %(date)s."
                        ) % {
                            'bill': bill.name or '/',
                            'dept': dept_id,
                            'date': budget_date,
                        })

        # Trigger PO recompute ONCE after processing all bills (not inside the loop).
        # This reduces the PO's 'reserved' moves to reflect only the unbilled remainder.
        # Skipped in bulk cron mode because the cron already processes all POs.
        if not self.env.context.get('_skip_trigger_linked'):
            self._trigger_linked_po_recompute()
