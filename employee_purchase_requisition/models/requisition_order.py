from odoo import api, fields, models

class RequisitionOrder(models.Model):
    _name = 'requisition.order'
    _description = 'Requisition Order'

    requisition_product_id = fields.Many2one(  # ใช้ชื่อเดียวกับที่อ้างอิงใน One2many
        'employee.purchase.requisition',
        string='Requisition Reference',
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        domain="[('product_tmpl_id.can_be_expensed', '=', False)]"
    )
    description = fields.Text(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0)
    product_uom_category_id = fields.Many2one(
        'uom.category',
        related='product_id.uom_id.category_id',
        string='Product UOM Category',
        store=True,
        readonly=True
    )
    uom = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
        domain="[('category_id', '=', product_uom_category_id)]"
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor'
    )
    analytic_distribution = fields.Json(
        string="Analytic Distribution",
        copy=True,
        store=True,
        default={}
    )
    analytic_precision = fields.Integer(
        string="Analytic Precision",
        default=lambda self: self.env['decimal.precision'].precision_get('Percentage Analytic')
    )
    
    unit_price = fields.Float(
        string="Unit Price",
        help="Enter the custom unit price for this product"
    )
    price_subtotal = fields.Float(
        string="Subtotal",
        compute="_compute_price_subtotal",
        store=True,
        help="Automatically calculated as quantity × unit price"
    )
    remark = fields.Text(
        string="Remark",
        help="Additional notes or remarks for this requisition line"
    )

    select_for_rfq = fields.Boolean(string='Select for RFQ', default=False, copy=False)
    rfq_qty = fields.Float(
        string='RFQ Opened', compute='_compute_rfq_tracking',
        help='Quantity already placed on non-cancelled Purchase Orders (RFQs).'
    )
    rfq_remaining_qty = fields.Float(
        string='RFQ Remaining', compute='_compute_rfq_tracking',
        help='Quantity not yet placed on any Purchase Order (RFQ).'
    )

    def _compute_rfq_tracking(self):
        POLine = self.env['purchase.order.line'].sudo()
        for line in self:
            if not line.id:
                line.rfq_qty = 0.0
                line.rfq_remaining_qty = line.quantity
                continue
            po_lines = POLine.search([
                ('requisition_order_line_id', '=', line.id),
                ('order_id.state', '!=', 'cancel'),
            ])
            rfq_qty = sum(po_lines.mapped('product_qty'))
            line.rfq_qty = rfq_qty
            line.rfq_remaining_qty = max(line.quantity - rfq_qty, 0.0)

    @api.depends('quantity', 'unit_price')
    def _compute_price_subtotal(self):
        """Calculate subtotal for each line item"""
        for line in self:
            line.price_subtotal = line.quantity * line.unit_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.name
            self.uom = self.product_id.uom_id.id
