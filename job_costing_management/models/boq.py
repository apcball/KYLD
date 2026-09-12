# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class BOQ(models.Model):
    _name = 'boq.boq'
    _description = 'Bill of Quantities (BOQ)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(string='BOQ Reference', required=True, copy=False, readonly=True,
                      default=lambda self: _('New'))
    
    # Relations
    project_id = fields.Many2one('project.project', string='Project', required=True, index=True)
    job_order_id = fields.Many2one('job.order', string='Job Order', index=True)
    job_cost_sheet_id = fields.Many2one('job.cost.sheet', string='Job Cost Sheet', index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, 
                                 default=lambda self: self.env.company, index=True)
    
    # BOQ Information
    title = fields.Char(string='BOQ Title', required=True)
    description = fields.Text(string='Description')
    boq_date = fields.Date(string='BOQ Date', default=fields.Date.today)
    revision = fields.Char(string='Revision', default='1.0')
    
    # State management
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('locked', 'Locked'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True, index=True)
    
    # BOQ Lines
    line_ids = fields.One2many('boq.line', 'boq_id', string='BOQ Lines')
    material_line_ids = fields.One2many(
        'boq.line', 'boq_id', string='Material Lines',
        domain=[('line_type', '=', 'material')])
    labour_line_ids = fields.One2many(
        'boq.line', 'boq_id', string='Labour Lines',
        domain=[('line_type', '=', 'labour')])
    
    # Categories
    category_ids = fields.One2many('boq.category', 'boq_id', string='Categories')
    
    # Totals
    total_quantity = fields.Float(string='Total Quantity', compute='_compute_totals', store=True)
    total_cost = fields.Float(string='Total Cost', compute='_compute_totals', store=True)
    
    # Purchase tracking totals
    total_requisitioned_amount = fields.Float(string='Total Requisitioned Amount', compute='_compute_purchase_totals', store=True)
    total_ordered_amount = fields.Float(string='Total Ordered Amount', compute='_compute_purchase_totals', store=True)
    total_received_amount = fields.Float(string='Total Received Amount', compute='_compute_purchase_totals', store=True)
    overall_purchase_progress = fields.Float(string='Overall Purchase Progress (%)', compute='_compute_purchase_totals', store=True)

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id and self.project_id.company_id:
            self.company_id = self.project_id.company_id
    
    # Smart buttons
    requisition_count = fields.Integer(string='Requisitions', compute='_compute_requisition_count')
    
    # Template relation
    template_id = fields.Many2one('boq.template', string='Created from Template')
    
    # Other fields
    prepared_by = fields.Many2one('res.users', string='Prepared by', default=lambda self: self.env.user)
    approved_by = fields.Many2one('res.users', string='Approved by')
    approved_date = fields.Date(string='Approved Date')
    
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self.env.company.currency_id)
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('boq.boq') or _('New')
        
        # Handle template creation
        template_id = vals.get('template_id') or self.env.context.get('default_template_id')
        if template_id:
            template = self.env['boq.template'].browse(template_id)
            if template.exists():
                vals['template_id'] = template_id
                # Set title and description from template if not provided
                if not vals.get('title'):
                    vals['title'] = template.name
                if not vals.get('description'):
                    vals['description'] = template.description
        
        result = super(BOQ, self).create(vals)
        
        # Create BOQ lines from template lines
        if template_id:
            template = self.env['boq.template'].browse(template_id)
            if template.exists():
                # Validate template has lines with products
                if not template.line_ids:
                    raise ValidationError(_('Template has no lines to copy.'))
                
                lines_without_products = template.line_ids.filtered(lambda l: not l.product_id)
                if lines_without_products:
                    raise ValidationError(_('Template has lines without products. Please ensure all template lines have products assigned.'))
                
                result._create_lines_from_template(template)
        
        return result
    
    def _create_lines_from_template(self, template):
        """Create BOQ lines from template lines"""
        BOQLine = self.env['boq.line']
        
        for template_line in template.line_ids:
            line_vals = {
                'boq_id': self.id,
                'sequence': template_line.sequence,
                'item_code': template_line.item_code,
                'product_id': template_line.product_id.id if template_line.product_id else False,
                'description': template_line.description,
                'specification': template_line.specification,
                'quantity': template_line.quantity,
                'uom_id': template_line.uom_id.id if template_line.uom_id else False,
                'unit_cost': template_line.unit_cost,
                'waste_percentage': template_line.waste_percentage,
                'contingency_percentage': template_line.contingency_percentage,
                'notes': template_line.notes,
            }
            
            # Validate that essential fields are present
            if not line_vals['description']:
                _logger.debug("Template line %s has no description, skipping", template_line.id)
                continue
                
            if not line_vals['uom_id']:
                _logger.debug("Template line %s has no UOM, skipping", template_line.id)
                continue
            
            BOQLine.create(line_vals)
    
    @api.depends('line_ids.quantity', 'line_ids.total_cost')
    def _compute_totals(self):
        for record in self:
            record.total_quantity = sum(record.line_ids.mapped('quantity'))
            record.total_cost = sum(record.line_ids.mapped('total_cost'))
    
    @api.depends('line_ids.total_requisitioned_qty', 'line_ids.total_ordered_qty', 'line_ids.total_received_qty', 'line_ids.unit_cost', 'line_ids.adjusted_total_cost')
    def _compute_purchase_totals(self):
        for record in self:
            # Calculate total amounts based on quantities and unit costs
            total_req_amount = 0
            total_ord_amount = 0
            total_rec_amount = 0
            total_boq_amount = sum(record.line_ids.mapped('adjusted_total_cost'))
            
            for line in record.line_ids:
                total_req_amount += line.total_requisitioned_qty * line.unit_cost
                total_ord_amount += line.total_ordered_qty * line.unit_cost
                total_rec_amount += line.total_received_qty * line.unit_cost
            
            record.total_requisitioned_amount = total_req_amount
            record.total_ordered_amount = total_ord_amount
            record.total_received_amount = total_rec_amount
            
            # Calculate overall progress
            if total_boq_amount > 0:
                record.overall_purchase_progress = (total_req_amount / total_boq_amount) * 100
            else:
                record.overall_purchase_progress = 0.0
    
    def _compute_requisition_count(self):
        for record in self:
            record.requisition_count = len(record.line_ids.mapped('requisition_line_ids.requisition_id'))
    
    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approved_date': fields.Date.today()
        })
        for boq in self:
            # Best-effort: approval must never fail because a BOQ has no
            # product lines yet, no cost sheet, or the approving user lacks
            # write access to that sheet - the manual button stays available
            # (and still raises) for whoever needs to sync it later.
            try:
                boq._sync_job_cost_lines(strict=False)
            except AccessError:
                pass
    
    def action_lock(self):
        self.write({'state': 'locked'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
    
    def action_duplicate(self):
        """Create a duplicate of this BOQ"""
        new_boq = self.copy()
        
        return {
            'name': 'Duplicate BOQ',
            'type': 'ir.actions.act_window',
            'res_model': 'boq.boq',
            'view_mode': 'form',
            'res_id': new_boq.id,
            'target': 'current',
        }
    
    def _check_requisition_context(self):
        self.ensure_one()
        self.check_access_rights('read')
        self.check_access_rule('read')
        if self.state not in ('approved', 'locked'):
            raise ValidationError(_('Approve or lock the BOQ before requesting materials.'))
        self._check_work_context()

    def _check_work_context(self):
        """Validate links explicitly; these legacy relations have no company checks."""
        self.ensure_one()
        if self.company_id not in self.env.companies:
            raise ValidationError(_('The BOQ company must be an allowed company.'))
        for record in (self.project_id, self.job_order_id, self.job_cost_sheet_id):
            if not record:
                continue
            record.check_access_rights('read')
            record.check_access_rule('read')
            if record.company_id and record.company_id != self.company_id:
                raise ValidationError(_('The project, job order and cost sheet must belong to the BOQ company.'))
        for record in (self.job_order_id, self.job_cost_sheet_id):
            if record and record.project_id != self.project_id:
                raise ValidationError(_('The job order and cost sheet must belong to the BOQ project.'))

    def _open_requisition_wizard(self, selected_lines=None):
        self._check_requisition_context()
        return {
            'name': _('Create Material Requisition'),
            'type': 'ir.actions.act_window',
            'res_model': 'boq.material.requisition.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': dict(
                self.env.context, default_boq_id=self.id,
                active_model=self._name, active_id=self.id,
                selected_boq_line_ids=selected_lines.ids if selected_lines else []),
        }

    def action_create_material_requisition(self):
        return self._open_requisition_wizard()

    def _create_material_requisition(self, lines, purpose, required_date, priority):
        """Single creation path for both header and line requests."""
        self._check_requisition_context()
        commands = []
        for line in lines:
            source = line.boq_line_id
            if source.boq_id != self:
                raise ValidationError(_('All selected lines must belong to this BOQ.'))
            if not source.product_id or not source.uom_id:
                raise ValidationError(_('Each selected line needs a product and unit of measure.'))
            if line.product_id != source.product_id or line.uom_id != source.uom_id:
                raise ValidationError(_('BOQ product or unit of measure changed. Reopen the request.'))
            if line.requested_quantity <= 0:
                raise ValidationError(_('Requested quantity must be greater than zero for all selected lines.'))
            cost_line = source._get_cost_line(self.job_cost_sheet_id)
            commands.append(fields.Command.create({
                'product_id': source.product_id.id,
                'description': line.description,
                'quantity': line.requested_quantity,
                'uom_id': source.uom_id.id,
                'estimated_cost': line.estimated_cost,
                'boq_line_id': source.id,
                'job_cost_line_id': cost_line.id,
            }))
        if not commands:
            raise ValidationError(_('Select at least one BOQ line to request.'))
        return self.env['material.requisition'].with_company(self.company_id).create({
            'project_id': self.project_id.id,
            'job_order_id': self.job_order_id.id,
            'job_cost_sheet_id': self.job_cost_sheet_id.id,
            'analytic_account_id': self.project_id.analytic_account_id.id,
            'company_id': self.company_id.id,
            'boq_id': self.id,
            'purpose': purpose,
            'required_date': required_date,
            'priority': priority,
            'state': 'draft',
            'line_ids': commands,
        })

    def action_create_job_cost_lines(self):
        """Create missing BOQ lines without modifying existing baselines."""
        self.ensure_one()
        created_count, result = self._sync_job_cost_lines(strict=True)
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {
                'title': _('BOQ Cost Lines'),
                'message': _('Created: %(created)s; already linked: %(existing)s.') % {
                    'created': created_count, 'existing': len(result) - created_count},
                'type': 'success', 'sticky': False,
                'next': {
                    'name': _('Job Cost Lines'), 'type': 'ir.actions.act_window',
                    'res_model': 'job.cost.line', 'view_mode': 'tree,form',
                    'views': [(False, 'tree'), (False, 'form')],
                    'domain': [('id', 'in', result.ids)],
                },
            },
        }

    def _sync_job_cost_lines(self, strict=True):
        """Create missing job cost lines from this BOQ's product lines.

        strict=True (manual "Create Job Cost Lines" button): raises so the
        user gets clear feedback when there's nothing to sync.
        strict=False (auto, on approve): skips quietly instead - approving a
        BOQ must never fail because it has no cost sheet yet, no product
        lines, or the approving user lacks write access to the sheet.
        """
        self.ensure_one()
        self.check_access_rights('read')
        self.check_access_rule('read')
        self._check_work_context()
        empty = (0, self.env['job.cost.line'])
        if not self.job_cost_sheet_id:
            if strict:
                raise ValidationError(_('Please specify a job cost sheet.'))
            return empty
        lines = self.line_ids.filtered('product_id')
        if not lines:
            if strict:
                raise ValidationError(_('No BOQ lines with products found to create job cost lines from.'))
            return empty
        # Update the sheet row to serialize concurrent create requests as well.
        self.job_cost_sheet_id.check_access_rights('write')
        self.job_cost_sheet_id.check_access_rule('write')
        self.job_cost_sheet_id.write({'write_date': fields.Datetime.now()})
        result = self.env['job.cost.line']
        created_count = 0
        for line in lines:
            cost_line = line._get_cost_line(self.job_cost_sheet_id)
            if not cost_line:
                cost_line = self.env['job.cost.line'].create({
                    'cost_sheet_id': self.job_cost_sheet_id.id,
                    'cost_type': 'labour' if line.product_id.detailed_type == 'service' else 'material',
                    'product_id': line.product_id.id,
                    'name': line.description,
                    'planned_qty': line.quantity,
                    'uom_id': line.uom_id.id,
                    'unit_cost': line.unit_cost,
                    'boq_line_id': line.id,
                    'boq_qty': line.quantity,
                    'boq_unit_cost': line.unit_cost,
                })
                created_count += 1
            result |= cost_line
        return created_count, result

    def action_view_requisitions(self):
        requisition_ids = self.line_ids.mapped('requisition_line_ids.requisition_id.id')
        
        return {
            'name': 'Material Requisitions',
            'type': 'ir.actions.act_window',
            'res_model': 'material.requisition',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', requisition_ids)],
        }
    
    def action_debug_wizard_access(self):
        """Debug method to check wizard access rights"""
        try:
            # Try to access the wizard model
            wizard_model = self.env['boq.material.requisition.wizard']
            
            # Check if user can create wizard records
            wizard_model.check_access_rights('create')
            wizard_model.check_access_rights('read')
            wizard_model.check_access_rights('write')
            
            # Get user groups
            user_groups = self.env.user.groups_id.mapped('name')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Wizard Access Check',
                    'message': f'✅ User has access to wizard. Groups: {", ".join(user_groups)}',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Wizard Access Error',
                    'message': f'❌ Access denied: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def check_requisition_readiness(self):
        """Check if BOQ is ready for material requisition creation"""
        issues = []
        
        if self.state not in ('approved', 'locked'):
            issues.append(f'BOQ state must be approved or locked (current: {self.state})')
        
        if not self.line_ids:
            issues.append('BOQ has no lines')
        
        lines_without_products = self.line_ids.filtered(lambda l: not l.product_id)
        if lines_without_products:
            issues.append(f'{len(lines_without_products)} BOQ lines have no products assigned')
        
        lines_with_products = self.line_ids.filtered(lambda l: l.product_id)
        lines_with_remaining = lines_with_products.filtered(lambda l: l.remaining_qty > 0)
        
        if not lines_with_remaining:
            if lines_with_products:
                issues.append('All BOQ lines with products have been fully requisitioned')
            else:
                issues.append('No BOQ lines have products assigned')
        
        return {
            'ready': len(issues) == 0,
            'issues': issues,
            'lines_total': len(self.line_ids),
            'lines_with_products': len(lines_with_products),
            'lines_with_remaining': len(lines_with_remaining),
        }
    
    def copy(self, default=None):
        """Override copy method to handle proper duplication of BOQ"""
        if default is None:
            default = {}
        
        # Generate new name for the copy
        if 'name' not in default:
            default['name'] = _('New')
        
        # Update title to indicate it's a copy
        if 'title' not in default:
            default['title'] = _("%s (Copy)") % self.title
        
        # Reset state and approval fields
        default.update({
            'state': 'draft',
            'approved_by': False,
            'approved_date': False,
            'template_id': False,  # Don't copy template reference
        })
        
        # Store original lines and categories
        original_lines = self.line_ids
        original_categories = self.category_ids
        
        # Copy the BOQ record using standard copy
        new_boq = super(BOQ, self).copy(default)
        
        # Clear any automatically copied lines that may not have copied properly
        if new_boq.line_ids:
            new_boq.line_ids.unlink()
        if new_boq.category_ids:
            new_boq.category_ids.unlink()
        
        # Copy categories first
        category_mapping = {}
        for category in original_categories:
            category_vals = {
                'boq_id': new_boq.id,
                'sequence': category.sequence,
                'name': category.name,
                'description': category.description,
            }
            new_category = self.env['boq.category'].create(category_vals)
            category_mapping[category.id] = new_category.id
        
        # Manually copy BOQ lines with proper field copying
        for line in original_lines:
            line_vals = {
                'boq_id': new_boq.id,
                'sequence': line.sequence,
                'category_id': category_mapping.get(line.category_id.id) if line.category_id else False,
                'item_code': line.item_code,
                'product_id': line.product_id.id if line.product_id else False,
                'description': line.description,
                'specification': line.specification,
                'quantity': line.quantity,
                'uom_id': line.uom_id.id if line.uom_id else False,
                'unit_cost': line.unit_cost,
                'waste_percentage': line.waste_percentage,
                'contingency_percentage': line.contingency_percentage,
                'notes': line.notes,
                # Reset status and don't copy relations
                'status': 'pending',
            }
            self.env['boq.line'].create(line_vals)
        
        return new_boq


class BOQCategory(models.Model):
    _name = 'boq.category'
    _description = 'BOQ Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    boq_id = fields.Many2one('boq.boq', string='BOQ', required=True, ondelete='cascade', index=True)
    description = fields.Text(string='Description')
    
    # Computed fields
    line_ids = fields.One2many('boq.line', 'category_id', string='BOQ Lines')
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)
    
    @api.depends('line_ids.total_cost')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = sum(record.line_ids.mapped('total_cost'))


