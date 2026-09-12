"""Diagnostic scenarios for QA_REPORT.md, 2026-09-12.
Run through Odoo shell ONLY in the isolated Docker Compose QA project.
Each scenario rolls back; this is evidence tooling, not an addon test import.
"""
from odoo.tools import config
if env.cr.dbname != 'MOG_TEST' or config['db_host'] != 'db':
    raise RuntimeError('Requires isolated Compose database MOG_TEST on host db')

import json
import traceback
from odoo import fields
from odoo.exceptions import AccessError, ValidationError

def emit(case, **data):
    print('QA_RESULT ' + json.dumps(dict(case=case, **data), ensure_ascii=False, default=str))

def fixture():
    company = env.company
    plan = env['account.analytic.plan'].search([], limit=1)
    analytic = env['account.analytic.account'].create({'name': 'QA analytic', 'plan_id': plan.id, 'company_id': company.id})
    project = env['project.project'].create({'name': 'QA โครงการทดสอบ', 'company_id': company.id, 'analytic_account_id': analytic.id})
    sheet = env['job.cost.sheet'].create({'project_id': project.id, 'analytic_account_id': analytic.id, 'state': 'approved'})
    product = env['product.product'].create({'name': 'QA วัสดุ', 'detailed_type': 'consu'})
    service = env['product.product'].create({'name': 'QA แรงงาน', 'detailed_type': 'service'})
    vendor = env['res.partner'].create({'name': 'QA ผู้ขาย', 'supplier_rank': 1})
    return company, analytic, project, sheet, product, service, vendor

def po_for(product, vendor, analytic, qty=10, price=100, **extra):
    vals = {'partner_id': vendor.id, 'date_order': '2026-09-12 00:00:00',
            'order_line': [fields.Command.create({'product_id': product.id, 'name': product.name,
                'product_qty': qty, 'product_uom': product.uom_id.id, 'price_unit': price,
                'taxes_id': [fields.Command.clear()], 'analytic_distribution': {str(analytic.id): 100}})]}
    vals.update(extra)
    po = env['purchase.order'].create(vals)
    po.button_confirm()
    return po

def mr_for(project, product, qty=10, action='purchase', **extra):
    vals = {'project_id': project.id, 'required_date': fields.Date.today(),
            'line_ids': [fields.Command.create({'product_id': product.id, 'description': product.name,
                'quantity': qty, 'uom_id': product.uom_id.id, 'requisition_action': action})]}
    vals.update(extra)
    return env['material.requisition'].create(vals)

def bill_case():
    company, analytic, project, sheet, product, service, vendor = fixture()
    expense = env['account.account'].create({'name': 'QA Expense', 'code': 'QA600001', 'account_type': 'expense', 'company_id': company.id})
    payable = env['account.account'].create({'name': 'QA Payable', 'code': 'QA200001', 'account_type': 'liability_payable', 'reconcile': True, 'company_id': company.id})
    vendor.property_account_payable_id = payable
    journal = env['account.journal'].create({'name': 'QA Purchases', 'code': 'QAPUR', 'type': 'purchase', 'company_id': company.id, 'default_account_id': expense.id})
    po = po_for(service, vendor, analytic)
    sheet._compute_actual_costs()
    before = sheet.actual_total_cost
    bill = env['account.move'].create({'move_type': 'in_invoice', 'partner_id': vendor.id,
        'invoice_date': fields.Date.today(), 'journal_id': journal.id,
        'invoice_line_ids': [fields.Command.create({'product_id': service.id, 'name': service.name,
            'quantity': 10, 'price_unit': 100, 'account_id': expense.id, 'purchase_line_id': po.order_line.id,
            'tax_ids': [fields.Command.clear()], 'analytic_distribution': {str(analytic.id): 100}})]})
    bill.action_post()
    sheet._compute_actual_costs()
    emit('posted_bill', before=before, after=sheet.actual_total_cost, expected=1000,
         bill_state=bill.state, display_type=bill.invoice_line_ids.display_type, bill_total=bill.amount_untaxed)
    refund = env['account.move'].create({'move_type': 'in_refund', 'partner_id': vendor.id,
        'invoice_date': fields.Date.today(), 'journal_id': journal.id,
        'invoice_line_ids': [fields.Command.create({'product_id': service.id, 'name': service.name,
            'quantity': 2, 'price_unit': 100, 'account_id': expense.id,
            'tax_ids': [fields.Command.clear()], 'analytic_distribution': {str(analytic.id): 100}})]})
    refund.action_post()
    sheet._compute_actual_costs()
    emit('vendor_refund', actual=sheet.actual_total_cost, expected=800, refund_subtotal=refund.invoice_line_ids.price_subtotal, refund_balance=refund.invoice_line_ids.balance)

