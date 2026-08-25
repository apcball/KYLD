# -*- coding: utf-8 -*-
import json

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class DashboardWidget(models.Model):
    _name = 'buz.dashboard.widget'
    _description = 'Dashboard Widget'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    dashboard_id = fields.Many2one('buz.dashboard', required=True, ondelete='cascade', index=True)
    widget_type = fields.Selection([
        ('kpi', 'KPI'),
        ('chart', 'Chart'),
        ('table', 'Table'),
        ('ranking', 'Ranking'),
        ('gauge', 'Gauge'),
        ('progress', 'Progress'),
        ('heatmap', 'Heatmap'),
        ('timeline', 'Timeline'),
        ('custom', 'Custom'),
    ], required=True, default='kpi')
    endpoint = fields.Char(help="API endpoint code that feeds this widget, e.g. 'job_costing.overview'")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    config_json = fields.Text(help="Widget-specific configuration as JSON")

    _sql_constraints = [
        ('dashboard_code_uniq', 'unique(dashboard_id, code)',
         'Widget code must be unique within a dashboard.'),
    ]

    @api.constrains('config_json')
    def _check_config_json(self):
        for record in self:
            if record.config_json:
                try:
                    json.loads(record.config_json)
                except ValueError as exc:
                    raise ValidationError(
                        _("Widget configuration must be valid JSON: %s") % exc) from exc
