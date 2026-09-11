# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.float_utils import float_compare


class BOQMaterialRequisitionWizard(models.TransientModel):
    _name = 'boq.material.requisition.wizard'
    _description = 'BOQ Material Requisition Wizard'

    boq_id = fields.Many2one('boq.boq', string='BOQ', required=True)
    project_id = fields.Many2one(related='boq_id.project_id', readonly=True)
    job_order_id = fields.Many2one(related='boq_id.job_order_id', readonly=True)
    job_cost_sheet_id = fields.Many2one(related='boq_id.job_cost_sheet_id', readonly=True)
    currency_id = fields.Many2one(related='boq_id.currency_id', readonly=True)
    purpose = fields.Text(string='Purpose/Reason', required=True)
    required_date = fields.Date(required=True, default=fields.Date.context_today)
    priority = fields.Selection([
        ('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent'),
    ], default='normal', required=True)
    requisition_id = fields.Many2one('material.requisition', readonly=True, copy=False)
    line_ids = fields.One2many(
        'boq.material.requisition.wizard.line', 'wizard_id', string='Requisition Lines')

    # Retain the former two-step interface for inherited views and callers.
    display_in_wizard = fields.Boolean(default=True)
    wizard_state = fields.Selection([
        ('select', 'Select Materials'), ('configure', 'Configure Quantities'),
    ], default='configure', required=True)
    boq_line_selection_ids = fields.Many2many('boq.line', string='Select BOQ Lines')
    total_lines_count = fields.Integer(string='Selected Items', compute='_compute_statistics')
    selected_total_quantity = fields.Float(compute='_compute_statistics')
    selected_total_cost = fields.Monetary(
        string='Total Estimated Cost', compute='_compute_statistics')

    @api.depends('line_ids.selected', 'line_ids.requested_quantity', 'line_ids.total_cost')
    def _compute_statistics(self):
        for wizard in self:
            selected = wizard.line_ids.filtered('selected')
            wizard.total_lines_count = len(selected)
            wizard.selected_total_quantity = sum(selected.mapped('requested_quantity'))
            wizard.selected_total_cost = sum(selected.mapped('total_cost'))

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        boq_id = values.get('boq_id') or self.env.context.get('default_boq_id')
        if not boq_id and self.env.context.get('active_model') == 'boq.boq':
            boq_id = self.env.context.get('active_id')
        if boq_id:
            boq = self.env['boq.boq'].browse(boq_id).exists()
            if not boq:
                raise ValidationError(_('The selected BOQ no longer exists.'))
            boq._check_requisition_context()
            available = boq.line_ids.filtered(lambda line: line.remaining_qty > 0)
            if not available:
                raise ValidationError(_('No BOQ lines have remaining quantities to request.'))
            selected_ids = self.env.context.get('selected_boq_line_ids', [])
            if 'boq_id' in fields_list:
                values['boq_id'] = boq.id
            if 'purpose' in fields_list:
                values['purpose'] = _('Material requisition from BOQ: %s') % boq.name
            if 'line_ids' in fields_list:
                values['line_ids'] = [fields.Command.create({
                    'boq_line_id': line.id,
                    'selected': line.id in selected_ids,
                    'product_id': line.product_id.id,
                    'description': line.description,
                    'uom_id': line.uom_id.id,
                    'estimated_cost': line.unit_cost,
                    'category_id': line.category_id.id,
                    'product_category_id': line.product_id.categ_id.id,
                    'boq_quantity': line.adjusted_quantity,
                    'requisitioned_quantity': line.total_requisitioned_qty,
                    'remaining_quantity': line.remaining_qty,
                    'requested_quantity': line.remaining_qty,
                }) for line in available]
        return values

    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': self._name,
            'res_id': self.id, 'view_mode': 'form', 'target': 'new',
        }

    def action_process_selection(self):
        """Compatibility entry point: deselected rows cannot remain selected."""
        self.ensure_one()
        for line in self.line_ids:
            line.selected = line.boq_line_id in self.boq_line_selection_ids
        self.wizard_state = 'configure'
        return self._reopen()

    def action_go_back_to_selection(self):
        return self._reopen()

    def _open_requisition(self):
        self.requisition_id.check_access_rights('read')
        self.requisition_id.check_access_rule('read')
        return {
            'name': _('Material Requisition'), 'type': 'ir.actions.act_window',
            'res_model': 'material.requisition', 'res_id': self.requisition_id.id,
            'view_mode': 'form', 'target': 'current',
        }

    def action_create_requisition(self):
        self.ensure_one()
        self.check_access_rights('write')
        self.check_access_rule('write')
        if not self.env.su and self.create_uid != self.env.user:
            raise AccessError(_('Only the user who opened this request can confirm it.'))
        # Serialize double-clicks; the second request opens the saved draft.
        self.env.cr.execute(
            'SELECT id FROM boq_material_requisition_wizard WHERE id = %s FOR UPDATE',
            [self.id])
        self.invalidate_recordset(['requisition_id'])
        if self.requisition_id:
            return self._open_requisition()
        self.boq_id._check_requisition_context()
        selected = self.line_ids.filtered('selected')
        if not selected:
            raise ValidationError(_('Select at least one BOQ line to request.'))
        if any(line.boq_line_id.boq_id != self.boq_id for line in selected):
            raise ValidationError(_('All selected lines must belong to this BOQ.'))
        if len(selected.boq_line_id) != len(selected):
            raise ValidationError(_('Select each BOQ line only once.'))

        # Re-read tracking rather than trusting values captured on opening.
        boq_lines = selected.boq_line_id
        boq_lines.invalidate_recordset(['requisition_line_ids'])
        boq_lines._compute_purchase_tracking()
        changed = False
        for line in selected:
            source = line.boq_line_id
            if float_compare(line.remaining_quantity, source.remaining_qty,
                             precision_rounding=source.uom_id.rounding or 0.01):
                line.write({
                    'boq_quantity': source.adjusted_quantity,
                    'requisitioned_quantity': source.total_requisitioned_qty,
                    'remaining_quantity': source.remaining_qty,
                })
                changed = True
        if changed:
            return {
                'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {
                    'title': _('Remaining quantities changed'),
                    'message': _('Review the updated quantities, then create the requisition again.'),
                    'type': 'warning', 'sticky': True, 'next': self._reopen(),
                },
            }
        self.requisition_id = self.boq_id._create_material_requisition(
            selected, self.purpose, self.required_date, self.priority)
        return self._open_requisition()


