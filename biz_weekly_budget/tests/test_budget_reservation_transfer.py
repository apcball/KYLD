from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import common


class TestBudgetReservationTransfer(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.today = fields.Date.today()

        cls.department = cls.env['hr.department'].create({
            'name': 'Budget Transfer Dept',
        })
        cls.analytic_plan = cls.env['account.analytic.plan'].create({
            'name': 'Budget Transfer Analytic Plan',
        })
        cls.analytic_account = cls.env['account.analytic.account'].create({
            'name': 'Budget Transfer Analytic',
            'plan_id': cls.analytic_plan.id,
        })
        cls.vendor = cls.env['res.partner'].create({
            'name': 'Budget Transfer Vendor',
            'supplier_rank': 1,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Budget Transfer Product',
            'type': 'consu',
            'standard_price': 100.0,
        })
        cls.project = cls.env['project.project'].create({
            'name': 'Budget Transfer Project',
        })

        cls.plan = cls.env['monthly.budget.plan'].create({
            'month': str(cls.today.month).zfill(2),
            'year': str(cls.today.year),
            'total_budget': 100000.0,
            'company_id': cls.company.id,
        })
        cls.allocation = cls.env['monthly.budget.allocation'].create({
            'plan_id': cls.plan.id,
            'department_id': cls.department.id,
            'percentage': 100.0,
        })
        cls.plan.action_confirm()

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Budget Transfer Employee',
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })

    def _reserved_amount(self, source_model, source_id):
        moves = self.env['budget.move'].search([
            ('source_model', '=', source_model),
            ('source_id', '=', source_id),
            ('move_type', '=', 'reserved'),
        ])
        return sum(moves.mapped('amount'))

    def _used_amount(self, source_model, source_id):
        moves = self.env['budget.move'].search([
            ('source_model', '=', source_model),
            ('source_id', '=', source_id),
            ('move_type', '=', 'used'),
        ])
        return sum(moves.mapped('amount'))

    def _po_line_vals(self, price_unit, quantity=1.0, extra_vals=None):
        return {
            'product_id': self.product.id,
            'name': self.product.name,
            'product_qty': quantity,
            'product_uom': self.product.uom_po_id.id,
            'date_planned': self.today,
            'price_unit': price_unit,
            'department_id': self.department.id,
            'analytic_account_id': self.analytic_account.id,
            **(extra_vals or {}),
        }

    def _create_po(self, price_unit, quantity=1.0, extra_vals=None, line_extra_vals=None):
        vals = {
            'partner_id': self.vendor.id,
            'company_id': self.company.id,
            'department_id': self.department.id,
            'date_order': self.today,
            'payment_date': self.today,
            'order_line': [fields.Command.create(self._po_line_vals(
                price_unit,
                quantity=quantity,
                extra_vals=line_extra_vals,
            ))],
            **(extra_vals or {}),
        }
        return self.env['purchase.order'].create(vals)

    def _create_vendor_bill(self, po, price_unit, quantity=1.0, po_line=None):
        po_line = po_line or po.order_line[:1]
        return self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor.id,
            'company_id': self.company.id,
            'department_id': self.department.id,
            'invoice_date': self.today,
            'invoice_date_due': self.today,
            'invoice_line_ids': [fields.Command.create({
                'product_id': self.product.id,
                'name': self.product.name,
                'quantity': quantity,
                'price_unit': price_unit,
                'purchase_line_id': po_line.id,
                'analytic_distribution': {str(self.analytic_account.id): 100.0},
            })],
        })

    def test_mr_reservation_moves_from_mr_to_po_then_bill(self):
        mr = self.env['material.requisition'].create({
            'project_id': self.project.id,
            'employee_id': self.employee.id,
            'required_date': self.today,
            'payment_date': self.today,
            'line_ids': [fields.Command.create({
                'product_id': self.product.id,
                'description': self.product.name,
                'quantity': 1.0,
                'uom_id': self.product.uom_id.id,
                'estimated_cost': 100.0,
                'analytic_account_id': self.analytic_account.id,
                'vendor_id': self.vendor.id,
                'requisition_action': 'purchase',
            })],
        })
        mr.write({'state': 'approved'})
        mr._update_budget_moves()
        self.assertAlmostEqual(self._reserved_amount('material.requisition', mr.id), 100.0)

        po = self._create_po(80.0, extra_vals={
            'origin': mr.name,
            'material_requisition_id': mr.id,
        }, line_extra_vals={
            'material_requisition_line_id': mr.line_ids.id,
        })
        po.write({'state': 'purchase'})
        po._update_budget_moves()

        self.assertAlmostEqual(self._reserved_amount('material.requisition', mr.id), 0.0)
        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 80.0)

        bill = self._create_vendor_bill(po, 80.0)
        self.assertAlmostEqual(self._used_amount('account.move', bill.id), 80.0)
        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 0.0)

    def test_pr_reservation_releases_price_difference_after_confirmed_po(self):
        pr = self.env['employee.purchase.requisition'].create({
            'employee_id': self.employee.id,
            'user_id': self.env.user.id,
            'company_id': self.company.id,
            'request_date': self.today,
            'requisition_date': self.today,
            'requisition_deadline': self.today,
            'payment_date': self.today,
            'requisition_order_ids': [fields.Command.create({
                'product_id': self.product.id,
                'quantity': 1.0,
                'uom': self.product.uom_id.id,
                'partner_id': self.vendor.id,
                'unit_price': 100.0,
                'analytic_distribution': {str(self.analytic_account.id): 100.0},
            })],
        })
        pr.write({'state': 'approved'})
        pr._update_budget_moves()
        self.assertAlmostEqual(self._reserved_amount('employee.purchase.requisition', pr.id), 100.0)

        po = self._create_po(80.0, extra_vals={
            'requisition_order': pr.name,
            'pr_number': pr.name,
        })
        po.write({'state': 'purchase'})
        po._update_budget_moves()

        self.assertAlmostEqual(self._reserved_amount('employee.purchase.requisition', pr.id), 0.0)
        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 80.0)

    def test_cancelled_pr_releases_reservation(self):
        pr = self.env['employee.purchase.requisition'].create({
            'employee_id': self.employee.id,
            'user_id': self.env.user.id,
            'company_id': self.company.id,
            'request_date': self.today,
            'requisition_date': self.today,
            'requisition_deadline': self.today,
            'payment_date': self.today,
            'requisition_order_ids': [fields.Command.create({
                'product_id': self.product.id,
                'quantity': 1.0,
                'uom': self.product.uom_id.id,
                'partner_id': self.vendor.id,
                'unit_price': 100.0,
            })],
        })
        pr.write({'state': 'approved'})
        self.assertAlmostEqual(
            self._reserved_amount('employee.purchase.requisition', pr.id), 100.0
        )

        pr.write({'state': 'cancelled'})

        self.assertAlmostEqual(
            self._reserved_amount('employee.purchase.requisition', pr.id), 0.0
        )

    def test_mr_reservation_stays_when_po_month_has_no_allocation(self):
        mr = self.env['material.requisition'].create({
            'project_id': self.project.id,
            'employee_id': self.employee.id,
            'required_date': self.today,
            'payment_date': self.today,
            'line_ids': [fields.Command.create({
                'product_id': self.product.id,
                'description': self.product.name,
                'quantity': 1.0,
                'uom_id': self.product.uom_id.id,
                'estimated_cost': 100.0,
                'analytic_account_id': self.analytic_account.id,
                'vendor_id': self.vendor.id,
                'requisition_action': 'purchase',
            })],
        })
        mr.write({'state': 'approved'})
        mr._update_budget_moves()

        no_plan_date = fields.Date.from_string('2099-01-15')
        po = self._create_po(80.0, extra_vals={
            'origin': mr.name,
            'material_requisition_id': mr.id,
            'payment_date': no_plan_date,
        }, line_extra_vals={
            'material_requisition_line_id': mr.line_ids.id,
        })
        po.write({'state': 'purchase'})
        po._update_budget_moves()

        self.assertAlmostEqual(self._reserved_amount('material.requisition', mr.id), 100.0)
        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 0.0)

    def test_mr_partial_purchase_allocation_keeps_only_unordered_quantity(self):
        mr = self.env['material.requisition'].create({
            'project_id': self.project.id,
            'employee_id': self.employee.id,
            'required_date': self.today,
            'payment_date': self.today,
            'line_ids': [fields.Command.create({
                'product_id': self.product.id,
                'description': self.product.name,
                'quantity': 2.0,
                'uom_id': self.product.uom_id.id,
                'estimated_cost': 100.0,
                'analytic_account_id': self.analytic_account.id,
                'vendor_id': self.vendor.id,
                'requisition_action': 'purchase',
            })],
        })
        mr.write({'state': 'approved'})
        mr._update_budget_moves()
        self.assertAlmostEqual(self._reserved_amount('material.requisition', mr.id), 200.0)

        po = self._create_po(80.0)
        self.env['purchase.allocation'].create({
            'po_line_id': po.order_line.id,
            'mr_line_id': mr.line_ids.id,
            'qty': 1.0,
        })
        po.write({'state': 'purchase'})
        po._update_budget_moves()

        self.assertAlmostEqual(self._reserved_amount('material.requisition', mr.id), 100.0)
        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 80.0)

    def test_vendor_bill_without_allocation_is_blocked(self):
        po = self._create_po(80.0)
        po.write({'state': 'purchase'})
        po._update_budget_moves()
        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 80.0)

        no_plan_date = fields.Date.from_string('2099-01-15')
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env['account.move'].create({
                'move_type': 'in_invoice',
                'partner_id': self.vendor.id,
                'company_id': self.company.id,
                'department_id': self.department.id,
                'invoice_date': no_plan_date,
                'invoice_date_due': no_plan_date,
                'invoice_line_ids': [fields.Command.create({
                    'product_id': self.product.id,
                    'name': self.product.name,
                    'quantity': 1.0,
                    'price_unit': 80.0,
                    'purchase_line_id': po.order_line.id,
                    'analytic_distribution': {str(self.analytic_account.id): 100.0},
                })],
            })

        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 80.0)

    def test_bill_below_reserved_amount_returns_difference(self):
        po = self._create_po(100.0)
        po.write({'state': 'purchase'})
        po._update_budget_moves()
        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 100.0)

        bill = self._create_vendor_bill(po, 80.0)

        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 0.0)
        self.assertAlmostEqual(self._used_amount('account.move', bill.id), 80.0)

    def test_bill_above_reserved_amount_consumes_difference(self):
        po = self._create_po(100.0)
        po.write({'state': 'purchase'})
        po._update_budget_moves()

        bill = self._create_vendor_bill(po, 120.0)

        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 0.0)
        self.assertAlmostEqual(self._used_amount('account.move', bill.id), 120.0)

    def test_partial_bill_replaces_only_billed_commitment(self):
        po = self._create_po(100.0, quantity=2.0)
        po.write({'state': 'purchase'})
        po._update_budget_moves()
        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 200.0)

        bill = self._create_vendor_bill(po, 80.0, quantity=1.0)

        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 100.0)
        self.assertAlmostEqual(self._used_amount('account.move', bill.id), 80.0)

    def test_negative_po_adjustments_release_reserved_budget(self):
        line_amounts = [100.0, 40.0, -40.0, 20.0, -20.0]
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id,
            'company_id': self.company.id,
            'department_id': self.department.id,
            'date_order': self.today,
            'payment_date': self.today,
            'order_line': [
                fields.Command.create(self._po_line_vals(amount))
                for amount in line_amounts
            ],
        })
        po.write({'state': 'purchase'})
        po._update_budget_moves()
        self.assertAlmostEqual(po.amount_untaxed, 100.0)
        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 100.0)

        billed_line = po.order_line.filtered(lambda line: line.price_unit == 40.0)
        bill = self._create_vendor_bill(po, 30.0, po_line=billed_line)

        self.assertAlmostEqual(self._reserved_amount('purchase.order', po.id), 60.0)
        self.assertAlmostEqual(self._used_amount('account.move', bill.id), 30.0)