class BOQLine(models.Model):
    _name = 'boq.line'
    _description = 'BOQ Line'
    _order = 'sequence, id'
    _rec_name = 'description'

    boq_id = fields.Many2one('boq.boq', string='BOQ', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', related='boq_id.company_id', string='Company', store=True, readonly=True)
    sequence = fields.Integer(string='Sequence', default=10)
    category_id = fields.Many2one('boq.category', string='Category', index=True)
    
    # Item information
    item_code = fields.Char(string='Item Code')
    product_id = fields.Many2one('product.product', string='Product', required=True, index=True)
    description = fields.Text(string='Description', required=True)
    specification = fields.Text(string='Specification')
    
    # Line type: auto-determined by product type
    line_type = fields.Selection([
        ('material', 'Material'),
        ('labour', 'Labour'),
    ], string='Type', compute='_compute_line_type', store=True)
    
    # Quantity and Unit
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    
    # Cost information
    unit_cost = fields.Float(string='Unit Cost', required=True)
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)
    
    # Waste and contingency
    waste_percentage = fields.Float(string='Waste %', default=0.0)
    contingency_percentage = fields.Float(string='Contingency %', default=0.0)
    
    # Adjusted quantities and costs
    adjusted_quantity = fields.Float(string='Adjusted Quantity', compute='_compute_adjusted_values', store=True)
    adjusted_total_cost = fields.Float(string='Adjusted Total Cost', compute='_compute_adjusted_values', store=True)
    
    # Relations
    requisition_line_ids = fields.One2many('material.requisition.line', 'boq_line_id', string='Requisition Lines')
    cost_line_ids = fields.One2many('job.cost.line', 'boq_line_id', string='Cost Lines')
    
    # Purchase tracking fields
    total_requisitioned_qty = fields.Float(string='Total Requisitioned Qty', compute='_compute_purchase_tracking', store=True)
    total_ordered_qty = fields.Float(string='Total Ordered Qty', compute='_compute_purchase_tracking', store=True)
    total_received_qty = fields.Float(string='Total Received Qty', compute='_compute_purchase_tracking', store=True)
    remaining_qty = fields.Float(string='Remaining Qty', compute='_compute_purchase_tracking', store=True)
    purchase_progress = fields.Float(string='Purchase Progress (%)', compute='_compute_purchase_tracking', store=True)
    
    # Status
    status = fields.Selection([
        ('pending', 'Pending'),
        ('requisitioned', 'Requisitioned'),
        ('ordered', 'Ordered'),
        ('received', 'Received'),
        ('completed', 'Completed')
    ], string='Status', default='pending', compute='_compute_status', store=True)
    
    # Notes
    notes = fields.Text(string='Notes')
    
    @api.depends('product_id', 'product_id.detailed_type')
    def _compute_line_type(self):
        for record in self:
            if record.product_id and record.product_id.detailed_type == 'service':
                record.line_type = 'labour'
            else:
                record.line_type = 'material'

    @api.depends('quantity', 'unit_cost')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = record.quantity * record.unit_cost
    
    @api.depends('requisition_line_ids', 'requisition_line_ids.quantity', 'requisition_line_ids.requisition_state')
    def _compute_purchase_tracking(self):
        """Compute purchase tracking fields.

        - total_requisitioned_qty: sum of active MR line quantities (unchanged).
        - total_ordered_qty: for purchase MR lines → actual PO line data;
                             for internal/service MR lines → MR state-based.
        - total_received_qty: for purchase MR lines → PO qty_received;
                              for internal/service MR lines → MR state-based.
        - remaining_qty: BOQ adjusted qty minus requisitioned qty.
        """
        POLine = self.env['purchase.order.line'].sudo()
        for record in self:
            # Get all requisition lines for this BOQ line
            req_lines = record.requisition_line_ids

            # Calculate total requisitioned quantity (all states except cancelled/rejected)
            active_req_lines = req_lines.filtered(
                lambda l: l.requisition_state not in ['cancelled', 'cancel', 'rejected'])
            record.total_requisitioned_qty = sum(active_req_lines.mapped('quantity'))

            # --- Split by requisition_action ---
            purchase_lines = active_req_lines.filtered(
                lambda l: l.requisition_action == 'purchase')
            internal_lines = active_req_lines.filtered(
                lambda l: l.requisition_action != 'purchase')

            # Purchase-type: derive from actual PO lines
            po_ordered = 0.0
            po_received = 0.0
            if purchase_lines:
                po_lines = POLine.search([
                    ('material_requisition_line_id', 'in', purchase_lines.ids),
                    ('order_id.state', 'in', ['purchase', 'done']),
                ])
                po_ordered = sum(po_lines.mapped('product_qty'))
                po_received = sum(po_lines.mapped('qty_received'))

            # Internal/service-type: use MR state as before
            int_ordered = sum(internal_lines.filtered(
                lambda l: l.requisition_state in ['approved', 'ordered', 'received']
            ).mapped('quantity'))
            int_received = sum(internal_lines.filtered(
                lambda l: l.requisition_state == 'received'
            ).mapped('quantity'))

            record.total_ordered_qty = po_ordered + int_ordered
            record.total_received_qty = po_received + int_received

            # Calculate remaining quantity
            record.remaining_qty = record.adjusted_quantity - record.total_requisitioned_qty

            # Calculate purchase progress percentage
            if record.adjusted_quantity > 0:
                record.purchase_progress = (record.total_requisitioned_qty / record.adjusted_quantity) * 100
            else:
                record.purchase_progress = 0.0
    
    @api.depends('quantity', 'waste_percentage', 'contingency_percentage', 'total_cost')
    def _compute_adjusted_values(self):
        for record in self:
            waste_factor = 1 + (record.waste_percentage / 100)
            contingency_factor = 1 + (record.contingency_percentage / 100)
            
            record.adjusted_quantity = record.quantity * waste_factor
            record.adjusted_total_cost = record.total_cost * waste_factor * contingency_factor
    
    @api.depends('requisition_line_ids.requisition_id.state', 'total_received_qty', 'adjusted_quantity')
    def _compute_status(self):
        for record in self:
            if not record.requisition_line_ids:
                record.status = 'pending'
            else:
                # Check if fully received
                if record.total_received_qty >= record.adjusted_quantity:
                    record.status = 'completed'
                elif record.total_received_qty > 0:
                    record.status = 'received'
                elif record.total_ordered_qty > 0:
                    record.status = 'ordered'
                elif record.total_requisitioned_qty > 0:
                    record.status = 'requisitioned'
                else:
                    record.status = 'pending'
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.name
            self.uom_id = self.product_id.uom_id
            self.unit_cost = self.product_id.standard_price
            self.item_code = self.product_id.default_code or ''
    
    def _get_cost_line(self, cost_sheet):
        self.ensure_one()
        if not cost_sheet:
            return self.env['job.cost.line']
        matches = self.env['job.cost.line'].search([
            ('boq_line_id', '=', self.id), ('cost_sheet_id', '=', cost_sheet.id),
        ])
        if len(matches) > 1:
            raise ValidationError(
                _('Multiple cost lines are linked to BOQ item %s. Resolve the duplicates first.')
                % self.description)
        return matches

    def action_create_requisition(self):
        self.ensure_one()
        if not self.product_id or self.remaining_qty <= 0:
            raise ValidationError(_('This BOQ line needs a product and a remaining quantity.'))
        return self.boq_id._open_requisition_wizard(self)
    
    def copy(self, default=None):
        """Override copy method to ensure proper copying of BOQ lines"""
        if default is None:
            default = {}
        
        # Ensure all relational fields are properly copied
        default.update({
            'requisition_line_ids': [],  # Don't copy requisition relations
            'cost_line_ids': [],  # Don't copy cost line relations
            'status': 'pending',  # Reset status
        })
        
        return super(BOQLine, self).copy(default)


