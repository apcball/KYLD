from collections import defaultdict

from odoo import api, fields, models, _
from odoo.osv import expression


class JobCostSheet(models.Model):
    _inherit = 'job.cost.sheet'

    service_po_line_ids = fields.Many2many(
        'purchase.order.line', compute='_compute_service_po', string='Service PO Lines')
    service_po_currency_id = fields.Many2one(
        'res.currency', compute='_compute_service_po', string='Service PO Currency')
    service_po_ordered_total = fields.Monetary(
        compute='_compute_service_po', currency_field='service_po_currency_id',
        string='Service PO Ordered Total')
    service_po_warning = fields.Text(compute='_compute_service_po')

    def _get_service_po_values(self):
        """Read purchase commitments without changing budget or source links."""
        self.ensure_one()
        self.check_access_rights('read')
        self.check_access_rule('read')
        currency = self.currency_id or self.company_id.currency_id
        if not self.id:
            return self.env['purchase.order.line'], {}, currency
        # Allocation membership takes precedence even when the allocation is
        # hidden by a record rule: never fall back to charging the whole PO.
        direct = expression.OR([
            [('job_cost_sheet_id', '=', self.id)],
            [('job_cost_sheet_id', '=', False),
             ('job_cost_line_id.cost_sheet_id', '=', self.id)],
            [('job_cost_sheet_id', '=', False), ('job_cost_line_id', '=', False),
             ('order_id.job_cost_sheet_id', '=', self.id)],
        ])
        membership = expression.OR([
            [('allocation_ids.job_cost_sheet_id', '=', self.id)],
            expression.AND([[('allocation_ids', '=', False)], direct]),
        ])
        lines = self.env['purchase.order.line'].search(expression.AND([
            [('company_id', '=', self.company_id.id),
             ('order_id.state', 'in', ['purchase', 'done']),
             ('display_type', '=', False),
             ('product_id.detailed_type', '=', 'service')], membership,
        ]), order='order_id, sequence, id')
        allocations = self.env['purchase.allocation'].search([
            ('po_line_id', 'in', lines.ids), ('job_cost_sheet_id', '=', self.id),
            ('company_id', '=', self.company_id.id),
        ])
        allocated = defaultdict(float)
        for allocation in allocations:
            allocated[allocation.po_line_id.id] += allocation.qty
        # Search respects allocation rules; the domain above prevents hidden
        # allocations from turning into unallocated full-value commitments.
        direct_ids = set(self.env['purchase.order.line'].search([
            ('id', 'in', lines.ids), ('allocation_ids', '=', False),
        ]).ids)
        values = {}
        for line in lines:
            if line.id not in direct_ids and line.id not in allocated:
                continue
            qty = allocated.get(line.id, line.product_qty)
            invalid = line.id in allocated and line.product_qty == 0
            amount = (line.price_subtotal * qty / line.product_qty
                      if line.id in allocated and not invalid else line.price_subtotal)
            if invalid:
                amount = 0.0
            amount = line.currency_id.round(amount)
            converted = line.currency_id._convert(
                amount, currency, self.company_id,
                fields.Date.to_date(line.order_id.date_order))
            values[line.id] = (qty, amount, converted, invalid)
        return lines.filtered(lambda line: line.id in values), values, currency

    @api.depends('company_id', 'currency_id')
    @api.depends_context('uid', 'company')
    def _compute_service_po(self):
        for sheet in self:
            lines, values, currency = sheet._get_service_po_values()
            sheet.service_po_line_ids = lines
            sheet.service_po_currency_id = currency
            sheet.service_po_ordered_total = sum(value[2] for value in values.values())
            invalid = lines.filtered(lambda line: values[line.id][3])
            sheet.service_po_warning = (
                _('Total is incomplete: allocated PO lines have zero ordered quantity: %s')
                % ', '.join('%s / %s' % (line.order_id.name, line.sequence) for line in invalid)
                if invalid else False)


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    service_jcs_qty = fields.Float(
        string='Sheet Quantity', compute='_compute_service_jcs', digits='Product Unit of Measure')
    service_jcs_subtotal = fields.Monetary(
        string='Sheet Subtotal (PO Currency)', compute='_compute_service_jcs')
    service_jcs_currency_id = fields.Many2one('res.currency', compute='_compute_service_jcs')
    service_jcs_amount = fields.Monetary(
        string='Sheet Ordered Amount', compute='_compute_service_jcs',
        currency_field='service_jcs_currency_id')
    service_jcs_invalid = fields.Boolean(compute='_compute_service_jcs')

    @api.depends_context('service_job_cost_sheet_id', 'uid', 'company')
    @api.depends('product_qty', 'price_subtotal', 'currency_id', 'order_id.date_order',
                 'order_id.state', 'allocation_ids.qty', 'allocation_ids.job_cost_sheet_id',
                 'job_cost_sheet_id', 'job_cost_line_id', 'order_id.job_cost_sheet_id')
    def _compute_service_jcs(self):
        sheet_id = self.env.context.get('service_job_cost_sheet_id')
        sheet = self.env['job.cost.sheet'].browse(sheet_id).exists() if sheet_id else False
        values, currency = {}, self.env['res.currency']
        if sheet:
            _lines, values, currency = sheet._get_service_po_values()
        for line in self:
            qty, amount, converted, invalid = values.get(line.id, (0.0, 0.0, 0.0, False))
            line.service_jcs_qty = qty
            line.service_jcs_subtotal = amount
            line.service_jcs_currency_id = currency
            line.service_jcs_amount = converted
            line.service_jcs_invalid = invalid

    def _get_service_allocation_sheet(self):
        """Single job cost sheet this service PO line unambiguously belongs to, or empty."""
        self.ensure_one()
        if self.allocation_ids:
            sheets = self.allocation_ids.mapped('job_cost_sheet_id')
            return sheets if len(sheets) == 1 else self.env['job.cost.sheet']
        return (self.job_cost_sheet_id or self.job_cost_line_id.cost_sheet_id
                or self.order_id.job_cost_sheet_id)

    def _auto_link_labour_cost_line(self):
        """Link confirmed service PO lines to a labour job.cost.line so the
        existing actual-cost engine picks them up. Only when the line resolves
        to exactly one job cost sheet; budget/planned totals are untouched.
        Never touches a job_cost_line_id this method didn't create itself
        (tracked via source_po_line_id), so manual links are left alone."""
        for line in self:
            if line.display_type:
                continue
            if (line.product_id.detailed_type != 'service'
                    or line.order_id.state not in ('purchase', 'done')):
                continue
            if line.job_cost_line_id and line.job_cost_line_id.source_po_line_id != line:
                continue  # manually linked elsewhere; not ours to touch
            sheet = line._get_service_allocation_sheet()
            if line.job_cost_line_id and line.job_cost_line_id.cost_sheet_id == sheet:
                continue  # already correctly linked
            if line.job_cost_line_id:
                line.job_cost_line_id = False  # allocation moved/split; became stale
            if not sheet:
                continue
            cost_line = self.env['job.cost.line'].sudo().get_or_create_cost_line(
                cost_sheet_id=sheet.id, product_id=line.product_id.id, cost_type='labour',
                source_po_line_id=line.id, vals={'name': line.name})
            line.job_cost_line_id = cost_line.id
            cost_line.update_actual_costs_from_purchases()

    def action_open_service_po(self):
        self.ensure_one()
        self.check_access_rights('read')
        self.check_access_rule('read')
        self.order_id.check_access_rights('read')
        self.order_id.check_access_rule('read')
        return {
            'type': 'ir.actions.act_window', 'name': _('Purchase Order'),
            'res_model': 'purchase.order', 'res_id': self.order_id.id,
            'view_mode': 'form', 'target': 'current',
        }
