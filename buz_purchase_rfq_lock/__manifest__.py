{
    'name': 'RFQ Lock Control',
    'version': '17.0.1.0.0',
    'category': 'Purchases',
    'summary': 'Restrict manual RFQ creation',
    'description': """
        This module restricts manual RFQ (Request for Quotation) creation.
        RFQs must only be created from explicit allowed processes (PR, MR, Auto Procurement)
        or by system administrators.
    """,
    'author': 'KYLD',
    'depends': ['purchase'],
    'data': [
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'AGPL-3',
}
