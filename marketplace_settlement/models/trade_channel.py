from odoo import models, fields, api

class MarketplaceTradeChannel(models.Model):
    _name = 'marketplace.trade.channel'
    _description = 'Marketplace Trade Channel'
    _order = 'sequence, name'

    name = fields.Char('Channel Name', required=True, translate=True)
    code = fields.Char('Code', required=True, help='Unique internal code for the channel (e.g. shopee, lazada)')
    active = fields.Boolean('Active', default=True)
    sequence = fields.Integer('Sequence', default=10)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'The channel code must be unique!')
    ]
