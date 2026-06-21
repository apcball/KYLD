# -*- coding: utf-8 -*-
"""Shared migration logic: budget.move → budget.transaction.

Called from both the post_init_hook (first install) and the migration
script (future upgrades).
"""
import logging

from odoo import SUPERUSER_ID, api, fields

_logger = logging.getLogger(__name__)


def run_migration(env):
    """Convert budget.move records into budget.transaction records."""
    Transaction = env['budget.transaction']
    Move = env['budget.move']

    existing = Transaction.search_count([])
    if existing > 0:
        _logger.info(
            'budget.transaction already has %d records — skipping migration',
            existing,
        )
        return

    moves = Move.search([])
    if not moves:
        _logger.info('No budget.move records to migrate.')
        return

    _logger.info('Migrating %d budget.move records to budget.transaction...',
                 len(moves))

    groups = {}
    for move in moves:
        demand = _find_demand(env, move)
        if not demand:
            _logger.warning(
                'Skipping orphaned move %s (source %s/%s no longer exists)',
                move.id, move.source_model, move.source_id,
            )
            continue

        key = (demand['origin_type'], demand['source_line_model'],
               demand['source_line_id'])
        if key not in groups:
            groups[key] = {
                **demand,
                'reserved': 0.0,
                'committed': 0.0,
                'used': 0.0,
                'po_line_id': False,
                'bill_line_ids': set(),
            }

        g = groups[key]
        if move.move_type == 'reserved':
            if move.source_model == 'purchase.order':
                g['committed'] += move.amount
            else:
                g['reserved'] += move.amount
        elif move.move_type == 'used':
            g['used'] += move.amount

        if move.source_model == 'purchase.order' and not g['po_line_id']:
            g['po_line_id'] = move.source_line_id
        if move.source_model == 'account.move':
            g['bill_line_ids'].add(move.source_line_id)

    created = 0
    for key, g in groups.items():
        active = g['reserved'] + g['committed'] + g['used']
        state = 'closed' if active <= 0 else 'pending'

        vals = {
            'origin_type': g['origin_type'],
            'source_line_model': g['source_line_model'],
            'source_line_id': g['source_line_id'],
            'source_doc_model': g.get('source_doc_model'),
            'source_doc_id': g.get('source_doc_id') or False,
            'source_doc_name': g.get('source_doc_name'),
            'raw_date': g['raw_date'],
            'raw_dept_id': g['raw_dept_id'],
            'raw_company_id': g['raw_company_id'],
            'product_id': g['product_id'],
            'analytic_account_id': g['analytic_account_id'],
            'reserved_amount': g['reserved'],
            'committed_amount': g['committed'],
            'used_amount': g['used'],
            'released_amount': 0.0,
            'state': state,
        }
        if g.get('po_line_id'):
            po_line = env['purchase.order.line'].browse(g['po_line_id'])
            if po_line.exists():
                vals['po_line_id'] = po_line.id

        try:
            tx = Transaction.create(vals)
            created += 1
            if g['bill_line_ids']:
                existing_amls = env['account.move.line'].browse(
                    list(g['bill_line_ids'])).exists()
                if existing_amls:
                    tx.bill_line_ids = [
                        fields.Command.link(a.id) for a in existing_amls
                    ]
        except Exception as e:
            _logger.error(
                'Failed to create transaction for %s/%s: %s',
                g['source_line_model'], g['source_line_id'], e,
            )

    try:
        Transaction.search(
            [('state', '=', 'pending')]
        )._resolve_allocation()
    except Exception as e:
        _logger.error('Allocation resolution failed during migration: %s', e)

    _logger.info(
        'Migration complete: %d budget.transaction records created '
        'from %d budget.move records (grouped into %d demand lines).',
        created, len(moves), len(groups),
    )