def timesheet_case():
    company, analytic, project, sheet, product, service, vendor = fixture()
    employee = env['hr.employee'].create({'name': 'QA Worker', 'company_id': company.id, 'hourly_cost': 100})
    task = env['project.task'].create({'name': 'QA Work', 'project_id': project.id})
    line = env['job.cost.line'].create({'cost_sheet_id': sheet.id, 'cost_type': 'labour', 'name': 'QA Hours'})
    timesheet = env['account.analytic.line'].create({'name': 'QA 2 hours', 'account_id': analytic.id,
        'task_id': task.id, 'employee_id': employee.id, 'unit_amount': 2, 'job_cost_line_id': line.id})
    line._compute_actual_qty(); line._compute_actual_unit_cost(); line._compute_actual_cost(); sheet._compute_actual_costs()
    emit('timesheet_total', amount=timesheet.amount, hours=timesheet.unit_amount, line_actual=line.actual_cost,
        sheet_actual=sheet.actual_total_cost, expected=abs(timesheet.amount))

def approval_case():
    company, analytic, project, sheet, product, service, vendor = fixture()
    user = env['res.users'].with_context(no_reset_password=True).create({'name': 'QA Requester', 'login': 'qa-requester-probe',
        'company_id': company.id, 'company_ids': [fields.Command.set([company.id])],
        'groups_id': [fields.Command.set([env.ref('job_costing_management.group_material_requisition_user').id])]})
    mr = mr_for(project, product)
    user_mr = mr.with_user(user)
    user_mr.action_dept_approve()
    user_mr.action_approve()
    emit('requester_approval', state=mr.state, user_is_manager=user.has_group('job_costing_management.group_material_requisition_manager'),
         user_is_dept_manager=user.has_group('job_costing_management.group_department_manager'), expected='AccessError; remain draft')
    mr2 = mr_for(project, product)
    mr2.with_user(user).write({'state': 'approved'})
    emit('requester_direct_state_write', actual=mr2.state, expected='AccessError')
    mr3 = mr_for(project, product)
    mr3.with_user(user).unlink()
    emit('requester_delete', exists=bool(mr3.exists()), note='Observed ACL behavior; confirm intended deletion policy')

def currency_case():
    company, analytic, project, sheet, product, service, vendor = fixture()
    foreign = env['res.currency'].create({'name': 'QAZ', 'symbol': 'Q', 'rounding': 0.01})
    env['res.currency.rate'].create({'currency_id': foreign.id, 'name': '2026-09-12', 'rate': 0.5, 'company_id': company.id})
    po = po_for(service, vendor, analytic, qty=1, price=100, currency_id=foreign.id)
    expected = foreign._convert(100, company.currency_id, company, po.date_order.date())
    sheet._compute_actual_costs()
    emit('foreign_currency', company_currency=company.currency_id.name, po_currency=foreign.name,
         actual=sheet.actual_total_cost, expected=expected)

def transfer_case():
    company, analytic, project, sheet, product, service, vendor = fixture()
    env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1).int_type_id.active = True
    mr = mr_for(project, product, action='internal', state='approved')
    first = env['stock.picking'].browse(mr.action_create_picking()['res_id'])
    second = env['stock.picking'].browse(mr.action_create_picking()['res_id'])
    emit('internal_transfer', source=first.location_id.complete_name, destination=first.location_dest_id.complete_name,
         same_location=first.location_id == first.location_dest_id, linked_pickings=len(mr.line_ids.picking_ids),
         total_requested_qty=sum((first | second).move_ids.mapped('product_uom_qty')), mr_qty=mr.line_ids.quantity)

