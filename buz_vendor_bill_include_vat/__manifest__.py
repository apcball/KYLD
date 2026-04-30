{
    'name': 'Buz Vendor Bill Include VAT',
    'summary': 'Include VAT in vendor bill price instead of separate tax lines',
    'description': """
This module allows users to include VAT in the price of vendor bills instead of having separate tax lines.
For companies that cannot claim VAT as input tax, this feature merges VAT into the product cost.
    """,
    'version': '17.0.2.0.0',
    'category': 'Accounting & Finance',
    'author': 'Buz',
    'depends': [
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/account_move_views.xml',
    ],
    'tests': [
        'tests/test_vat_inclusion.py',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