class BOQTemplate(models.Model):
    _name = 'boq.template'
    _description = 'BOQ Template'
    _order = 'name'

    name = fields.Char(string='Template Name', required=True)
    description = fields.Text(string='Description')
    job_type_id = fields.Many2one('job.type', string='Job Type', index=True)
    
    # Template lines
    line_ids = fields.One2many('boq.template.line', 'template_id', string='Template Lines')
    
    # Computed fields
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)
    
    @api.depends('line_ids.total_cost')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = sum(record.line_ids.mapped('total_cost'))
    
    def action_create_boq(self):
        """Create BOQ from template"""
        ctx = self.env.context.copy()
        ctx.update({
            'default_template_id': self.id,
            'default_title': self.name,
            'default_description': self.description,
        })
        
        return {
            'name': 'Create BOQ from Template',
            'type': 'ir.actions.act_window',
            'res_model': 'boq.boq',
            'view_mode': 'form',
            'context': ctx,
        }
    
    def copy(self, default=None):
        """Override copy method to handle proper duplication of BOQ Template"""
        if default is None:
            default = {}
        
        # Update name to indicate it's a copy
        if 'name' not in default:
            default['name'] = _("%s (Copy)") % self.name
        
        # Copy the template record
        new_template = super(BOQTemplate, self).copy(default)
        
        # Clear any automatically copied lines that may not have copied properly
        if new_template.line_ids:
            new_template.line_ids.unlink()
        
        # Manually copy template lines with proper field copying
        for line in self.line_ids:
            line_vals = {
                'template_id': new_template.id,
                'sequence': line.sequence,
                'item_code': line.item_code,
                'product_id': line.product_id.id if line.product_id else False,
                'description': line.description,
                'specification': line.specification,
                'quantity': line.quantity,
                'uom_id': line.uom_id.id if line.uom_id else False,
                'unit_cost': line.unit_cost,
                'waste_percentage': line.waste_percentage,
                'contingency_percentage': line.contingency_percentage,
                'notes': line.notes,
            }
            self.env['boq.template.line'].create(line_vals)
        
        return new_template