def uom_case():
    company, analytic, project, sheet, product, service, vendor = fixture()
    mr = mr_for(project, product, qty=12, state='ordered')
    po = po_for(product, vendor, analytic, qty=1)
    po.order_line.write({'product_uom': env.ref('uom.product_uom_dozen').id, 'material_requisition_line_id': mr.line_ids.id})
    mr._check_and_mark_done()
    emit('mr_uom', mr_qty=12, mr_uom=mr.line_ids.uom_id.name, po_qty=1, po_uom=po.order_line.product_uom.name,
         actual=mr.state, expected='received')

def report_case():
    company, analytic, project, sheet, product, service, vendor = fixture()
    sheet.currency_id = company.currency_id
    mr = mr_for(project, product)
    boq = env['boq.boq'].create({'title': 'QA วัสดุทดสอบ', 'project_id': project.id,
        'job_cost_sheet_id': sheet.id, 'line_ids': [fields.Command.create({'product_id': product.id,
            'description': 'วัสดุภาษาไทย', 'quantity': 2, 'unit_cost': 100, 'uom_id': product.uom_id.id})]})
    for model, record in [('job.cost.sheet', sheet), ('material.requisition', mr), ('boq.boq', boq)]:
        report = env['ir.actions.report'].search([('model', '=', model), ('report_name', 'like', 'job_costing_management')], limit=1)
        try:
            with env.cr.savepoint():
                if report.report_type == 'xlsx':
                    data, kind = report._render_xlsx(report.report_name, record.ids, data={})
                else:
                    data, kind = report._render_qweb_pdf(report.report_name, record.ids)
                emit('report', model=model, record_name=record.name, kind=kind, bytes=len(data), magic=data[:5].hex())
        except Exception as exc:
            emit('report', model=model, record_name=record.name, error=type(exc).__name__, message=str(exc)[-1800:])

def freshness_case():
    company, analytic, project, sheet, product, service, vendor = fixture()
    po = po_for(service, vendor, analytic, qty=1, price=100)
    env.flush_all()
    sheet.invalidate_recordset()
    stored = sheet.actual_total_cost
    computed = sheet._get_analytic_actual_cost_totals([analytic.id])
    emit('analytic_only_freshness', stored=stored, computed=computed, po_line_link=po.order_line.job_cost_line_id.id)
    sheet._compute_actual_costs()
    po.order_line.analytic_distribution = {}
    env.flush_all(); sheet.invalidate_recordset()
    emit('distribution_change', stored=sheet.actual_total_cost, computed=sheet._get_analytic_actual_cost_totals([analytic.id]))

def cross_company_case():
    company, analytic, project, sheet, product, service, vendor = fixture()
    other = env['res.company'].create({'name': 'QA Probe Company B %s' % project.id})
    other_project = env['project.project'].with_company(other).create({'name': 'QA B Project', 'company_id': other.id})
    user = env['res.users'].with_context(no_reset_password=True).create({'name': 'QA manager', 'login': 'qa-manager-probe',
        'company_id': company.id, 'company_ids': [fields.Command.set([company.id, other.id])],
        'groups_id': [fields.Command.set([env.ref('job_costing_management.group_job_costing_manager').id])]})
    bad = env['job.cost.sheet'].with_user(user).with_context(allowed_company_ids=[company.id, other.id]).create({
        'project_id': other_project.id, 'company_id': company.id, 'analytic_account_id': analytic.id})
    emit('cross_company_link', sheet_company=bad.company_id.id, project_company=bad.project_id.company_id.id,
        expected='ValidationError for incompatible companies')
    other_sheet = env['job.cost.sheet'].with_company(other).create({'project_id': other_project.id, 'company_id': other.id})
    visible = env['job.cost.sheet'].with_user(user).with_context(allowed_company_ids=[company.id]).search([('id', '=', other_sheet.id)])
    emit('cross_company_read_rule', visible_ids=visible.ids, expected=[])

def validate(picking, qty):
    picking.move_ids.write({'quantity': qty, 'picked': True})
    return picking.with_context(skip_backorder=True).button_validate()

