# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    advance_box_id = fields.Many2one(
        'employee.advance.box',
        string='Default Advance Box',
        help='Default advance box for this employee. Will be auto-filled in expense reports.'
    )
