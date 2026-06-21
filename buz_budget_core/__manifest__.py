# -*- coding: utf-8 -*-
{
    'name': 'Budget Core Transaction Ledger',
    'version': '17.0.1.0.3',
    'category': 'Accounting/Budget',
    'summary': 'Event-sourced budget transaction ledger replacing derived budget.move',
    'description': """
Budget Core — Transaction Ledger
================================

Replaces the derived/rebuild-on-change budget.move model with an
event-sourced transaction ledger that tracks one record per demand
line (MR/PR/direct-PO) through its lifecycle:

    reserved → committed → used → released

Key advantages over budget.move:
- No delete-rebuild on every document change (eliminates deadlocks)
- Retroactive allocation resolution (pending state catches up when plan confirmed)
- Department and date fixed at creation (no drift)
- Partial billing tracked natively (committed decreases, used increases)
- Pool consolidation handled via lineage links (no double-count)
""",
    'author': 'Mogen Co., Ltd.',
    'website': 'https://www.mogen.co.th',
    'license': 'LGPL-3',
    'depends': [
        'biz_weekly_budget',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/budget_transaction_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init',
}
