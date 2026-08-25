# -*- coding: utf-8 -*-
from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    buz_dashboard_cache_backend = fields.Selection([
        ('db', 'Database'),
        ('none', 'Disabled'),
    ], string='Dashboard Cache Backend', default='db',
        config_parameter='buz_dashboard.cache_backend')
    buz_dashboard_cache_ttl = fields.Integer(
        string='Dashboard Cache TTL (seconds)', default=60,
        config_parameter='buz_dashboard.cache_ttl')
    buz_dashboard_threshold_warning = fields.Float(
        string='Cost Progress Warning Threshold (%)', default=90.0,
        config_parameter='buz_dashboard.threshold_warning')
    buz_dashboard_threshold_critical = fields.Float(
        string='Cost Progress Critical Threshold (%)', default=100.0,
        config_parameter='buz_dashboard.threshold_critical')
    buz_dashboard_cors_origins = fields.Char(
        string='Allowed CORS Origins (comma-separated)',
        config_parameter='buz_dashboard.cors_origins',
        help="e.g. https://dashboard.mogen.co.th,https://tv.mogen.co.th. "
             "Leave empty to disable cross-origin requests.")
