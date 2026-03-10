from odoo import models, fields, api

class StockMove(models.Model):
    _inherit = 'stock.move'

    analytic_distribution = fields.Json(
        string='Analytic Distribution',
        compute='_compute_analytic_distribution',
        store=True,
        readonly=False,
        copy=True,
    )

    analytic_precision = fields.Integer(
        string="Analytic Precision",
        compute='_compute_analytic_precision',
    )

    def _compute_analytic_precision(self):
        precision = self.env['decimal.precision'].precision_get('Percentage Analytic')
        for move in self:
            move.analytic_precision = precision

    @api.depends('sale_line_id.analytic_distribution', 'purchase_line_id.analytic_distribution')
    def _compute_analytic_distribution(self):
        for move in self:
            if move.analytic_distribution:
                continue
            distribution = False
            if move.sale_line_id:
                distribution = move.sale_line_id.analytic_distribution
            elif move.purchase_line_id:
                distribution = move.purchase_line_id.analytic_distribution
            
            move.analytic_distribution = distribution

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('analytic_distribution'):
                distribution = False
                if vals.get('sale_line_id'):
                    sale_line = self.env['sale.order.line'].browse(vals['sale_line_id'])
                    distribution = sale_line.analytic_distribution
                elif vals.get('purchase_line_id'):
                    purchase_line = self.env['purchase.order.line'].browse(vals['purchase_line_id'])
                    distribution = purchase_line.analytic_distribution
                
                if distribution:
                    vals['analytic_distribution'] = distribution
        return super().create(vals_list)
