from odoo import models, fields, api

class StockMove(models.Model):
    _inherit = 'stock.move'

    custom_analytic_account_names = fields.Char(
        string='Analytic Account Names',
        compute='_compute_custom_analytic_account_names',
        store=True,
    )

    # Using _compute method without @api.depends for purchase_line_id / sale_line_id 
    # to avoid KeyError if the bridge modules (purchase_stock, sale_stock) aren't installed.
    # We can depend on picking_id or move_line_ids as a fallback.
    @api.depends('analytic_distribution')
    def _compute_custom_analytic_account_names(self):
        for move in self:
            names = []
            distribution = move.analytic_distribution
            if distribution:
                # distribution is a dict like {'1': 100.0, '2': 50.0} where keys are analytic account IDs (as strings)
                account_ids = []
                for key in distribution.keys():
                    # Handle composite keys like '1,2' by splitting
                    for subkey in str(key).split(','):
                        if subkey.isdigit():
                            account_ids.append(int(subkey))
                if account_ids:
                    accounts = self.env['account.analytic.account'].browse(account_ids)
                    names = [acc.name for acc in accounts if acc.exists()]
            
            move.custom_analytic_account_names = ', '.join(names) if names else ''
