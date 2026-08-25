# -*- coding: utf-8 -*-
{
    'name': 'buz Dashboard Engine',
    'version': '17.0.1.0.0',
    'category': 'Project',
    'summary': 'Dashboard API / Engine for external Job Costing dashboards (React/Next.js)',
    'description': """
buz Dashboard Engine
=====================

Read-only JSON API layer over Job Costing data (materials, labour, overheads,
profitability, variance, trends) for external frontends. Does not build a
dashboard UI inside Odoo.

Layers
------
* Controllers: thin JSON routing only
* Services: KPI/aggregation business logic, one per business domain
* Models: dashboard configuration, cache store

Extension
---------
New business domains (sales, purchase, stock, accounting) are added as new
service classes registered in the service registry, without touching the
controller layer.
    """,
    'author': 'Apichart Pangsalung',
    'website': 'https://www.mogen.co.th',
    'depends': [
        'base',
        'project',
        'job_costing_management',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/dashboard_data.xml',
        'views/dashboard_views.xml',
        'views/dashboard_widget_views.xml',
        'views/res_config_settings_views.xml',
        'views/dashboard_menu.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