def pool_case():
    company, analytic, project, sheet, product, service, vendor = fixture()
    mr1 = mr_for(project, product, qty=4, state='approved', analytic_account_id=analytic.id, job_cost_sheet_id=sheet.id)
    mr2 = mr_for(project, product, qty=6, state='approved', analytic_account_id=analytic.id, job_cost_sheet_id=sheet.id)
    mrs = mr1 | mr2
    mrs.line_ids.write({'vendor_id': vendor.id, 'analytic_distribution': {str(analytic.id): 100}})
    wizard = env['add.to.pool.wizard'].create({'requisition_id': mr1.id, 'create_new_pool': True,
        'mr_line_ids': [fields.Command.set(mr1.line_ids.ids)]})
    pool = env['procurement.pool'].browse(wizard.action_add_to_pool()['res_id'])
    env['add.to.pool.wizard'].create({'requisition_id': mr2.id, 'pool_id': pool.id,
        'mr_line_ids': [fields.Command.set(mr2.line_ids.ids)]}).action_add_to_pool()
    pool.line_ids.price_unit = 100
    pool.action_confirm()
    pool.action_create_rfq()
    po = env['purchase.order'].search([('procurement_pool_id', '=', pool.id)])
    allocs = env['purchase.allocation'].search([('po_line_id', 'in', po.order_line.ids)])
    emit('pool_rfq_initial', demand=pool.line_ids.total_qty, stored_ordered=pool.line_ids.ordered_qty,
        po_qty=sum(po.order_line.mapped('product_qty')), allocated=sum(allocs.mapped('qty')))
    env.flush_all()
    pool.line_ids.invalidate_recordset()
    try:
        with env.cr.savepoint():
            pool.action_create_rfq()
            repeat = env['purchase.order'].search([('procurement_pool_id', '=', pool.id)])
            emit('pool_rfq_repeat', po_count=len(repeat), total_po_qty=sum(repeat.order_line.mapped('product_qty')), expected='no additional demand')
            raise RuntimeError('rollback repeat diagnostic')
    except RuntimeError:
        pass
    po.button_confirm()
    picking = po.picking_ids.filtered(lambda p: p.state != 'cancel')
    validate(picking, 4)
    backorder = env['stock.picking'].search([('backorder_id', '=', picking.id)])
    emit('pool_partial_receipt', received=po.order_line.qty_received, picking_state=picking.state,
        backorder_qty=sum(backorder.move_ids.mapped('product_uom_qty')), allocated_received=sum(allocs.mapped('qty_received')))
    if backorder:
        validate(backorder, 6)
    emit('pool_full_receipt', received=po.order_line.qty_received, allocated_received=sum(allocs.mapped('qty_received')),
        pool_state=pool.state, mr_states=mrs.mapped('state'))
    return_wizard = env['stock.return.picking'].with_context(active_id=picking.id, active_ids=picking.ids, active_model='stock.picking').create({})
    return_wizard.product_return_moves.quantity = 2
    return_action = return_wizard.create_returns()
    returned = env['stock.picking'].browse(return_action['res_id'])
    validate(returned, 2)
    emit('pool_return', po_received=po.order_line.qty_received, allocated_received=sum(allocs.mapped('qty_received')),
        expected_allocated_received=8, pool_state=pool.state)

def direct_receipt_case():
    company, analytic, project, sheet, product, service, vendor = fixture()
    po = po_for(product, vendor, analytic)
    receipt = po.picking_ids
    validate(receipt, 4)
    sheet._compute_actual_costs()
    emit('direct_partial', received=po.order_line.qty_received, actual=sheet.actual_material_cost, expected=400)
    backorder = env['stock.picking'].search([('backorder_id','=',receipt.id)])
    validate(backorder, 6)
    sheet._compute_actual_costs()
    emit('direct_full', received=po.order_line.qty_received, actual=sheet.actual_material_cost, expected=1000)
    return_wizard = env['stock.return.picking'].with_context(active_id=receipt.id, active_ids=receipt.ids, active_model='stock.picking').create({})
    return_wizard.product_return_moves.quantity = 2
    returned = env['stock.picking'].browse(return_wizard.create_returns()['res_id'])
    validate(returned, 2)
    sheet._compute_actual_costs()
    emit('direct_return', received=po.order_line.qty_received, actual=sheet.actual_material_cost, expected=800)


for case in [bill_case, timesheet_case, approval_case, currency_case, transfer_case,
             uom_case, report_case, freshness_case, cross_company_case,
             pool_case, direct_receipt_case]:
    try:
        with env.cr.savepoint():
            case()
    except Exception as exc:
        emit(case.__name__, error=type(exc).__name__, message=str(exc),
             traceback=traceback.format_exc()[-1800:])
    finally:
        env.cr.rollback()
        env.invalidate_all()
