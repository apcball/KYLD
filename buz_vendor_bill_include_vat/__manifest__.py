{
    'name': 'Include VAT in Price',
    'version': '17.0.1.0.0',
    'category': 'Accounting',
    'summary': 'Remove VAT from Bill Lines and include it in the price unit',
    'description': 'Adds a button on Vendor Bills to move VAT amount into the product price.',
    'author': 'Gemini',
    'depends': ['account'],
    'data': [
        'views/account_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'AGPL-3',
}