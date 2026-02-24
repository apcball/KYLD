{
    'name': 'Stock Analytic Connector',
    'version': '17.0.1.0.0',
    'category': 'Inventory/Inventory',
    'summary': 'Pass Analytic Distribution from SO/PO to Stock Moves',
    'description': """
        This module ensures that the Analytic Distribution defined on Sales Order Lines
        and Purchase Order Lines is carried over to the resulting Stock Moves and Pickings.
    """,
    'author': 'KYLD',
    'depends': ['sale_stock', 'purchase_stock', 'analytic'],
    'data': [
        'views/stock_move_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'AGPL-3',
}
