from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    analytic_account_ids = fields.Many2many(
        comodel_name='account.analytic.account',
        string='Analytic',
        compute='_compute_analytic_account_ids',
        store=True,
        readonly=True,
    )

    @api.depends('order_line', 'order_line.display_type', 'order_line.analytic_distribution')
    def _compute_analytic_account_ids(self):
        analytic_account_model = self.env['account.analytic.account']
        for order in self:
            analytic_account_ids = set()
            for line in order.order_line.filtered(lambda line: not line.display_type):
                for distribution_key in (line.analytic_distribution or {}):
                    for analytic_account_id in str(distribution_key).split(','):
                        analytic_account_id = analytic_account_id.strip()
                        if analytic_account_id.isdigit():
                            analytic_account_ids.add(int(analytic_account_id))

            order.analytic_account_ids = analytic_account_model.browse(
                sorted(analytic_account_ids)
            ).exists()