class BOQTemplateLine(models.Model):
    _name = 'boq.template.line'
    _description = 'BOQ Template Line'
    _order = 'sequence, id'

    template_id = fields.Many2one('boq.template', string='Template', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    # Item information
    item_code = fields.Char(string='Item Code')
    product_id = fields.Many2one('product.product', string='Product', required=True, index=True)
    description = fields.Text(string='Description', required=True)
    specification = fields.Text(string='Specification')
    
    # Quantity and Unit
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    
    # Cost information
    unit_cost = fields.Float(string='Unit Cost', required=True)
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)
    
    # Waste and contingency
    waste_percentage = fields.Float(string='Waste %', default=0.0)
    contingency_percentage = fields.Float(string='Contingency %', default=0.0)
    
    # Notes
    notes = fields.Text(string='Notes')
    
    @api.depends('quantity', 'unit_cost')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = record.quantity * record.unit_cost
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.name
            self.uom_id = self.product_id.uom_id
            self.unit_cost = self.product_id.standard_price
            self.item_code = self.product_id.default_code or ''
    
    def copy(self, default=None):
        """Override copy method to ensure proper copying of BOQ template lines"""
        if default is None:
            default = {}
        
        # Ensure all fields are properly copied
        return super(BOQTemplateLine, self).copy(default)
