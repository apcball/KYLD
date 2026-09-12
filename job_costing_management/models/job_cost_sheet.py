# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class JobCostSheet(models.Model):
    _name = 'job.cost.sheet'
    _description = 'Job Cost Sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name desc'

    name = fields.Char(string='Job Cost Sheet', required=True, copy=False, readonly=True,
                      default=lambda self: _('New'))
    sequence = fields.Integer(string='Sequence', default=10)
    project_id = fields.Many2one('project.project', string='Project/Contract', required=True, index=True)
    job_order_id = fields.Many2one('job.order', string='Job Order', index=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company, index=True)
    
    # State management
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True, index=True)
    
    # Dates
    date_start = fields.Date(string='Start Date', default=fields.Date.today)
    date_end = fields.Date(string='End Date')
    
    # Cost lines
    material_cost_ids = fields.One2many('job.cost.line', 'cost_sheet_id', 
                                       domain=[('cost_type', '=', 'material')],
                                       string='Material Costs')
    labour_cost_ids = fields.One2many('job.cost.line', 'cost_sheet_id', 
                                     domain=[('cost_type', '=', 'labour')],
                                     string='Labour Costs')
    overhead_cost_ids = fields.One2many('job.cost.line', 'cost_sheet_id', 
                                       domain=[('cost_type', '=', 'overhead')],
                                       string='Overhead Costs')
    
    # Totals
    total_material_cost = fields.Float(string='Total Material Cost', compute='_compute_totals', store=True)
    total_labour_cost = fields.Float(string='Total Labour Cost', compute='_compute_totals', store=True)
    total_overhead_cost = fields.Float(string='Total Overhead Cost', compute='_compute_totals', store=True)
    total_cost = fields.Float(string='Total Cost', compute='_compute_totals', store=True)
    
    # Active totals (excluding cancelled/rejected MRs)
    active_material_cost = fields.Float(string='Active Material Cost', compute='_compute_active_totals', store=True,
                                        help='Material cost excluding cancelled/rejected Material Requisitions')
    active_total_cost = fields.Float(string='Active Total Cost', compute='_compute_active_totals', store=True,
                                     help='Total cost excluding cancelled/rejected Material Requisitions')
    
    # BOQ Baseline Totals (original budget, never changes)
    boq_material_cost = fields.Float(string='BOQ Material Cost', compute='_compute_boq_totals', store=True,
                                     help='Original material budget from BOQ')
    boq_labour_cost = fields.Float(string='BOQ Labour Cost', compute='_compute_boq_totals', store=True,
                                   help='Original labour budget from BOQ')
    boq_overhead_cost = fields.Float(string='BOQ Overhead Cost', compute='_compute_boq_totals', store=True,
                                     help='Original overhead budget from BOQ')
    boq_total_cost = fields.Float(string='BOQ Total Cost', compute='_compute_boq_totals', store=True,
                                  help='Total original budget from BOQ')
    
    # Actual costs
    actual_material_cost = fields.Float(string='Actual Material Cost', compute='_compute_actual_costs', store=True)
    actual_labour_cost = fields.Float(string='Actual Labour Cost', compute='_compute_actual_costs', store=True)
    actual_overhead_cost = fields.Float(string='Actual Overhead Cost', compute='_compute_actual_costs', store=True)
    actual_total_cost = fields.Float(string='Actual Total Cost', compute='_compute_actual_costs', store=True)
    
    # Variance
    material_variance = fields.Float(string='Material Variance', compute='_compute_variance', store=True)
    labour_variance = fields.Float(string='Labour Variance', compute='_compute_variance', store=True)
    overhead_variance = fields.Float(string='Overhead Variance', compute='_compute_variance', store=True)
    total_variance = fields.Float(string='Total Variance', compute='_compute_variance', store=True)
    
    # BOQ linkage
    boq_ids = fields.One2many('boq.boq', 'job_cost_sheet_id', string='BOQs')

    # Smart buttons
    purchase_order_count = fields.Integer(string='Purchase Orders', compute='_compute_purchase_order_count')
    timesheet_count = fields.Integer(string='Timesheets', compute='_compute_timesheet_count')
    invoice_count = fields.Integer(string='Invoices', compute='_compute_invoice_count')
    cost_lines_count = fields.Integer(string='Cost Lines', compute='_compute_cost_lines_count')
    boq_count = fields.Integer(string='BOQ Count', compute='_compute_boq_count')
    has_unsynced_boq = fields.Boolean(string='Has Unsynced BOQ', compute='_compute_boq_sync_status')
    shared_analytic_account_sheets = fields.Char(string='Sheets Sharing Analytic Account',
                                                  compute='_compute_shared_analytic_account')
    
    # Other fields
    notes = fields.Text(string='Notes')
    currency_id = fields.Many2one('res.currency', string='Currency')

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', _('Job Cost Sheet name must be unique!')),
        ('check_planned_qty_positive', 'CHECK(1=1)', _('')),  # Placeholder, real check on cost.line
    ]

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            self.analytic_account_id = self.project_id.analytic_account_id
            if self.project_id.company_id:
                self.company_id = self.project_id.company_id

    @api.model
    def create(self, vals):
        # Set default currency if not provided
        if not vals.get('currency_id'):
            # Try to get THB currency first, fallback to company currency
            thb_currency = self.env['res.currency'].search([('name', '=', 'THB')], limit=1)
            if thb_currency:
                vals['currency_id'] = thb_currency.id
            else:
                vals['currency_id'] = self.env.company.currency_id.id
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('job.cost.sheet') or _('New')
        result = super(JobCostSheet, self).create(vals)
        return result
    
    @api.depends('material_cost_ids.total_cost', 'labour_cost_ids.total_cost', 'overhead_cost_ids.total_cost')
    def _compute_totals(self):
        for record in self:
            record.total_material_cost = sum(record.material_cost_ids.mapped('total_cost'))
            record.total_labour_cost = sum(record.labour_cost_ids.mapped('total_cost'))
            record.total_overhead_cost = sum(record.overhead_cost_ids.mapped('total_cost'))
            record.total_cost = record.total_material_cost + record.total_labour_cost + record.total_overhead_cost
    
    def _non_cancelled_boq_lines(self, lines):
        """Drop cost lines whose BOQ was cancelled after the lines were
        created. action_cancel() on boq.boq only flips the BOQ's own state
        and never touches the job.cost.line rows it already produced, so
        without this filter a cancelled BOQ's baseline/planned budget keeps
        counting toward the sheet forever."""
        return lines.filtered(lambda l: not l.boq_line_id or l.boq_line_id.boq_id.state != 'cancelled')

    @api.depends('material_cost_ids.active_total_cost', 'labour_cost_ids.active_total_cost',
                 'overhead_cost_ids.active_total_cost',
                 'material_cost_ids.boq_line_id.boq_id.state', 'labour_cost_ids.boq_line_id.boq_id.state',
                 'overhead_cost_ids.boq_line_id.boq_id.state')
    def _compute_active_totals(self):
        """Compute active totals excluding cancelled/rejected Material Requisitions
        and lines whose BOQ itself was cancelled."""
        for record in self:
            material_lines = record._non_cancelled_boq_lines(record.material_cost_ids)
            labour_lines = record._non_cancelled_boq_lines(record.labour_cost_ids)
            overhead_lines = record._non_cancelled_boq_lines(record.overhead_cost_ids)
            record.active_material_cost = sum(material_lines.mapped('active_total_cost'))
            record.active_total_cost = (
                sum(material_lines.mapped('active_total_cost')) +
                sum(labour_lines.mapped('active_total_cost')) +
                sum(overhead_lines.mapped('active_total_cost'))
            )

    @api.depends('material_cost_ids.boq_total_cost', 'labour_cost_ids.boq_total_cost',
                 'overhead_cost_ids.boq_total_cost',
                 'material_cost_ids.boq_line_id.boq_id.state', 'labour_cost_ids.boq_line_id.boq_id.state',
                 'overhead_cost_ids.boq_line_id.boq_id.state')
    def _compute_boq_totals(self):
        """Compute BOQ baseline totals from cost lines, excluding lines whose
        BOQ was cancelled."""
        for record in self:
            material_lines = record._non_cancelled_boq_lines(record.material_cost_ids)
            labour_lines = record._non_cancelled_boq_lines(record.labour_cost_ids)
            overhead_lines = record._non_cancelled_boq_lines(record.overhead_cost_ids)
            record.boq_material_cost = sum(material_lines.mapped('boq_total_cost'))
            record.boq_labour_cost = sum(labour_lines.mapped('boq_total_cost'))
            record.boq_overhead_cost = sum(overhead_lines.mapped('boq_total_cost'))
            record.boq_total_cost = (record.boq_material_cost + record.boq_labour_cost +
                                    record.boq_overhead_cost)
    
    @api.model
    def _get_bill_actual_cost_totals(self, sheet_ids, analytic_account_ids):
        """Actual cost from POSTED VENDOR BILLS ONLY (account.move.line on a
        posted in_invoice/in_refund) - per user decision 2026-09-12 to treat
        confirmed-but-unbilled PO commitments and timesheets as not yet
        "actual" (see docs/qa/prod_reliability_audit_20260912.md). Replaces
        the previous PO+bill+timesheet query.

        Returns (by_sheet, by_account), each {key: {'material': f, 'labour':
        f, 'overhead': f}}. A sheet's real actual cost is the sum of both
        buckets for its id and its analytic_account_id.

        Two sources, mutually exclusive per line (a line counted by source 1
        is excluded from source 2, so never double-counted):

        1. `job_cost_line_id` set on the bill line: attributed directly to
           that line's own `cost_sheet_id`. Unambiguous - this is what fixes
           the original bug where two sheets sharing one analytic_account_id
           (e.g. a "zone" account covering several plots) both showed the
           combined total, since the old query grouped by account id even
           for this already-sheet-known source (confirmed on PROD
           2026-09-12: JCS/0004..0008/2025 all showed the same 6.5M THB
           zone-wide total instead of their own ~200-300K plot-level cost).
        2. No job_cost_line_id, but `analytic_distribution` matches one of
           these sheets' accounts (comma-separated multi-plan key, weighted
           by stored percentage): attributed by analytic account id. This
           remains genuinely ambiguous when 2+ sheets share an account - a
           bill tagged only at account level, never linked to a specific
           cost line, has no signal saying which plot it belongs to. Cannot
           be dropped: confirmed on PROD (2026-09-12) at ~38.9M THB across
           ~2,792 bill lines system-wide, larger than the ~25.2M/3,544 lines
           that source 1 already captures unambiguously.

        Classification mirrors purchase_order.py's is_service convention for
        source 2 (no product -> overhead, service -> labour, else material);
        source 1 reuses the job.cost.line's own stored cost_type.
        """
        sheet_ids = [sid for sid in (sheet_ids or []) if sid]
        account_ids = list({aid for aid in (analytic_account_ids or []) if aid})
        by_sheet, by_account = {}, {}
        if not sheet_ids and not account_ids:
            return by_sheet, by_account

        self.env['account.move.line'].flush_model()
        self.env['job.cost.line'].flush_model()

        if sheet_ids:
            self.env.cr.execute("""
                SELECT jcl.cost_sheet_id, jcl.cost_type, SUM(aml.balance)
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN job_cost_line jcl ON jcl.id = aml.job_cost_line_id
                WHERE am.state = 'posted' AND am.move_type IN ('in_invoice', 'in_refund')
                  AND aml.display_type = 'product'
                  AND jcl.cost_sheet_id = ANY(%(sheet_ids)s)
                GROUP BY jcl.cost_sheet_id, jcl.cost_type
            """, {'sheet_ids': sheet_ids})
            for sheet_id, bucket, total in self.env.cr.fetchall():
                by_sheet.setdefault(sheet_id, {'material': 0.0, 'labour': 0.0, 'overhead': 0.0})
                by_sheet[sheet_id][bucket] = float(total or 0.0)

        if account_ids:
            self.env.cr.execute("""
                WITH ids AS (SELECT unnest(%(ids)s::int[]) AS account_id)
                SELECT
                    ids.account_id,
                    CASE
                        WHEN aml.product_id IS NULL THEN 'overhead'
                        WHEN pt.detailed_type = 'service' THEN 'labour'
                        ELSE 'material'
                    END AS bucket,
                    SUM((kv.value::numeric / 100.0) * aml.balance) AS amount
                FROM account_move_line aml
                JOIN account_move am ON am.id = aml.move_id
                JOIN jsonb_each_text(COALESCE(aml.analytic_distribution, '{}'::jsonb)) AS kv(key, value) ON TRUE
                JOIN ids ON kv.key ~ ('(^|,)' || ids.account_id || '(,|$)')
                LEFT JOIN product_product pp ON pp.id = aml.product_id
                LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
                WHERE am.state = 'posted' AND am.move_type IN ('in_invoice', 'in_refund')
                  AND aml.display_type = 'product'
                  AND aml.job_cost_line_id IS NULL
                GROUP BY ids.account_id, bucket
            """, {'ids': account_ids})
            for account_id, bucket, total in self.env.cr.fetchall():
                by_account.setdefault(account_id, {'material': 0.0, 'labour': 0.0, 'overhead': 0.0})
                by_account[account_id][bucket] = float(total or 0.0)

        return by_sheet, by_account

    @api.depends('material_cost_ids.actual_cost', 'labour_cost_ids.actual_cost', 'overhead_cost_ids.actual_cost')
    def _compute_actual_costs(self):
        by_sheet, by_account = self._get_bill_actual_cost_totals(
            self.ids, self.mapped('analytic_account_id').ids)
        empty = {'material': 0.0, 'labour': 0.0, 'overhead': 0.0}
        for record in self:
            b1 = by_sheet.get(record.id, empty)
            b2 = by_account.get(record.analytic_account_id.id, empty) if record.analytic_account_id else empty
            record.actual_material_cost = b1['material'] + b2['material']
            record.actual_labour_cost = b1['labour'] + b2['labour']
            record.actual_overhead_cost = b1['overhead'] + b2['overhead']
            record.actual_total_cost = (record.actual_material_cost + record.actual_labour_cost
                                         + record.actual_overhead_cost)
    
    @api.depends('total_material_cost', 'actual_material_cost', 'total_labour_cost', 'actual_labour_cost',
                 'total_overhead_cost', 'actual_overhead_cost', 'total_cost', 'actual_total_cost')
    def _compute_variance(self):
        for record in self:
            record.material_variance = record.actual_material_cost - record.total_material_cost
            record.labour_variance = record.actual_labour_cost - record.total_labour_cost
            record.overhead_variance = record.actual_overhead_cost - record.total_overhead_cost
            record.total_variance = record.actual_total_cost - record.total_cost
    
    def _compute_purchase_order_count(self):
        for record in self:
            # Get purchase orders linked through job cost lines
            all_cost_line_ids = record.material_cost_ids.ids + record.overhead_cost_ids.ids
            if all_cost_line_ids:
                po_line_ids = self.env['purchase.order.line'].search([
                    ('job_cost_line_id', 'in', all_cost_line_ids),
                    ('job_cost_line_id', '!=', False)  # Filter out empty job_cost_line_id
                ])
                po_ids_via_lines = set(po_line_ids.mapped('order_id.id'))
            else:
                po_ids_via_lines = set()
            
            # Get purchase orders linked directly to this job cost sheet
            po_ids_direct = set(self.env['purchase.order'].search([
                ('job_cost_sheet_id', '=', record.id)
            ]).ids)
            
            # Combine both sets and get unique count
            all_po_ids = po_ids_via_lines.union(po_ids_direct)
            record.purchase_order_count = len(all_po_ids)
    
    def _compute_timesheet_count(self):
        for record in self:
            record.timesheet_count = self.env['account.analytic.line'].search_count([
                ('job_cost_line_id', 'in', record.labour_cost_ids.ids)
            ])
    
    def _compute_invoice_count(self):
        for record in self:
            # Get invoice lines linked to job cost lines
            all_cost_line_ids = record.material_cost_ids.ids + record.labour_cost_ids.ids + record.overhead_cost_ids.ids
            if all_cost_line_ids:
                invoice_line_ids = self.env['account.move.line'].search([
                    ('job_cost_line_id', 'in', all_cost_line_ids),
                    ('job_cost_line_id', '!=', False)  # Filter out empty job_cost_line_id
                ])
                # Get unique invoice IDs using set instead of list
                invoice_ids = set(invoice_line_ids.mapped('move_id.id'))
                # Filter out None values and count
                invoice_ids = {inv_id for inv_id in invoice_ids if inv_id}
                record.invoice_count = len(invoice_ids)
            else:
                record.invoice_count = 0
    
    @api.depends('material_cost_ids', 'labour_cost_ids', 'overhead_cost_ids')
    def _compute_cost_lines_count(self):
        for record in self:
            record.cost_lines_count = len(record.material_cost_ids) + len(record.labour_cost_ids) + len(record.overhead_cost_ids)

    @api.depends('boq_ids')
    def _compute_boq_count(self):
        for record in self:
            record.boq_count = len(record.boq_ids)

    @api.depends('boq_ids.total_cost', 'boq_ids.state', 'boq_total_cost')
    def _compute_boq_sync_status(self):
        """A BOQ is 'unsynced' when its lines haven't been materialized as
        job.cost.line records yet (action_create_job_cost_lines never run),
        so its budget is linked but invisible in boq_total_cost. Cancelled
        BOQs are excluded from this comparison - their budget is meant to be
        invisible in boq_total_cost now (see _compute_boq_totals), not a
        sync gap."""
        for record in self:
            active_boqs = record.boq_ids.filtered(lambda b: b.state != 'cancelled')
            record.has_unsynced_boq = bool(active_boqs) and (
                sum(active_boqs.mapped('total_cost')) != record.boq_total_cost
            )

    def _compute_shared_analytic_account(self):
        """Actual Cost is computed by grouping PO/bill/timesheet lines by
        analytic_account_id (_get_analytic_actual_cost_totals), not by sheet
        id. If two job.cost.sheet records share the same analytic account
        (e.g. two sheets created for the same project), their Actual Cost
        figures are identical/combined - not each sheet's own number. Warn
        instead of silently showing a misleading total (see
        scripts/audit_jcs0028_labour_cost.py, JCS/0024/2026 vs
        JCS/0028/2026, 2026-09-12)."""
        for record in self:
            if not record.analytic_account_id:
                record.shared_analytic_account_sheets = False
                continue
            others = self.search([
                ('analytic_account_id', '=', record.analytic_account_id.id),
                ('id', '!=', record.id),
            ])
            record.shared_analytic_account_sheets = ', '.join(others.mapped('name')) if others else False

    def action_approve(self):
        self.write({'state': 'approved'})
        
    def action_done(self):
        self.write({'state': 'done'})
        
    def action_cancel(self):
        self.write({'state': 'cancelled'})
        
    def action_draft(self):
        self.write({'state': 'draft'})
        
    def action_view_purchase_orders(self):
        # Get purchase orders linked through job cost lines
        all_cost_line_ids = self.material_cost_ids.ids + self.overhead_cost_ids.ids
        if all_cost_line_ids:
            po_line_ids = self.env['purchase.order.line'].search([
                ('job_cost_line_id', 'in', all_cost_line_ids),
                ('job_cost_line_id', '!=', False)  # Filter out empty job_cost_line_id
            ])
            po_ids_via_lines = set(po_line_ids.mapped('order_id.id'))
        else:
            po_ids_via_lines = set()
        
        # Get purchase orders linked directly to this job cost sheet
        po_ids_direct = set(self.env['purchase.order'].search([
            ('job_cost_sheet_id', '=', self.id)
        ]).ids)
        
        # Combine both sets of IDs
        all_po_ids = po_ids_via_lines.union(po_ids_direct)
        all_po_ids = list(all_po_ids)  # Convert set to list for domain
        
        # Use our custom purchase order view to avoid approval_state errors
        tree_view = self.env.ref('job_costing_management.view_purchase_order_tree_job_costing', False)
        
        return {
            'name': 'Purchase Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'views': [(tree_view.id if tree_view else False, 'tree'), (False, 'form')],
            'domain': [('id', 'in', all_po_ids)],
            'context': {'res_model': 'purchase.order'},
        }
    
    def action_view_timesheets(self):
        return {
            'name': 'Timesheets',
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_mode': 'tree,form',
            'domain': [('job_cost_line_id', 'in', self.labour_cost_ids.ids)],
        }
    
    def action_view_invoices(self):
        all_cost_line_ids = self.material_cost_ids.ids + self.labour_cost_ids.ids + self.overhead_cost_ids.ids
        if all_cost_line_ids:
            invoice_line_ids = self.env['account.move.line'].search([
                ('job_cost_line_id', 'in', all_cost_line_ids),
                ('job_cost_line_id', '!=', False)  # Filter out empty job_cost_line_id
            ])
            # Get unique invoice IDs using set instead of list
            invoice_ids = set(invoice_line_ids.mapped('move_id.id'))
            # Filter out None values and convert to list
            invoice_ids = list({inv_id for inv_id in invoice_ids if inv_id})
        else:
            invoice_ids = []
        
        return {
            'name': 'Invoices',
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', invoice_ids)],
        }
    
    def action_sync_actual_costs(self):
        """Manually sync actual costs from all linked POs and Invoices.
        
        Step 1: Find ALL related POs (direct link, from MRs, from Pool allocations)
        Step 2: Link unlinked PO lines to matching cost lines
        Step 3: Link unlinked invoice lines to matching cost lines
        Step 4: Force recompute all actual cost fields
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        _logger.info(f"=== Syncing actual costs for Job Cost Sheet: {self.name} ===")
        
        # --- Step 1: Find ALL related Purchase Orders ---
        po_ids = set()
        
        # 1a. POs directly linked to this job cost sheet
        direct_pos = self.env['purchase.order'].search([
            ('job_cost_sheet_id', '=', self.id)
        ])
        po_ids.update(direct_pos.ids)
        
        # 1b. POs linked via PO lines' job_cost_sheet_id
        po_lines_linked = self.env['purchase.order.line'].search([
            ('job_cost_sheet_id', '=', self.id)
        ])
        po_ids.update(po_lines_linked.mapped('order_id').ids)
        
        # 1c. POs linked via purchase allocations
        allocations = self.env['purchase.allocation'].search([
            ('job_cost_sheet_id', '=', self.id)
        ])
        po_ids.update(allocations.mapped('po_line_id.order_id').ids)
        
        # 1d. POs linked via MR lines in this cost sheet's MRs
        if self.project_id:
            mr_pos = self.env['purchase.order'].search([
                ('project_id', '=', self.project_id.id),
                ('state', 'in', ['purchase', 'done']),
            ])
            po_ids.update(mr_pos.ids)
        
        all_pos = self.env['purchase.order'].browse(list(po_ids))
        _logger.info(f"Found {len(all_pos)} related POs: {all_pos.mapped('name')}")
        
        # --- Step 2: Link unlinked PO lines to cost lines ---
        all_cost_lines = (
            self.material_cost_ids | self.labour_cost_ids | self.overhead_cost_ids
        )
        
        linked_count = 0
        for po in all_pos.filtered(lambda p: p.state in ('purchase', 'done')):
            # Set job_cost_sheet_id on PO if not set
            if not po.job_cost_sheet_id:
                po.job_cost_sheet_id = self.id
                
            for po_line in po.order_line:
                # Check if already linked to a cost line IN THIS job cost sheet
                if po_line.job_cost_line_id and po_line.job_cost_line_id.cost_sheet_id.id == self.id:
                    continue  # Correctly linked to this JCS
                
                product = po_line.product_id
                if not product:
                    continue
                
                # Find matching cost line in THIS JCS
                matching = all_cost_lines.filtered(lambda l: l.product_id == product)
                if matching:
                    po_line.write({
                        'job_cost_line_id': matching[0].id,
                        'job_cost_sheet_id': self.id,
                    })
                    linked_count += 1
                    _logger.info(f"  Linked PO line {po.name}/{product.name} → cost line {matching[0].name} (id={matching[0].id})")
        
        # --- Step 3: Link unlinked Invoice lines ---
        invoice_linked = 0
        invoices = self.env['account.move'].search([
            '|',
            ('job_cost_sheet_id', '=', self.id),
            ('invoice_origin', 'in', all_pos.mapped('name')),
            ('move_type', 'in', ['in_invoice', 'in_refund']),
        ])
        
        for inv in invoices:
            if not inv.job_cost_sheet_id:
                inv.job_cost_sheet_id = self.id
                
            for inv_line in inv.invoice_line_ids:
                # Check if correctly linked to a cost line in THIS JCS
                if inv_line.job_cost_line_id and inv_line.job_cost_line_id.cost_sheet_id.id == self.id:
                    continue
                
                product = inv_line.product_id
                if not product:
                    continue
                
                matching = all_cost_lines.filtered(lambda l: l.product_id == product)
                if matching:
                    inv_line.write({'job_cost_line_id': matching[0].id})
                    invoice_linked += 1
        
        # --- Step 4: Force recompute ---
        for cost_line in all_cost_lines:
            if cost_line.cost_type == 'labour':
                cost_line._compute_actual_qty()
                cost_line._compute_actual_unit_cost()
                cost_line._compute_actual_cost()
            else:
                cost_line.update_actual_costs_from_purchases()
                # Also force recompute computed fields
                cost_line._compute_actual_qty()
                cost_line._compute_actual_unit_cost()
                cost_line._compute_actual_cost()
                
        # Force recompute job cost sheet totals
        self._compute_actual_costs()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'job.cost.sheet',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_recalculate_active_costs(self):
        """Refresh active planned amounts using the existing computations."""
        self.ensure_one()
        lines = self.material_cost_ids | self.labour_cost_ids | self.overhead_cost_ids
        lines._compute_active_planned_qty()
        lines._compute_active_total_cost()
        self._compute_active_totals()
        return self._cost_refresh_notification()

    def _cost_refresh_notification(self):
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('Costs Updated'),
                'message': _('Cost totals have been updated.'),
                'type': 'success', 'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            },
        }

    def action_update_costs(self):
        self.ensure_one()
        if self.state in ('approved', 'done'):
            self.action_sync_actual_costs()
        return self.action_recalculate_active_costs()
    
    def action_create_rfq(self):
        """Open wizard to create RFQ from job cost sheet"""
        return {
            'name': 'Create RFQ from Job Cost Sheet',
            'type': 'ir.actions.act_window',
            'res_model': 'create.rfq.from.job.cost',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_job_cost_sheet_id': self.id,
            }
        }
    
    def action_view_cost_analysis(self):
        """Open detailed cost analysis view"""
        return {
            'name': 'Cost Analysis',
            'type': 'ir.actions.act_window',
            'res_model': 'job.cost.line',
            'view_mode': 'tree,form',
            'domain': [('cost_sheet_id', '=', self.id)],
            'context': {
                'default_cost_sheet_id': self.id,
                'search_default_group_cost_type': 1,
            },
        }
    
    def action_view_boqs(self):
        """Open the BOQs linked to this job cost sheet"""
        return {
            'name': f'BOQs - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'boq.boq',
            'view_mode': 'tree,form,kanban',
            'domain': [('job_cost_sheet_id', '=', self.id)],
            'context': {'default_job_cost_sheet_id': self.id, 'default_project_id': self.project_id.id},
        }

    def action_view_all_cost_lines(self):
        """Open all cost lines for this job cost sheet"""
        return {
            'name': f'Cost Lines - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'job.cost.line',
            'view_mode': 'tree,form',
            'domain': [('cost_sheet_id', '=', self.id)],
            'context': {
                'default_cost_sheet_id': self.id,
                'default_analytic_account_id': self.analytic_account_id.id,
            },
        }


class JobCostLine(models.Model):
    _name = 'job.cost.line'
    _description = 'Job Cost Line'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    cost_sheet_id = fields.Many2one('job.cost.sheet', string='Cost Sheet', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', related='cost_sheet_id.company_id', string='Company', store=True, readonly=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    # Cost type
    cost_type = fields.Selection([
        ('material', 'Material'),
        ('labour', 'Labour'),
        ('overhead', 'Overhead')
    ], string='Cost Type', required=True, tracking=True, index=True)
    
    # Product/Service
    product_id = fields.Many2one('product.product', string='Product/Service', tracking=True, index=True)
    name = fields.Char(string='Description', required=True, tracking=True)
    
    # Quantities
    planned_qty = fields.Float(string='Planned Quantity', default=1.0, tracking=True)
    active_planned_qty = fields.Float(string='Active Planned Quantity', compute='_compute_active_planned_qty', store=True,
                                      help='Planned quantity excluding cancelled/rejected Material Requisitions')
    actual_qty = fields.Float(string='Actual Quantity', compute='_compute_actual_qty', store=True)
    
    # Unit costs
    unit_cost = fields.Float(string='Unit Cost', tracking=True)
    actual_unit_cost = fields.Float(string='Actual Unit Cost', compute='_compute_actual_unit_cost', store=True)
    
    # Total costs
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)
    active_total_cost = fields.Float(string='Active Total Cost', compute='_compute_active_total_cost', store=True,
                                      help='Total cost excluding cancelled/rejected Material Requisitions')
    actual_cost = fields.Float(string='Actual Cost', compute='_compute_actual_cost', store=True)
    
    # BOQ Baseline (original budget from BOQ, set once, never changes)
    boq_qty = fields.Float(string='BOQ Quantity', default=0.0,
                           help='Original quantity from BOQ (baseline budget)')
    boq_unit_cost = fields.Float(string='BOQ Unit Cost', default=0.0,
                                 help='Original unit cost from BOQ (baseline budget)')
    boq_total_cost = fields.Float(string='BOQ Total Cost', compute='_compute_boq_total_cost', store=True,
                                  help='BOQ baseline cost = boq_qty × boq_unit_cost')
    
    # Variance
    qty_variance = fields.Float(string='Quantity Variance', compute='_compute_variance', store=True)
    cost_variance = fields.Float(string='Cost Variance', compute='_compute_variance', store=True)
    
    # UOM
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    
    # Analytic
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', index=True)
    
    # Relations
    material_requisition_line_ids = fields.One2many('material.requisition.line', 'job_cost_line_id', string='Material Requisition Lines')
    purchase_order_line_ids = fields.One2many('purchase.order.line', 'job_cost_line_id', string='Purchase Order Lines')
    timesheet_ids = fields.One2many('account.analytic.line', 'job_cost_line_id', string='Timesheets')
    invoice_line_ids = fields.One2many('account.move.line', 'job_cost_line_id', string='Invoice Lines')
    boq_line_id = fields.Many2one('boq.line', string='BOQ Line', index=True)
    
    # Source tracking fields to prevent duplicates
    source_po_line_id = fields.Many2one('purchase.order.line', string='Source PO Line', index=True, 
                                        help='Tracks the PO line that created this cost line to prevent duplicates')
    source_timesheet_id = fields.Many2one('account.analytic.line', string='Source Timesheet', index=True,
                                          help='Tracks the timesheet that created this cost line to prevent duplicates')
    source_invoice_line_id = fields.Many2one('account.move.line', string='Source Invoice Line', index=True,
                                             help='Tracks the invoice line that created this cost line to prevent duplicates')
    
    # Currency (inherits from cost sheet)
    currency_id = fields.Many2one('res.currency', related='cost_sheet_id.currency_id', string='Currency', store=True, readonly=True)

    _sql_constraints = [
        ('check_planned_qty_positive', 'CHECK(planned_qty >= 0)', _('Planned quantity must be positive!')),
        ('check_unit_cost_positive', 'CHECK(unit_cost >= 0)', _('Unit cost must be positive!')),
    ]

    # Cost computations
    @api.depends('boq_qty', 'boq_unit_cost')
    def _compute_boq_total_cost(self):
        """Compute BOQ baseline total cost"""
        for record in self:
            record.boq_total_cost = record.boq_qty * record.boq_unit_cost
    
    @api.depends('planned_qty', 'unit_cost')
    def _compute_total_cost(self):
        """Compute base total cost from planned_qty (unchanged for compatibility)"""
        for record in self:
            record.total_cost = record.planned_qty * record.unit_cost
    
    @api.depends('active_planned_qty', 'unit_cost')
    def _compute_active_total_cost(self):
        """Compute active total cost using active_planned_qty to exclude cancelled MRs"""
        for record in self:
            record.active_total_cost = record.active_planned_qty * record.unit_cost
    
    @api.depends('planned_qty', 'boq_line_id', 'cost_sheet_id', 'product_id')
    def _compute_active_planned_qty(self):
        """
        Compute active planned quantity by filtering out cancelled/rejected Material Requisitions.
        
        Logic supports TWO scenarios:
        1. Job Cost Line has boq_line_id (created from BOQ)
           → Find MRs through BOQ Line
        2. Job Cost Line created manually (no boq_line_id)
           → Find MRs through Job Cost Sheet → BOQ → MR Lines matching product
        """
        for record in self:
            # Scenario 1: Has BOQ Line link (created from BOQ)
            if record.boq_line_id:
                mr_lines = record.boq_line_id.requisition_line_ids
                
                if not mr_lines:
                    record.active_planned_qty = record.planned_qty
                else:
                    active_mr_lines = mr_lines.filtered(
                        lambda l: l.requisition_state not in ['cancelled', 'rejected']
                    )
                    record.active_planned_qty = sum(active_mr_lines.mapped('quantity')) if active_mr_lines else 0.0
            
            # Scenario 2: No BOQ Line link (manual Job Cost Sheet)
            elif record.cost_sheet_id and record.product_id:
                # Find all MRs created for this Job Cost Sheet's BOQ
                mr_lines = self.env['material.requisition.line'].search([
                    ('requisition_id.job_cost_sheet_id', '=', record.cost_sheet_id.id),
                    ('product_id', '=', record.product_id.id),
                ])
                
                if not mr_lines:
                    # No MRs found for this product
                    record.active_planned_qty = record.planned_qty
                else:
                    # Filter out cancelled/rejected MRs
                    active_mr_lines = mr_lines.filtered(
                        lambda l: l.requisition_state not in ['cancelled', 'rejected']
                    )
                    record.active_planned_qty = sum(active_mr_lines.mapped('quantity')) if active_mr_lines else 0.0

            else:
                # No BOQ Line and no product/cost sheet - use full planned qty
                record.active_planned_qty = record.planned_qty
    
    @api.depends('purchase_order_line_ids.product_qty', 'purchase_order_line_ids.qty_received',
                 'timesheet_ids.unit_amount', 'invoice_line_ids.quantity')
    def _compute_actual_qty(self):
        for record in self:
            if record.cost_type == 'material':
                # Use received quantity from confirmed purchase orders
                po_lines = record.purchase_order_line_ids.filtered(lambda l: l.order_id.state in ['purchase', 'done'])
                record.actual_qty = sum(po_lines.mapped('qty_received'))
            elif record.cost_type == 'labour':
                # Labour: combine timesheets + PO lines (for subcontracted labour)
                timesheet_qty = sum(record.timesheet_ids.mapped('unit_amount'))
                po_lines = record.purchase_order_line_ids.filtered(lambda l: l.order_id.state in ['purchase', 'done'])
                po_qty = sum(po_lines.mapped('qty_received'))
                record.actual_qty = timesheet_qty + po_qty
                    
            else:  # overhead
                # Prevent double counting - use invoice lines OR purchase orders, not both.
                # Switch on presence of posted invoice lines, not their sign, so
                # credit notes (negative qty/amount) still count as the source
                # instead of being ignored in favour of the PO fallback.
                invoice_lines = record.invoice_line_ids.filtered(lambda l: l.move_id.state == 'posted')
                if invoice_lines:
                    record.actual_qty = sum(invoice_lines.mapped('quantity'))
                else:
                    po_lines = record.purchase_order_line_ids.filtered(lambda l: l.order_id.state in ['purchase', 'done'])
                    record.actual_qty = sum(po_lines.mapped('qty_received'))
    
    @api.depends('purchase_order_line_ids.price_unit', 'purchase_order_line_ids.product_qty', 
                 'timesheet_ids.amount', 'invoice_line_ids.price_unit', 'invoice_line_ids.quantity')
    def _compute_actual_unit_cost(self):
        for record in self:
            total_cost = 0
            total_qty = 0
            
            if record.cost_type == 'material':
                # Use confirmed/received purchase order lines
                for line in record.purchase_order_line_ids.filtered(lambda l: l.order_id.state in ['purchase', 'done']):
                    total_cost += line.price_subtotal
                    total_qty += line.product_qty
            elif record.cost_type == 'labour':
                # Labour: combine timesheets + PO lines (for subcontracted labour)
                for line in record.timesheet_ids:
                    cost_amount = abs(line.amount) if line.amount else 0
                    total_cost += cost_amount
                    total_qty += line.unit_amount
                for line in record.purchase_order_line_ids.filtered(lambda l: l.order_id.state in ['purchase', 'done']):
                    total_cost += line.price_subtotal
                    total_qty += line.product_qty
            else:  # overhead
                # Prevent double counting - use invoice lines OR purchase orders, not
                # both. Same source switch as _compute_actual_qty: presence of
                # posted invoice lines decides, so credit notes aren't dropped.
                invoice_lines = record.invoice_line_ids.filtered(lambda l: l.move_id.state == 'posted')
                if invoice_lines:
                    total_cost = sum(invoice_lines.mapped('price_subtotal'))
                    total_qty = sum(invoice_lines.mapped('quantity'))
                else:
                    for line in record.purchase_order_line_ids.filtered(lambda l: l.order_id.state in ['purchase', 'done']):
                        total_cost += line.price_subtotal
                        total_qty += line.product_qty
            
            record.actual_unit_cost = total_cost / total_qty if total_qty else 0
    
    @api.depends('actual_qty', 'actual_unit_cost')
    def _compute_actual_cost(self):
        for record in self:
            record.actual_cost = record.actual_qty * record.actual_unit_cost
    
    @api.depends('actual_qty', 'planned_qty', 'actual_cost', 'total_cost')
    def _compute_variance(self):
        for record in self:
            record.qty_variance = record.actual_qty - record.planned_qty
            record.cost_variance = record.actual_cost - record.total_cost
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.name
            self.unit_cost = self.product_id.standard_price
            self.uom_id = self.product_id.uom_id
            
            # Store original cost type to check if it changes
            original_cost_type = self.cost_type
            
            # Auto-adjust cost type based on product type
            if self.product_id.detailed_type == 'service':
                # Service products should be labour cost type
                self.cost_type = 'labour'
                # Set appropriate UOM for labour (hours)
                hours_uom = self.env['uom.uom'].search([('name', 'ilike', 'hour')], limit=1)
                if hours_uom:
                    self.uom_id = hours_uom
                    
            elif self.product_id.detailed_type in ['product', 'consu']:
                # Storable and consumable products should be material cost type
                self.cost_type = 'material'
                # Keep product's default UOM for materials
                self.uom_id = self.product_id.uom_id
            
            # Show notification if cost type was changed automatically
            if original_cost_type and original_cost_type != self.cost_type:
                return {
                    'warning': {
                        'title': _('Cost Type Auto-Adjusted'),
                        'message': _('Cost type has been automatically changed to "%s" based on the selected product type (%s).') % (
                            dict(self._fields['cost_type'].selection)[self.cost_type],
                            self.product_id.detailed_type.title()
                        )
                    }
                }
    
    @api.onchange('cost_type')
    def _onchange_cost_type(self):
        """Clear product when cost type changes to ensure proper domain filtering"""
        if self.cost_type:
            self.product_id = False
            # Set default UOM based on cost type
            if self.cost_type == 'labour':
                # Try to find Hours UOM
                hours_uom = self.env['uom.uom'].search([('name', 'ilike', 'hour')], limit=1)
                if hours_uom:
                    self.uom_id = hours_uom
            elif self.cost_type == 'material':
                # Try to find Units UOM
                units_uom = self.env['uom.uom'].search([('name', 'ilike', 'unit')], limit=1)
                if units_uom:
                    self.uom_id = units_uom
    
    @api.constrains('cost_type', 'product_id')
    def _check_product_cost_type_consistency(self):
        """Ensure product type matches cost type with flexible validation"""
        for record in self:
            if record.product_id and record.cost_type:
                # Skip validation in certain contexts (like RFQ creation)
                if self.env.context.get('skip_product_validation', False):
                    continue
                    
                # Check for product type mismatches
                validation_issues = []
                
                if record.cost_type == 'material' and record.product_id.detailed_type == 'service':
                    validation_issues.append({
                        'type': 'material_service',
                        'message': _("Material cost line '%s' uses service product '%s'. Consider changing cost type to 'Labour' or use a storable/consumable product.") % (record.name, record.product_id.name)
                    })
                    
                elif record.cost_type == 'labour' and record.product_id.detailed_type not in ['service']:
                    validation_issues.append({
                        'type': 'labour_non_service', 
                        'message': _("Labour cost line '%s' uses non-service product '%s'. Consider changing cost type to 'Material' or use a service product.") % (record.name, record.product_id.name)
                    })
                
                # Handle validation issues
                for issue in validation_issues:
                    # Log warning for all cases
                    _logger.warning(issue['message'])
                    
                    # Only raise error if strict validation is enabled AND not in flexible contexts
                    strict_validation = getattr(self.env.company, 'job_costing_strict_product_validation', False)
                    flexible_context = self.env.context.get('flexible_product_validation', False)
                    
                    # More lenient - only error in very strict mode
                    if strict_validation and not flexible_context and not self.env.context.get('auto_cost_type_adjustment', False):
                        if issue['type'] == 'material_service':
                            raise ValidationError(_("Material cost lines should not use service products. Please change cost type to 'Labour' or select a storable/consumable product."))
                        elif issue['type'] == 'labour_non_service':
                            raise ValidationError(_("Labour cost lines should use service products. Please change cost type to 'Material' or select a service product."))
    
    def validate_product_for_cost_type(self, product_id, cost_type):
        """Helper method to validate if a product is suitable for a cost type"""
        if not product_id:
            return True, ""
            
        product = self.env['product.product'].browse(product_id)
        
        if cost_type == 'material' and product.detailed_type == 'service':
            return False, _("Service products are typically used for labour costs. Consider changing cost type to 'Labour' or use a storable/consumable product.")
        elif cost_type == 'labour' and product.detailed_type not in ['service']:
            return False, _("Non-service products are typically used for material costs. Consider changing cost type to 'Material' or use a service product.")
        
        return True, ""
    
    @api.onchange('product_id', 'cost_type')
    def _onchange_product_cost_type_validation(self):
        """Provide user-friendly warnings for product/cost type mismatches"""
        if self.product_id and self.cost_type:
            is_valid, message = self.validate_product_for_cost_type(self.product_id.id, self.cost_type)
            if not is_valid:
                return {
                    'warning': {
                        'title': _('Product Type Warning'),
                        'message': message
                    }
                }
    
    def action_edit_cost_line(self):
        """Action to open the cost line in form view for editing"""
        return {
            'name': 'Edit Job Cost Line',
            'type': 'ir.actions.act_window',
            'res_model': 'job.cost.line',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def update_actual_costs_from_purchases(self):
        """Method to manually update actual costs from purchase orders"""
        for record in self:
            if record.cost_type in ('material', 'labour', 'overhead'):
                # Get confirmed purchase order lines
                po_lines = record.purchase_order_line_ids.filtered(
                    lambda l: l.order_id.state in ['purchase', 'done']
                )
                if po_lines:
                    if record.cost_type == 'labour':
                        # Services have no goods-receipt step (qty_received is
                        # never populated by a stock picking), so a confirmed
                        # service PO line's cost is recognized in full - unlike
                        # material, there is no "partially received" milestone
                        # to scale against.
                        total_cost = sum(po_lines.mapped('price_subtotal'))
                        total_qty = sum(po_lines.mapped('product_qty'))
                    else:
                        # Scale cost to the received portion only - a confirmed
                        # PO line is a commitment, not an actual cost, until
                        # goods are received against it.
                        total_cost = sum(
                            line.price_subtotal * (line.qty_received / line.product_qty)
                            for line in po_lines if line.product_qty
                        )
                        total_qty = sum(po_lines.mapped('qty_received'))

                    # For labour, also add timesheet data
                    if record.cost_type == 'labour' and record.timesheet_ids:
                        total_cost += sum(abs(ts.amount) for ts in record.timesheet_ids if ts.amount)
                        total_qty += sum(record.timesheet_ids.mapped('unit_amount'))

                    record.actual_qty = total_qty
                    record.actual_unit_cost = total_cost / total_qty if total_qty else 0
                    record.actual_cost = total_cost
    
    def button_update_actual_costs(self):
        """Button action to update actual costs"""
        self.update_actual_costs_from_purchases()
        return True
    
    @api.model
    def get_or_create_cost_line(self, cost_sheet_id, product_id, cost_type='material', 
                                source_po_line_id=None, source_timesheet_id=None, 
                                source_invoice_line_id=None, vals=None):
        """
        Get existing cost line or create new one.
        Prevents duplicate cost lines by checking source tracking fields.
        
        FIX ISSUE #2: Duplicate Cost Lines Prevention
        """
        if vals is None:
            vals = {}
            
        domain = [('cost_sheet_id', '=', cost_sheet_id)]
        
        # Check by source fields first (most reliable)
        if source_po_line_id:
            existing = self.search([('source_po_line_id', '=', source_po_line_id)], limit=1)
            if existing:
                _logger.info(f"Found existing cost line {existing.id} for PO line {source_po_line_id}")
                return existing
                
        if source_timesheet_id:
            existing = self.search([('source_timesheet_id', '=', source_timesheet_id)], limit=1)
            if existing:
                _logger.info(f"Found existing cost line {existing.id} for timesheet {source_timesheet_id}")
                return existing
                
        if source_invoice_line_id:
            existing = self.search([('source_invoice_line_id', '=', source_invoice_line_id)], limit=1)
            if existing:
                _logger.info(f"Found existing cost line {existing.id} for invoice line {source_invoice_line_id}")
                return existing
        
        # Check by product if no source match. Also match on description when
        # given, so distinct BOQ items that share a product (e.g. several
        # differently-described doors under one service product) don't
        # collapse onto the same cost line.
        if product_id:
            domain.append(('product_id', '=', product_id))
            if vals.get('name'):
                domain.append(('name', '=', vals['name']))
            existing = self.search(domain, limit=1)
            if existing:
                _logger.info(f"Found existing cost line {existing.id} for product {product_id} in sheet {cost_sheet_id}")
                return existing
        
        # Create new cost line
        create_vals = {
            'cost_sheet_id': cost_sheet_id,
            'cost_type': cost_type,
            'product_id': product_id,
            'source_po_line_id': source_po_line_id,
            'source_timesheet_id': source_timesheet_id,
            'source_invoice_line_id': source_invoice_line_id,
        }
        create_vals.update(vals)
        
        # Set default name if not provided
        if not create_vals.get('name') and product_id:
            product = self.env['product.product'].browse(product_id)
            create_vals['name'] = product.name
            
        new_line = self.create(create_vals)
        _logger.info(f"Created new cost line {new_line.id} for sheet {cost_sheet_id}")
        return new_line