class BOQMaterialRequisitionWizardLine(models.TransientModel):
    _name = 'boq.material.requisition.wizard.line'
    _description = 'BOQ Material Requisition Wizard Line'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'boq.material.requisition.wizard', required=True, ondelete='cascade')
    selected = fields.Boolean(string='Select', default=False)
    sequence = fields.Integer(default=10)
    boq_line_id = fields.Many2one('boq.line', required=True)
    product_id = fields.Many2one('product.product', string='Product')
    description = fields.Text(required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    estimated_cost = fields.Float(string='Estimated Unit Cost')
    category_id = fields.Many2one('boq.category', string='BOQ Category')
    product_category_id = fields.Many2one('product.category')
    boq_quantity = fields.Float(string='BOQ Quantity', readonly=True)
    requisitioned_quantity = fields.Float(string='Already Requisitioned', readonly=True)
    remaining_quantity = fields.Float(string='Remaining Quantity', readonly=True)
    requested_quantity = fields.Float(string='Requested Quantity', required=True)
    currency_id = fields.Many2one(related='wizard_id.currency_id')
    total_cost = fields.Monetary(string='Total Cost', compute='_compute_total_cost')
    quantity_status = fields.Selection([
        ('within', 'Within BOQ'), ('exceed', 'Exceeds BOQ'),
        ('complete', 'Fully Requisitioned'),
    ], string='Status', compute='_compute_quantity_status')
    has_warning = fields.Boolean(compute='_compute_quantity_status')

    @api.depends('requested_quantity', 'estimated_cost')
    def _compute_total_cost(self):
        for line in self:
            line.total_cost = line.requested_quantity * line.estimated_cost

    @api.depends('requested_quantity', 'remaining_quantity')
    def _compute_quantity_status(self):
        for line in self:
            line.has_warning = line.requested_quantity > line.remaining_quantity
            line.quantity_status = ('exceed' if line.has_warning else
                                    'complete' if line.remaining_quantity <= 0 else 'within')

    @api.onchange('selected', 'requested_quantity')
    def _onchange_requested_quantity(self):
        if self.selected and self.requested_quantity > self.remaining_quantity:
            return {'warning': {
                'title': _('BOQ Quantity Exceeded'),
                'message': _('The requested quantity exceeds the remaining BOQ quantity. You can still proceed if needed.'),
            }}
