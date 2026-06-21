# -*- coding: utf-8 -*-
"""Budget Transaction Ledger — event-sourced budget tracking.

One record per demand line (MR line / PR line / direct PO line) that
persists through the full procurement lifecycle.  Money flows through
independent stage buckets instead of being deleted and rebuilt:

    reserved_amount  →  committed_amount  →  used_amount
       (MR/PR estimate)   (PO confirmed)       (billed)
                           ↘ released_amount ↙
                              (cancelled)

Design decisions (per user spec):
1. Separate fields reserved/committed/used — amounts differ between
   stages (MR estimate ≠ PO actual ≠ bill actual).
2. Partial billing: committed decrements, used increments
   (PO 100k, bill 60k → committed 40k + used 60k).
3. One transaction per MR line — the transaction owns the full
   lifecycle; PO and bill events update stage amounts in place.
"""
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class BudgetTransaction(models.Model):
    _name = 'budget.transaction'
    _description = 'Budget Transaction Ledger'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'raw_date desc, id desc'
    _rec_name = 'name'

    # ──────────────────────────────────────────────────────────────
    # Identity
    # ──────────────────────────────────────────────────────────────
    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )

    origin_type = fields.Selection([
        ('mr_line', 'Material Requisition'),
        ('pr_line', 'Purchase Requisition'),
        ('direct_po', 'Direct Purchase Order'),
    ], string='Origin Type', required=True, index=True, tracking=True)

    # Generic polymorphic source reference (the DEMAND line)
    source_line_model = fields.Char(
        string='Source Line Model', required=True, index=True,
    )
    source_line_id = fields.Integer(
        string='Source Line ID', required=True, index=True,
    )
    # Header document for display
    source_doc_model = fields.Char(string='Source Doc Model')
    source_doc_id = fields.Integer(string='Source Doc ID', index=True)
    source_doc_name = fields.Char(string='Source Document', tracking=True)

    # ──────────────────────────────────────────────────────────────
    # Raw attributes — FIXED at creation, never auto-changed
    # ──────────────────────────────────────────────────────────────
    raw_date = fields.Date(
        string='Budget Date', required=True, index=True, tracking=True,
        help='The payment/expected-payment date determining which budget '
             'period this transaction falls into.',
    )
    raw_dept_id = fields.Many2one(
        'hr.department', string='Department', index=True,
        help='Department charged for this budget. Fixed at creation to '
             'prevent department drift across the procurement chain.',
    )
    raw_company_id = fields.Many2one(
        'res.company', string='Source Company', required=True, index=True,
    )
    product_id = fields.Many2one(
        'product.product', string='Product', index=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        related='raw_company_id.currency_id', store=True, readonly=True,
    )

    # ──────────────────────────────────────────────────────────────
    # Allocation — resolved lazily
    # ──────────────────────────────────────────────────────────────
    allocation_id = fields.Many2one(
        'monthly.budget.allocation', string='Budget Allocation',
        index=True, tracking=True,
        help='The budget allocation this transaction charges. May be empty '
             '(state=pending) until a matching plan is confirmed.',
    )
    plan_id = fields.Many2one(
        related='allocation_id.plan_id', string='Budget Plan',
        store=True, index=True,
    )

    # ──────────────────────────────────────────────────────────────
    # Amounts by stage — independent buckets
    # ──────────────────────────────────────────────────────────────
    # Invariant: reserved + committed + used + released = total_demand
    # (total_demand may change when a confirmed PO/bill sets a different
    # actual amount, but the four buckets always reconcile.)
    reserved_amount = fields.Float(
        string='Reserved', default=0.0,
        help='Amount in the reserved stage (MR/PR estimate, not yet on a '
             'confirmed PO).',
    )
    committed_amount = fields.Float(
        string='Committed', default=0.0,
        help='Amount on a confirmed PO, not yet billed.',
    )
    used_amount = fields.Float(
        string='Used', default=0.0,
        help='Amount billed (vendor invoice posted).',
    )
    released_amount = fields.Float(
        string='Released', default=0.0,
        help='Amount released due to cancellation or partial close.',
    )

    total_demand = fields.Float(
        string='Total Demand',
        compute='_compute_total_demand', store=True,
        help='Sum of all active stage amounts.',
    )
    active_amount = fields.Float(
        string='Active',
        compute='_compute_total_demand', store=True,
        help='reserved + committed + used (excludes released).',
    )
    primary_stage = fields.Selection([
        ('pending', 'Pending'),
        ('reserved', 'Reserved'),
        ('committed', 'Committed'),
        ('used', 'Used'),
        ('partial', 'Partial Bill'),
        ('closed', 'Closed'),
    ], string='Stage', compute='_compute_primary_stage', store=True,
        index=True, tracking=True,
    )

    # ──────────────────────────────────────────────────────────────
    # Lineage — track the full procurement chain
    # ──────────────────────────────────────────────────────────────
    pool_line_id = fields.Many2one(
        'procurement.pool.line', string='Pool Line',
        help='Procurement pool line this transaction passed through, if any.',
    )
    po_line_id = fields.Many2one(
        'purchase.order.line', string='PO Line',
        help='The confirmed PO line that committed this transaction.',
    )
    po_id = fields.Many2one(
        related='po_line_id.order_id', string='Purchase Order',
        store=True, index=True,
    )
    # Many2many for partial billing: one transaction can be hit by
    # multiple bill lines over time.
    bill_line_ids = fields.Many2many(
        'account.move.line', 'budget_transaction_bill_rel',
        'transaction_id', 'aml_id', string='Bill Lines',
    )

    # ──────────────────────────────────────────────────────────────
    # Status
    # ──────────────────────────────────────────────────────────────
    state = fields.Selection([
        ('pending', 'Pending Allocation'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ], string='Status', default='pending', index=True, tracking=True,
        help='pending = no allocation resolved yet; '
             'active = allocation linked; '
             'closed = fully used or released.',
    )
    month_key = fields.Char(
        string='Month', compute='_compute_month_key', store=True, index=True,
    )
    company_id = fields.Many2one(
        related='raw_company_id', string='Company', store=True, index=True,
    )

    # ══════════════════════════════════════════════════════════════
    # COMPUTES
    # ══════════════════════════════════════════════════════════════
    @api.depends(
        'reserved_amount', 'committed_amount', 'used_amount', 'released_amount')
    def _compute_total_demand(self):
        for rec in self:
            rec.active_amount = (
                rec.reserved_amount + rec.committed_amount + rec.used_amount
            )
            rec.total_demand = rec.active_amount + rec.released_amount

    @api.depends(
        'reserved_amount', 'committed_amount', 'used_amount',
        'released_amount', 'state')
    def _compute_primary_stage(self):
        for rec in self:
            if rec.state == 'pending':
                rec.primary_stage = 'pending'
            elif rec.reserved_amount <= 0 and rec.committed_amount <= 0 \
                    and rec.used_amount <= 0:
                rec.primary_stage = 'closed'
            elif rec.committed_amount > 0 and rec.used_amount > 0:
                rec.primary_stage = 'partial'
            elif rec.used_amount > 0:
                rec.primary_stage = 'used'
            elif rec.committed_amount > 0:
                rec.primary_stage = 'committed'
            else:
                rec.primary_stage = 'reserved'

    @api.depends('raw_date')
    def _compute_month_key(self):
        for rec in self:
            rec.month_key = rec.raw_date.strftime('%Y-%m') if rec.raw_date else False

    # ══════════════════════════════════════════════════════════════
    # CRUD
    # ══════════════════════════════════════════════════════════════
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'budget.transaction') or _('New')
        records = super().create(vals_list)
        # Try to resolve allocation immediately for new transactions
        records._resolve_allocation()
        return records

    # ══════════════════════════════════════════════════════════════
    # ALLOCATION RESOLUTION
    # ══════════════════════════════════════════════════════════════
    def _resolve_allocation(self):
        """Resolve allocation_id for pending/active transactions.

        Uses the same multi-company priority logic as
        monthly.budget.allocation._get_allocation but reads from the
        fixed raw_* fields.  Safe to call repeatedly — skips already
        resolved or closed transactions.
        """
        pending = self.filtered(
            lambda t: not t.allocation_id and t.raw_date
            and t.state != 'closed'
        )
        if not pending:
            return

        Allocation = self.env['monthly.budget.allocation'].sudo()
        for tx in pending:
            alloc = Allocation._get_allocation(
                tx.raw_date, tx.raw_dept_id, tx.raw_company_id,
            )
            if alloc:
                tx.allocation_id = alloc.id
                tx.state = 'active'
            else:
                tx.state = 'pending'

    # ══════════════════════════════════════════════════════════════
    # LIFECYCLE SERVICE METHODS
    # ══════════════════════════════════════════════════════════════
    @api.model
    def upsert_from_demand_line(self, line, vals):
        """Create or refresh a transaction from a demand line (MR/PR line).

        Called when an MR/PR line is approved or its amount changes.
        If a transaction already exists for this source line, it is
        updated (reserved_amount recalculated); otherwise a new one is
        created.
        """
        existing = self.search([
            ('source_line_model', '=', line._name),
            ('source_line_id', '=', line.id),
            ('state', '!=', 'closed'),
        ], limit=1)

        if existing:
            # Only adjust reserved if nothing has been committed/used yet
            if existing.committed_amount == 0 and existing.used_amount == 0:
                existing.write({'reserved_amount': vals.get('reserved_amount', 0.0)})
            return existing

        return self.create(vals)

    def commit_from_po(self, po_line, coverage_amount):
        """Move amount from reserved → committed when a PO confirms.

        ``coverage_amount`` is how much of this transaction the PO line
        covers.  Decrements reserved (up to what's available), increments
        committed by the full coverage amount.  If the PO actual differs
        from the reserved estimate, committed reflects the PO actual.

        Handles direct POs (reserved=0): committed increases even when
        nothing was previously reserved.
        """
        self.ensure_one()
        if coverage_amount <= 0:
            return
        from_reserved = min(coverage_amount, self.reserved_amount)
        self.write({
            'reserved_amount': self.reserved_amount - from_reserved,
            'committed_amount': self.committed_amount + coverage_amount,
            'po_line_id': po_line.id,
        })

    def use_from_bill(self, bill_line, bill_amount):
        """Move amount from committed → used when a bill is posted.

        For partial billing: committed decrements by bill_amount, used
        increments by bill_amount.  The bill_line is linked for audit.
        """
        self.ensure_one()
        move_amount = min(bill_amount, self.committed_amount)
        if move_amount <= 0:
            # Bill without prior commit (direct bill on draft PO):
            # take from reserved if available, else just record as used.
            move_amount = min(bill_amount, self.reserved_amount)
            if move_amount <= 0:
                return
            self.write({
                'reserved_amount': self.reserved_amount - move_amount,
                'used_amount': self.used_amount + move_amount,
                'bill_line_ids': [fields.Command.link(bill_line.id)],
            })
            return
        self.write({
            'committed_amount': self.committed_amount - move_amount,
            'used_amount': self.used_amount + move_amount,
            'bill_line_ids': [fields.Command.link(bill_line.id)],
        })

    def unuse_from_bill(self, bill_line, bill_amount):
        """Reverse a previous use_from_bill when a bill is cancelled.

        Moves amount from used back to committed.  If the transaction
        had no prior commit (direct bill path), moves used back to
        reserved instead.
        """
        self.ensure_one()
        if bill_amount <= 0:
            return
        move_amount = min(bill_amount, self.used_amount)
        if move_amount <= 0:
            return
        if self.committed_amount > 0 or self.po_line_id:
            # Return to committed (normal PO path)
            self.write({
                'used_amount': self.used_amount - move_amount,
                'committed_amount': self.committed_amount + move_amount,
            })
        else:
            # Return to reserved (direct bill path)
            self.write({
                'used_amount': self.used_amount - move_amount,
                'reserved_amount': self.reserved_amount + move_amount,
            })
        # Unlink the bill line from the M2M
        self.bill_line_ids = [fields.Command.unlink(bill_line.id)]
        # Reopen if was closed
        if self.state == 'closed' and self.active_amount > 0:
            self.state = 'active'

    def release(self, amount=None, reason=''):
        """Release active amount back to the released bucket.

        Called on document cancellation.  If ``amount`` is None,
        releases all active amounts.
        """
        for tx in self:
            if amount is None:
                rel = tx.active_amount
            else:
                rel = min(amount, tx.active_amount)
            if rel <= 0:
                continue
            # Release proportionally from reserved and committed
            total_active = tx.active_amount
            if total_active <= 0:
                continue
            res_ratio = tx.reserved_amount / total_active
            from_reserved = rel * res_ratio
            from_committed = rel - from_reserved
            new_reserved = tx.reserved_amount - from_reserved
            new_committed = tx.committed_amount - from_committed
            tx.write({
                'reserved_amount': new_reserved,
                'committed_amount': new_committed,
                'released_amount': tx.released_amount + rel,
            })
            if reason:
                tx.message_post(
                    body=_('Released %s: %s') % (rel, reason),
                    message_type='notification',
                )
            # Check closure using computed values (active_amount is a
            # stored compute that hasn't flushed yet after the write).
            if new_reserved + new_committed + tx.used_amount <= 0:
                tx.state = 'closed'

    def action_resolve_allocation(self):
        """Button action to manually trigger allocation resolution."""
        self._resolve_allocation()

    # ══════════════════════════════════════════════════════════════
    # LOOKUP HELPERS
    # ══════════════════════════════════════════════════════════════
    @api.model
    def find_for_source_line(self, model_name, line_id):
        """Find the active transaction for a source line."""
        return self.search([
            ('source_line_model', '=', model_name),
            ('source_line_id', '=', line_id),
            ('state', '!=', 'closed'),
        ], limit=1)

    @api.model
    def find_for_po_line(self, po_line_id):
        """Find transactions linked to a PO line (committed or used)."""
        return self.search([
            ('po_line_id', '=', po_line_id),
            ('state', '!=', 'closed'),
        ])

    @api.model
    def resolve_pending_for_plan(self, plan):
        """Resolve all pending transactions that fall within a plan's range.

        Called when a plan is confirmed — catches up transactions that
        were created before the plan existed.
        """
        pending = self.search([
            ('state', '=', 'pending'),
            ('raw_date', '>=', plan.date_from),
            ('raw_date', '<=', plan.date_to),
        ])
        pending._resolve_allocation()
        _logger.info(
            'Resolved %d pending budget transactions for plan %s',
            len(pending), plan.name,
        )
        return len(pending)

    # ══════════════════════════════════════════════════════════════
    # CRON
    # ══════════════════════════════════════════════════════════════
    @api.model
    def _cron_resolve_pending(self):
        """Periodic sweep to resolve pending transactions."""
        pending = self.search([('state', '=', 'pending')])
        pending._resolve_allocation()
        _logger.info('Cron: resolved %d pending budget transactions', len(pending))

    # ══════════════════════════════════════════════════════════════
    # CONSTRAINTS
    # ══════════════════════════════════════════════════════════════
    @api.constrains('reserved_amount', 'committed_amount',
                    'used_amount', 'released_amount')
    def _check_non_negative(self):
        """Ensure committed and released are never negative.

        reserved_amount and used_amount may be negative in edge cases:
        - used_amount: vendor refunds (in_refund) create negative usage
        - reserved_amount: over-release corrections
        """
        for rec in self:
            for fname in ('committed_amount', 'released_amount'):
                if getattr(rec, fname) < 0:
                    raise ValidationError(_(
                        'Stage amount %s cannot be negative on %s'
                    ) % (fname, rec.name))
