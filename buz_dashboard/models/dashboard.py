# -*- coding: utf-8 -*-
from odoo import models, fields, api


class Dashboard(models.Model):
    _name = 'buz.dashboard'
    _description = 'Dashboard Configuration'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    sequence = fields.Integer(default=10)
    description = fields.Text()
    widget_ids = fields.One2many('buz.dashboard.widget', 'dashboard_id', string='Widgets')
    widget_count = fields.Integer(compute='_compute_widget_count')

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'Dashboard code must be unique per company.'),
    ]

    @api.depends('widget_ids')
    def _compute_widget_count(self):
        for record in self:
            record.widget_count = len(record.widget_ids)
