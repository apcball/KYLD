{
    'name': 'Purchase Order Analytic Filter',
    'version': '17.0.1.0.0',
    'category': 'Purchase',
    'summary': 'Display and search analytic accounts on purchase orders',
    'depends': ['purchase', 'analytic'],
    'data': [
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
