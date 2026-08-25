# -*- coding: utf-8 -*-
from odoo import models, fields, api


class DashboardCache(models.Model):
    _name = 'buz.dashboard.cache'
    _description = 'Dashboard API Cache Entry'
    _rec_name = 'key'

    key = fields.Char(required=True, index=True)
    payload = fields.Text(required=True)
    company_id = fields.Many2one('res.company', required=True, index=True,
                                  default=lambda self: self.env.company)
    expires_at = fields.Datetime(required=True, index=True)

    _sql_constraints = [
        ('key_uniq', 'unique(key)', 'A cache entry with this key already exists.'),
    ]

    @api.autovacuum
    def _gc_expired(self):
        self.sudo().search([('expires_at', '<', fields.Datetime.now())]).unlink()