def _find_demand(env, move):
    """Trace a budget.move back to its demand line."""
    POLine = env['purchase.order.line'].sudo()
    AML = env['account.move.line'].sudo()
    MRLine = env['material.requisition.line'].sudo()
    ReqOrder = env['requisition.order'].sudo()

    def _mr_demand(mr_line, source_doc_id, source_doc_name):
        req = mr_line.requisition_id
        return {
            'origin_type': 'mr_line',
            'source_line_model': 'material.requisition.line',
            'source_line_id': mr_line.id,
            'source_doc_model': 'material.requisition',
            'source_doc_id': source_doc_id,
            'source_doc_name': source_doc_name or (req.name if req else ''),
            'raw_date': move.date,
            'raw_dept_id': (
                req.department_id.id
                if req and getattr(req, 'department_id', False) else False
            ),
            'raw_company_id': (
                move.company_id.id if move.company_id else (
                    req.company_id.id if req and req.company_id else False
                )
            ),
            'product_id': mr_line.product_id.id if mr_line.product_id else False,
            'analytic_account_id': (
                mr_line.analytic_account_id.id
                if mr_line.analytic_account_id else False
            ),
        }

    def _pr_demand(ro_line, source_doc_id, source_doc_name):
        pr = ro_line.requisition_product_id
        return {
            'origin_type': 'pr_line',
            'source_line_model': 'requisition.order',
            'source_line_id': ro_line.id,
            'source_doc_model': 'employee.purchase.requisition',
            'source_doc_id': source_doc_id,
            'source_doc_name': source_doc_name or (pr.name if pr else ''),
            'raw_date': move.date,
            'raw_dept_id': (
                pr.department_id.id
                if pr and getattr(pr, 'department_id', False) else False
            ),
            'raw_company_id': (
                pr.company_id.id if pr and pr.company_id else False
            ),
            'product_id': ro_line.product_id.id if ro_line.product_id else False,
            'analytic_account_id': False,
        }

    def _po_demand(po_line, source_doc_id, source_doc_name):
        po = po_line.order_id
        return {
            'origin_type': 'direct_po',
            'source_line_model': 'purchase.order.line',
            'source_line_id': po_line.id,
            'source_doc_model': 'purchase.order',
            'source_doc_id': source_doc_id,
            'source_doc_name': source_doc_name or (po.name if po else ''),
            'raw_date': move.date,
            'raw_dept_id': (
                po_line.department_id.id if po_line.department_id else (
                    po.department_id.id
                    if getattr(po, 'department_id', False) else False
                )
            ),
            'raw_company_id': po.company_id.id if po and po.company_id else False,
            'product_id': po_line.product_id.id if po_line.product_id else False,
            'analytic_account_id': False,
        }

    if move.source_model == 'material.requisition':
        mr_line = MRLine.browse(move.source_line_id)
        if not mr_line.exists():
            return None
        return _mr_demand(mr_line, move.source_id, move.name)

    if move.source_model == 'employee.purchase.requisition':
        ro_line = ReqOrder.browse(move.source_line_id)
        if not ro_line.exists():
            return None
        return _pr_demand(ro_line, move.source_id, move.name)

    if move.source_model == 'purchase.order':
        po_line = POLine.browse(move.source_line_id)
        if not po_line.exists():
            return None
        mr_line = po_line.material_requisition_line_id
        if mr_line and mr_line.exists():
            return _mr_demand(mr_line, po_line.order_id.id, move.name)
        return _po_demand(po_line, move.source_id, move.name)

    if move.source_model == 'account.move':
        aml = AML.browse(move.source_line_id)
        if not aml.exists():
            return None
        po_line = getattr(aml, 'purchase_line_id', False)
        if po_line and po_line.exists():
            mr_line = po_line.material_requisition_line_id
            if mr_line and mr_line.exists():
                return _mr_demand(mr_line, aml.move_id.id, move.name)
            return _po_demand(po_line, aml.move_id.id, move.name)
        return {
            'origin_type': 'direct_po',
            'source_line_model': 'account.move.line',
            'source_line_id': aml.id,
            'source_doc_model': 'account.move',
            'source_doc_id': aml.move_id.id if aml.move_id else move.source_id,
            'source_doc_name': move.name,
            'raw_date': move.date,
            'raw_dept_id': (
                aml.move_id.department_id.id
                if getattr(aml.move_id, 'department_id', False) else False
            ),
            'raw_company_id': (
                aml.move_id.company_id.id
                if aml.move_id and aml.move_id.company_id else False
            ),
            'product_id': (
                aml.product_id.id if getattr(aml, 'product_id', False) else False
            ),
            'analytic_account_id': False,
        }

    return None
