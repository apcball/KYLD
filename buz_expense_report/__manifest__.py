# -*- coding: utf-8 -*-
{
    'name': 'Buz Expense Report',
    'version': '17.0.1.0.0',
    'category': 'Human Resources/Expenses',
    'summary': 'Custom PDF Expense Report with Multi-Company support',
    'description': """
        This module provides a custom PDF expense report layout matching a specific grid format.
        It supports multi-company by dynamically showing the company logo and name in the header.
    """,
    'author': 'KYLD',
    'website': '',
    'depends': ['hr_expense'],
    'data': [
        'report/expense_report_action.xml',
        'report/expense_report_template.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'buz_expense_report/static/src/css/fonts.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'AGPL-3',
}
