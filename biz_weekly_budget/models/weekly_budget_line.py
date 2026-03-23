# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class WeeklyBudgetLine(models.Model):
    _name = 'weekly.budget.line'
    _description = 'Weekly Budget Line'
    _order = 'date_from asc'

    plan_id = fields.Many2one(
        'weekly.budget.plan',
        string='Budget Plan',
        required=True,
        ondelete='cascade',
        index=True,
    )
    name = fields.Char(string='Week Label', required=True)
    week_number = fields.Integer(string='Week #')
    date_from = fields.Date(string='Date From', required=True, index=True)
    date_to = fields.Date(string='Date To', required=True, index=True)
    amount_limit = fields.Float(string='Budget Limit', required=True)
    amount_used = fields.Float(
        string='Used Amount',
        compute='_compute_amount_used',
        store=True,
    )
    amount_reserved = fields.Float(
        string='Reserved Amount',
        compute='_compute_amount_reserved',
        store=True,
        help='Total tentative budget reserved from non-draft PRs, MRs, and standalone RFQs.',
    )
    amount_available = fields.Float(
        string='Available',
        compute='_compute_remaining',
        store=True,
        help='Budget Limit minus Used and Reserved amounts.',
    )
    amount_remaining = fields.Float(
        string='Remaining (vs Used)',
        compute='_compute_remaining',
        store=True,
    )
    usage_percentage = fields.Float(
        string='Usage %',
        compute='_compute_remaining',
        store=True,
    )
    status = fields.Selection([
        ('normal', 'Normal'),
        ('exceeded', 'Exceeded'),
    ], string='Status', compute='_compute_remaining', store=True)

    currency_id = fields.Many2one(
        related='plan_id.currency_id',
        string='Currency',
        store=True,
    )
    company_id = fields.Many2one(
        related='plan_id.company_id',
        string='Company',
        store=True,
    )
    all_companies = fields.Boolean(
        related='plan_id.all_companies',
        string='All Companies',
        store=True,
    )
    plan_state = fields.Selection(
        related='plan_id.state',
        string='Plan Status',
        store=True,
    )

    # History tracking
    history_ids = fields.One2many(
        'weekly.budget.line.history',
        'line_id',
        string='Adjustment History',
    )

    def _get_company_domain(self):
        """Return company domain filter for this budget line."""
        if self.plan_id.all_companies:
            return []
        elif self.plan_id.company_id:
            return [('company_id', '=', self.plan_id.company_id.id)]
        return []

    @api.depends('date_from', 'date_to', 'plan_id.company_id',
                 'plan_id.all_companies', 'plan_id.state')
    def _compute_amount_used(self):
        """Compute total used amount based on posted Vendor Bills due this week."""
        for line in self:
            if not line.date_from or not line.date_to:
                line.amount_used = 0.0
                continue

            # Need to find posted Vendor Bills where invoice_date_due is between date_from and date_to
            move_domain = [
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
                ('invoice_date_due', '>=', line.date_from),
                ('invoice_date_due', '<=', line.date_to),
            ]

            if not line.plan_id.all_companies and line.plan_id.company_id:
                move_domain.append(
                    ('company_id', '=', line.plan_id.company_id.id)
                )

            bills = self.env['account.move'].sudo().search(move_domain)
            line.amount_used = sum(bills.mapped('amount_total'))

    @api.depends('date_from', 'date_to', 'plan_id.company_id',
                 'plan_id.all_companies', 'plan_id.state')
    def _compute_amount_reserved(self):
        """
        Compute total budget reserved from:
          1. Non-draft PRs whose payment_date falls in week
          2. Non-draft MRs whose payment_date falls in week
          3. Draft POs (RFQs) NOT linked to any active PR or MR
          4. Confirmed POs (unbilled amount) NOT linked to any active PR or MR

        Key: each source document is counted EXACTLY ONCE. When a PR/MR has
        a confirmed PO, only the PO's unbilled amount is counted (the PR/MR
        is excluded to avoid double counting).
        """
        for line in self:
            if not line.date_from or not line.date_to:
                line.amount_reserved = 0.0
                continue

            date_from = line.date_from
            date_to = line.date_to
            company_id = line.plan_id.company_id.id if not line.plan_id.all_companies else False

            # ── Step A: Fetch PRs and MRs in this week ─────────────────────
            pr_domain = [
                ('state', '!=', 'draft'),
                ('payment_date', '>=', date_from),
                ('payment_date', '<=', date_to),
            ]
            if company_id:
                pr_domain.append(('company_id', '=', company_id))
            prs = self.env['employee.purchase.requisition'].sudo().search(pr_domain)
            pr_name_set = {pr.name for pr in prs}

            mr_domain = [
                ('state', '!=', 'draft'),
                ('payment_date', '>=', date_from),
                ('payment_date', '<=', date_to),
            ]
            if company_id:
                mr_domain.append(('company_id', '=', company_id))
            mrs = self.env['material.requisition'].sudo().search(mr_domain)
            mr_name_to_id = {mr.name: mr.id for mr in mrs}
            mr_id_set = set(mr_name_to_id.values())

            # ── Step B: Determine which PRs/MRs already have confirmed POs ─
            confirmed_po_domain = [('state', 'in', ['purchase', 'done'])]
            if company_id:
                confirmed_po_domain.append(('company_id', '=', company_id))
            confirmed_pos = self.env['purchase.order'].sudo().search(confirmed_po_domain)

            excluded_pr_names = set()
            excluded_mr_ids = set()
            for po in confirmed_pos:
                req_order = (getattr(po, 'requisition_order', '') or '').strip()
                pr_number = (getattr(po, 'pr_number', '') or '').strip()
                origin = (po.origin or '').strip()

                # Match PR by requisition_order, pr_number, or origin
                for val in (req_order, pr_number, origin):
                    if val and val in pr_name_set:
                        excluded_pr_names.add(val)

                # Match MR by M2O field
                mr_link = getattr(po, 'material_requisition_id', False)
                if mr_link and mr_link.id in mr_id_set:
                    excluded_mr_ids.add(mr_link.id)
                # Match MR by origin as fallback
                if origin and origin in mr_name_to_id:
                    excluded_mr_ids.add(mr_name_to_id[origin])

            # ── 1. Non-draft PRs (excluding those with confirmed POs) ──────
            pr_amount = 0.0
            active_pr_names = set()
            for pr in prs:
                if pr.name in excluded_pr_names:
                    continue
                pr_amount += sum(pr.requisition_order_ids.mapped('price_subtotal'))
                active_pr_names.add(pr.name)

            # ── 2. Non-draft MRs (excluding those with confirmed POs) ──────
            mr_amount = 0.0
            active_mr_ids = set()
            active_mr_names = set()
            for mr in mrs:
                if mr.id in excluded_mr_ids:
                    continue
                mr_amount += (mr.total_cost or 0.0)
                active_mr_ids.add(mr.id)
                active_mr_names.add(mr.name)

            # ── 3. Standalone RFQs (draft POs not linked to active PR/MR) ──
            rfq_domain = [
                ('state', '=', 'draft'),
                ('payment_date', '>=', date_from),
                ('payment_date', '<=', date_to),
            ]
            if company_id:
                rfq_domain.append(('company_id', '=', company_id))
            rfqs = self.env['purchase.order'].sudo().search(rfq_domain)

            rfq_amount = 0.0
            for po in rfqs:
                if self._po_linked_to_active_pr_mr(po, active_pr_names, active_mr_ids, active_mr_names):
                    continue
                rfq_amount += po.amount_total

            # ── 4. Confirmed POs (Unbilled) not linked to active PR/MR ─────
            confirmed_po_week_domain = [
                ('state', 'in', ['purchase', 'done']),
                '|',
                '&', ('payment_date', '>=', date_from), ('payment_date', '<=', date_to),
                '&', ('payment_date', '=', False),
                     '&', ('date_order', '>=', fields.Datetime.to_datetime(date_from)),
                          ('date_order', '<=', fields.Datetime.to_datetime(date_to).replace(hour=23, minute=59, second=59))
            ]
            if company_id:
                confirmed_po_week_domain.append(('company_id', '=', company_id))

            week_confirmed_pos = self.env['purchase.order'].sudo().search(confirmed_po_week_domain)

            po_unbilled_amount = 0.0
            for po in week_confirmed_pos:
                if self._po_linked_to_active_pr_mr(po, active_pr_names, active_mr_ids, active_mr_names):
                    continue
                po_unbilled_amount += po.remaining_to_bill

            line.amount_reserved = pr_amount + mr_amount + rfq_amount + po_unbilled_amount

    def _po_linked_to_active_pr_mr(self, po, active_pr_names, active_mr_ids, active_mr_names):
        """Check if a PO is linked to a PR or MR that is already counted as reserved."""
        # Check MR via M2O
        mr_id = getattr(po, 'material_requisition_id', False)
        if mr_id and mr_id.id in active_mr_ids:
            return True
        # Check PR via requisition_order / pr_number
        req_order = (getattr(po, 'requisition_order', '') or '').strip()
        pr_number = (getattr(po, 'pr_number', '') or '').strip()
        if req_order in active_pr_names or pr_number in active_pr_names:
            return True
        # Check origin against active PR or MR names
        origin = (po.origin or '').strip()
        if origin and origin in active_pr_names:
            return True
        if any(mr_name and mr_name in origin for mr_name in active_mr_names):
            return True
        return False

    @api.depends('amount_limit', 'amount_used', 'amount_reserved')
    def _compute_remaining(self):
        for line in self:
            line.amount_remaining = line.amount_limit - line.amount_used
            line.amount_available = line.amount_limit - line.amount_used - line.amount_reserved
            line.usage_percentage = (
                (line.amount_used / line.amount_limit * 100)
                if line.amount_limit else 0.0
            )
            line.status = 'exceeded' if line.amount_used > line.amount_limit else 'normal'

    def action_adjust_budget(self):
        """Open the budget adjustment wizard."""
        self.ensure_one()
        return {
            'name': _('Adjust Budget'),
            'type': 'ir.actions.act_window',
            'res_model': 'budget.adjustment.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_line_id': self.id,
                'default_current_amount': self.amount_limit,
            },
        }

    def _invalidate_reserved(self):
        """Force recompute of amount_reserved for budget lines covering this date range."""
        self.invalidate_recordset(['amount_reserved'])
        self._compute_amount_reserved()


class WeeklyBudgetLineHistory(models.Model):
    _name = 'weekly.budget.line.history'
    _description = 'Budget Line Adjustment History'
    _order = 'create_date desc'

    line_id = fields.Many2one(
        'weekly.budget.line',
        string='Budget Line',
        required=True,
        ondelete='cascade',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Adjusted By',
        default=lambda self: self.env.uid,
        readonly=True,
    )
    date = fields.Datetime(
        string='Date',
        default=fields.Datetime.now,
        readonly=True,
    )
    old_amount = fields.Float(string='Previous Amount', readonly=True)
    new_amount = fields.Float(string='New Amount', readonly=True)
    reason = fields.Text(string='Reason', readonly=True)
