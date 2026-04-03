# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MaterialRequisition(models.Model):
    _name = 'material.requisition'
    _description = 'Material Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(string='Requisition Number', required=True, copy=False, readonly=True,
                      default=lambda self: _('New'))
    
    # Relations
    project_id = fields.Many2one('project.project', string='Project', required=True)
    job_order_id = fields.Many2one('job.order', string='Job Order')
    job_cost_sheet_id = fields.Many2one('job.cost.sheet', string='Job Cost Sheet')  # Add job cost sheet link
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    boq_id = fields.Many2one('boq.boq', string='BOQ Reference')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    company_currency_id = fields.Many2one('res.currency', string='Company Currency', related='company_id.currency_id', readonly=True, store=True)
    employee_id = fields.Many2one('hr.employee', string='Requested by', 
                                 default=lambda self: self.env.user.employee_id)
    department_id = fields.Many2one('hr.department', string='Department',
                                   related='employee_id.department_id', store=True)
    
    # State management
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('dept_approved', 'Department Approved'),
        ('approved', 'Approved'),
        ('ordered', 'Ordered'),
        ('received', 'Received'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    # Dates
    request_date = fields.Date(string='Request Date', default=fields.Date.today)
    requisition_date = fields.Date(string='Requisition Date', default=fields.Date.today)
    required_date = fields.Date(string='Required Date', required=True)
    approved_date = fields.Date(string='Approved Date')
    
    # Requisition lines
    line_ids = fields.One2many('material.requisition.line', 'requisition_id', string='Requisition Lines')
    
    # Approval workflow
    dept_manager_id = fields.Many2one('res.users', string='Department Manager')
    requisition_manager_id = fields.Many2one('res.users', string='Requisition Manager')
    dept_approval_date = fields.Date(string='Department Approval Date')
    
    # Other fields
    purpose = fields.Text(string='Purpose/Reason')
    delivery_to = fields.Many2one('stock.picking.type', string='Delivery To')
    notes = fields.Text(string='Notes')
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string='Priority', default='normal')
    
    # Procurement Pool
    is_pooled = fields.Boolean(
        string='In Procurement Pool', compute='_compute_is_pooled', store=True)
    
    # Smart buttons
    purchase_order_count = fields.Integer(string='Purchase Orders', compute='_compute_purchase_order_count')
    picking_count = fields.Integer(string='Pickings', compute='_compute_picking_count')
    pool_count = fields.Integer(string='Procurement Pools', compute='_compute_pool_count')
    
    # Total cost computation
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_amount', store=True)
    
    @api.depends('line_ids.pool_line_ids')
    def _compute_is_pooled(self):
        for record in self:
            record.is_pooled = any(line.pool_line_ids for line in record.line_ids)

    def _compute_pool_count(self):
        for record in self:
            pool_ids = record.line_ids.mapped('pool_line_ids.pool_id').ids
            record.pool_count = len(set(pool_ids))

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            self.analytic_account_id = self.project_id.analytic_account_id
            if self.project_id.company_id:
                self.company_id = self.project_id.company_id
                
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('material.requisition') or _('New')
        result = super(MaterialRequisition, self).create(vals)
        return result
    
    def _compute_purchase_order_count(self):
        for record in self:
            # Since we don't have direct linking, we can search for POs by origin
            purchase_orders = self.env['purchase.order'].search([('origin', '=', record.name)])
            record.purchase_order_count = len(purchase_orders)
    
    def _compute_picking_count(self):
        for record in self:
            # Get all picking IDs from requisition lines
            picking_ids = record.line_ids.mapped('picking_ids.id')
            # Also search for pickings by origin
            pickings_by_origin = self.env['stock.picking'].search([('origin', '=', record.name)])
            picking_ids.extend(pickings_by_origin.ids)
            # Remove duplicates
            picking_ids = list(set(picking_ids))
            
            record.picking_count = len(picking_ids)
    
    @api.depends('line_ids.total_cost')
    def _compute_total_amount(self):
        """Compute total amount from requisition lines"""
        for record in self:
            record.total_cost = sum(record.line_ids.mapped('total_cost'))
    
    def action_submit(self):
        if not self.line_ids:
            raise ValidationError(_('Please add at least one requisition line.'))
        self.write({'state': 'submitted'})
    
    def action_dept_approve(self):
        self.write({
            'state': 'dept_approved',
            'dept_approval_date': fields.Date.today(),
            'dept_manager_id': self.env.user.id
        })
    
    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_date': fields.Date.today(),
            'requisition_manager_id': self.env.user.id
        })
    
    def action_reject(self):
        self.write({'state': 'rejected'})
    
    def action_cancel(self):
        for record in self:
            # Check for related pickings that are not in cancel/draft/done state
            # We allow 'done' state to support returns: User returns stock -> Cancels PO -> Cancels MR
            picking_ids = record.line_ids.mapped('picking_ids.id')
            pickings_by_origin = self.env['stock.picking'].search([('origin', '=', record.name)])
            picking_ids.extend(pickings_by_origin.ids)
            picking_ids = list(set(picking_ids))
            
            if picking_ids:
                pickings = self.env['stock.picking'].browse(picking_ids)
                # content: We allow done pickings because user might have returned them.
                # We only block active movements.
                non_cancellable_pickings = pickings.filtered(
                    lambda p: p.state not in ['draft', 'cancel', 'done']
                )
                if non_cancellable_pickings:
                    raise ValidationError(_(
                        'Cannot cancel this requisition because the following internal transfers are in progress (not done/cancelled):\n%s'
                    ) % '\n'.join(['- %s (%s)' % (p.name, p.state) for p in non_cancellable_pickings]))
                # Cancel related draft pickings
                pickings.filtered(lambda p: p.state == 'draft').action_cancel()
            
            # Check for related purchase orders
            # We attempt to cancel any draft POs, but we DO NOT block if POs are confirmed/done.
            # This allows the "Return Goods -> Cancel MR" workflow even if Odoo prevents PO cancellation.
            if record.state == 'ordered':
                purchase_orders = self.env['purchase.order'].search([('origin', '=', record.name)])
                if purchase_orders:
                    # Cancel related draft POs
                    purchase_orders.filtered(lambda po: po.state == 'draft').button_cancel()
                    
                    # Log a note if there are confirmed POs
                    confirmed_pos = purchase_orders.filtered(lambda po: po.state not in ['draft', 'cancel'])
                    if confirmed_pos:
                        msg = _('Material Requisition cancelled. Linked Purchase Orders remain active: %s') % ', '.join(confirmed_pos.mapped('name'))
                        record.message_post(body=msg)
            
            record.write({'state': 'cancelled'})
            
            # IMPORTANT: Trigger recalculation of Job Cost Line active costs
            # Find all related Job Cost Lines through BOQ lines
            boq_lines = record.line_ids.mapped('boq_line_id')
            if boq_lines:
                cost_lines = boq_lines.mapped('cost_line_ids')
                if cost_lines:
                    # Force recomputation of active planned qty and active total cost
                    cost_lines._compute_active_planned_qty()
                    cost_lines._compute_active_total_cost()
                    
                    # Also recompute the Job Cost Sheet totals
                    cost_sheets = cost_lines.mapped('cost_sheet_id')
                    if cost_sheets:
                        cost_sheets._compute_active_totals()
    
    def action_reset_to_draft(self):
        for record in self:
            # Check for related purchase orders that are not cancelled
            purchase_orders = self.env['purchase.order'].search([('origin', '=', record.name)])
            non_draft_pos = purchase_orders.filtered(lambda po: po.state not in ['draft', 'cancel'])
            if non_draft_pos:
                raise ValidationError(_(
                    'Cannot reset to draft because the following purchase orders are already confirmed:\n%s'
                ) % '\n'.join(['- %s (%s)' % (po.name, po.state) for po in non_draft_pos]))
            
            # Check for related pickings that are not in cancel/draft state
            picking_ids = record.line_ids.mapped('picking_ids.id')
            pickings_by_origin = self.env['stock.picking'].search([('origin', '=', record.name)])
            picking_ids.extend(pickings_by_origin.ids)
            picking_ids = list(set(picking_ids))
            
            if picking_ids:
                pickings = self.env['stock.picking'].browse(picking_ids)
                non_draft_pickings = pickings.filtered(lambda p: p.state not in ['draft', 'cancel'])
                if non_draft_pickings:
                    raise ValidationError(_(
                        'Cannot reset to draft because the following internal transfers are already in progress:\n%s'
                    ) % '\n'.join(['- %s (%s)' % (p.name, p.state) for p in non_draft_pickings]))
            
            record.write({'state': 'draft'})
    
    def action_create_purchase_order(self):
        # Check if there are any purchase lines
        purchase_lines = self.line_ids.filtered(lambda l: l.requisition_action == 'purchase' and l.vendor_id)
        if not purchase_lines:
            raise ValidationError(_('No purchase lines found with vendors assigned.'))
        
        # Group lines by vendor
        vendor_lines = {}
        for line in purchase_lines:
            if line.vendor_id not in vendor_lines:
                vendor_lines[line.vendor_id] = []
            vendor_lines[line.vendor_id].append(line)
        
        purchase_orders = []
        for vendor, lines in vendor_lines.items():
            po_vals = {
                'partner_id': vendor.id,
                'origin': self.name,
                'material_requisition_id': self.id,  # Link to material requisition
                'job_cost_sheet_id': self.job_cost_sheet_id.id if self.job_cost_sheet_id else False,  # Pass job cost sheet
                'employee_id': self.employee_id.id if self.employee_id else False,
                'department_id': self.department_id.id if self.department_id else False,
                'dept_id': self.department_id.id if self.department_id else False,
                'order_line': []
            }
            if self.delivery_to:
                po_vals['picking_type_id'] = self.delivery_to.id
            
            for line in lines:
                po_line_vals = {
                    'product_id': line.product_id.id,
                    'name': line.description,
                    'product_qty': line.quantity,
                    'product_uom': line.uom_id.id,
                    'price_unit': line.estimated_cost,
                    'material_requisition_line_id': line.id,  # Link to requisition line
                    'job_cost_sheet_id': self.job_cost_sheet_id.id if self.job_cost_sheet_id else False,  # Pass job cost sheet
                    'job_cost_line_id': line.job_cost_line_id.id if line.job_cost_line_id else False,  # Pass job cost line
                    'analytic_distribution': line.analytic_distribution,
                }
                po_vals['order_line'].append((0, 0, po_line_vals))
            
            if po_vals['order_line']:
                try:
                    po = self.env['purchase.order'].create(po_vals)
                    purchase_orders.append(po.id)
                except Exception as e:
                    raise ValidationError(_('Error creating purchase order for vendor %s: %s') % (vendor.name, str(e)))
        
        if purchase_orders:
            self.write({'state': 'ordered'})
            
            # Use our custom purchase order view to avoid approval_state errors
            tree_view = self.env.ref('job_costing_management.view_purchase_order_tree_job_costing', False)
            
            return {
                'name': 'Purchase Orders',
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_mode': 'tree,form',
                'views': [(tree_view.id if tree_view else False, 'tree'), (False, 'form')],
                'domain': [('id', 'in', purchase_orders)],
                'context': {'res_model': 'purchase.order'},
            }
    
    def action_create_picking(self):
        internal_lines = self.line_ids.filtered(lambda l: l.requisition_action == 'internal')
        if not internal_lines:
            raise ValidationError(_('No internal transfer lines found.'))
        
        company = self.company_id or self.env.company
        
        # Get destination location
        dest_location = None
        if hasattr(self.employee_id, 'dest_location_id') and self.employee_id.dest_location_id:
            dest_location = self.employee_id.dest_location_id.id
        elif hasattr(self.department_id, 'dest_location_id') and self.department_id.dest_location_id:
            dest_location = self.department_id.dest_location_id.id
        else:
            # Default to warehouse stock location for this company
            warehouse = self.env['stock.warehouse'].sudo().search([('company_id', '=', company.id)], limit=1)
            if warehouse and warehouse.lot_stock_id:
                dest_location = warehouse.lot_stock_id.id
            else:
                locations = self.env['stock.location'].sudo().search([('usage', '=', 'internal'), ('company_id', 'in', [company.id, False])], limit=1)
                if locations:
                    dest_location = locations[0].id
                else:
                    raise ValidationError(_('No destination location found for company %s. Please configure a destination location for the employee or department.') % company.name)
        
        # Get source location
        warehouse = self.env['stock.warehouse'].sudo().search([('company_id', '=', company.id)], limit=1)
        if warehouse and warehouse.lot_stock_id:
            source_location = warehouse.lot_stock_id.id
        else:
            locations = self.env['stock.location'].sudo().search([('usage', '=', 'internal'), ('company_id', 'in', [company.id, False])], limit=1)
            if locations:
                source_location = locations[0].id
            else:
                raise ValidationError(_('No source location found for company %s.') % company.name)
        
        # Get internal picking type for the correct company (multi-company safe)
        picking_type_rec = self.env['stock.picking.type'].sudo().search([
            ('code', '=', 'internal'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not picking_type_rec:
            raise ValidationError(_('No internal picking type found for company %s.') % company.name)
        picking_type = picking_type_rec.id
        
        # Create internal transfer
        picking_vals = {
            'picking_type_id': picking_type,
            'location_id': source_location,
            'location_dest_id': dest_location,
            'origin': self.name,
            'move_ids': []
        }
        
        for line in internal_lines:
            move_vals = {
                'name': line.description,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.uom_id.id,
                'location_id': source_location,
                'location_dest_id': dest_location,
                # Don't set material_requisition_line_id as it doesn't exist in stock.move
            }
            picking_vals['move_ids'].append((0, 0, move_vals))
        
        if picking_vals['move_ids']:
            picking = self.env['stock.picking'].sudo().create(picking_vals)
            
            # Link the picking to the requisition lines
            for line in internal_lines:
                line.sudo().write({'picking_ids': [(4, picking.id)]})
            
            picking.sudo().action_confirm()
            picking.sudo().action_assign()
            
            self.write({'state': 'ordered'})
            
            # Return action to show the created picking
            return {
                'name': _('Internal Transfer'),
                'type': 'ir.actions.act_window',
                'res_model': 'stock.picking',
                'res_id': picking.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            raise ValidationError(_('No move lines created for internal transfer.'))
    
    def action_received(self):
        self.write({'state': 'received'})

    def action_add_to_pool(self):
        """Open wizard to add approved MR lines to a procurement pool."""
        self.ensure_one()
        if self.state != 'approved':
            raise ValidationError(_('Only approved MRs can be added to a procurement pool.'))

        purchase_lines = self.line_ids.filtered(
            lambda l: l.requisition_action == 'purchase' and not l.pool_line_ids)
        if not purchase_lines:
            raise ValidationError(
                _('No purchase lines available to add to pool. '
                  'Lines may already be in a pool.'))

        return {
            'name': _('Add to Procurement Pool'),
            'type': 'ir.actions.act_window',
            'res_model': 'add.to.pool.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_requisition_id': self.id,
                'default_mr_line_ids': [(6, 0, purchase_lines.ids)],
            },
        }

    def action_view_pools(self):
        """Smart button action to view related procurement pools."""
        pool_ids = self.line_ids.mapped('pool_line_ids.pool_id').ids
        return {
            'name': _('Procurement Pools'),
            'type': 'ir.actions.act_window',
            'res_model': 'procurement.pool',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', list(set(pool_ids)))],
        }
    
    def action_view_purchase_orders(self):
        # Search for purchase orders by origin since we don't have direct linking
        purchase_orders = self.env['purchase.order'].search([('origin', '=', self.name)])
        po_ids = purchase_orders.ids
        
        # Use standard purchase order views
        return {
            'name': 'Purchase Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', po_ids)],
            'context': {'res_model': 'purchase.order'},
        }
    
    def action_view_pickings(self):
        # Get all picking IDs from requisition lines
        picking_ids = self.line_ids.mapped('picking_ids.id')
        # Also search for pickings by origin
        pickings_by_origin = self.env['stock.picking'].search([('origin', '=', self.name)])
        picking_ids.extend(pickings_by_origin.ids)
        # Remove duplicates
        picking_ids = list(set(picking_ids))
        
        return {
            'name': 'Internal Transfers',
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', picking_ids)],
            'context': {'default_picking_type_code': 'internal'},
        }


class MaterialRequisitionLine(models.Model):
    _name = 'material.requisition.line'
    _description = 'Material Requisition Line'
    _order = 'sequence, id'

    requisition_id = fields.Many2one('material.requisition', string='Requisition', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', related='requisition_id.company_id', string='Company', store=True, readonly=True)
    company_currency_id = fields.Many2one('res.currency', string='Company Currency', related='company_id.currency_id', readonly=True, store=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    # Product information
    product_id = fields.Many2one('product.product', string='Product', required=True)
    description = fields.Char(string='Description', required=True)
    quantity = fields.Float(string='Quantity', default=1.0, required=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    analytic_distribution = fields.Json(string='Analytic Distribution')
    analytic_precision = fields.Integer(store=False, default=2)
    
    # Cost information
    estimated_cost = fields.Float(string='Estimated Unit Cost')
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)
    
    # Requisition action
    requisition_action = fields.Selection([
        ('purchase', 'Purchase Order'),
        ('internal', 'Internal Picking')
    ], string='Requisition Action', default='purchase', required=True)
    
    # Vendor information (for purchase)
    vendor_id = fields.Many2one('res.partner', string='Vendor',
                               domain=[('is_company', '=', True), ('supplier_rank', '>', 0)])
    
    # Relations
    # purchase_order_line_ids = fields.One2many('purchase.order.line', 'material_requisition_line_id', 
    #                                          string='Purchase Order Lines')
    picking_ids = fields.Many2many('stock.picking', string='Pickings')
    boq_line_id = fields.Many2one('boq.line', string='BOQ Line')
    job_cost_line_id = fields.Many2one('job.cost.line', string='Job Cost Line')  # Add job cost line link
    
    # Related fields for easier access
    requisition_state = fields.Selection(related='requisition_id.state', string='Requisition State', readonly=True)
    
    # BOQ tracking fields
    boq_remaining_qty = fields.Float(string='BOQ Remaining Qty', related='boq_line_id.remaining_qty', readonly=True)
    boq_total_qty = fields.Float(string='BOQ Total Qty', related='boq_line_id.adjusted_quantity', readonly=True)
    boq_requisitioned_qty = fields.Float(string='BOQ Requisitioned Qty', related='boq_line_id.total_requisitioned_qty', readonly=True)
    
    # Procurement Pool
    pool_line_ids = fields.Many2many(
        'procurement.pool.line',
        'procurement_pool_mr_line_rel',
        'mr_line_id', 'pool_line_id',
        string='Pool Lines')
    is_pooled = fields.Boolean(
        string='In Pool', compute='_compute_is_pooled', store=True)
    allocated_qty = fields.Float(
        string='Allocated Qty', compute='_compute_allocated_qty')
    
    # Notes
    notes = fields.Text(string='Notes')
    
    @api.depends('pool_line_ids')
    def _compute_is_pooled(self):
        for record in self:
            record.is_pooled = bool(record.pool_line_ids)
    
    def _compute_allocated_qty(self):
        Allocation = self.env['purchase.allocation']
        for record in self:
            allocations = Allocation.search([
                ('mr_line_id', '=', record.id)])
            record.allocated_qty = sum(allocations.mapped('qty'))
    
    @api.depends('quantity', 'estimated_cost')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = record.quantity * record.estimated_cost
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.name
            self.uom_id = self.product_id.uom_id
            self.estimated_cost = self.product_id.standard_price
            
            # Get preferred vendor
            seller = self.product_id.seller_ids[:1]
            if seller:
                self.vendor_id = seller.partner_id
                self.estimated_cost = seller.price
    
    @api.onchange('quantity', 'boq_line_id')
    def _onchange_quantity_boq_check(self):
        """Check quantity against BOQ remaining quantity and show warning"""
        if self.boq_line_id and self.quantity:
            remaining_qty = self.boq_line_id.remaining_qty
            
            if self.quantity > remaining_qty:
                # Show warning but don't prevent the action
                warning_msg = _(
                    'Warning: Requisition quantity (%s %s) exceeds remaining BOQ quantity (%s %s).\n'
                    'BOQ Total: %s %s\n'
                    'Already Requisitioned: %s %s\n'
                    'Remaining: %s %s\n\n'
                    'You can still proceed with this requisition if needed.'
                ) % (
                    self.quantity, self.uom_id.name or '',
                    remaining_qty, self.boq_line_id.uom_id.name,
                    self.boq_line_id.adjusted_quantity, self.boq_line_id.uom_id.name,
                    self.boq_line_id.total_requisitioned_qty, self.boq_line_id.uom_id.name,
                    remaining_qty, self.boq_line_id.uom_id.name
                )
                
                return {
                    'warning': {
                        'title': _('BOQ Quantity Exceeded'),
                        'message': warning_msg
                    }
                }
    
    @api.onchange('requisition_action')
    def _onchange_requisition_action(self):
        if self.requisition_action == 'internal':
            self.vendor_id = False
