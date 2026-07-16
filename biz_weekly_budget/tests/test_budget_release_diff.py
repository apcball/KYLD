from odoo import fields
from odoo.tests import common


class TestBudgetReleaseDiff(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.today = fields.Date.today()

        cls.department = cls.env['hr.department'].create({
            'name': 'Release Diff Dept',
        })
        cls.analytic_plan = cls.env['account.analytic.plan'].create({
            'name': 'Release Diff Plan',
        })
        cls.analytic_account = cls.env['account.analytic.account'].create({
            'name': 'Release Diff AA',
            'plan_id': cls.analytic_plan.id,
        })
        cls.vendor_po = cls.env['res.partner'].create({
            'name': 'PO Vendor',
            'supplier_rank': 1,
        })
        cls.vendor_pr = cls.env['res.partner'].create({
            'name': 'PR Vendor (different)',
            'supplier_rank': 1,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Release Diff Product',
            'type': 'consu',
            'standard_price': 100.0,
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
            'name': 'Release Diff Employee',
            'department_id': cls.department.id,
            'company_id': cls.company.id,
        })

        cls.project = cls.env['project.project'].search(
            [('active', '=', True)], limit=1)
        if not cls.project:
            cls.skipTest(cls, 'No active project in DB — billing_type NOT NULL prevents creation')

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

    def _create_po(self, price_unit, quantity=1.0, extra_vals=None):
        vals = {
            'partner_id': self.vendor_po.id,
            'company_id': self.company.id,
            'department_id': self.department.id,
            'date_order': self.today,
            'payment_date': self.today,
            'order_line': [fields.Command.create({
                'product_id': self.product.id,
                'name': self.product.name,
                'product_qty': quantity,
                'product_uom': self.product.uom_po_id.id,
                'date_planned': self.today,
                'price_unit': price_unit,
                'department_id': self.department.id,
                'analytic_account_id': self.analytic_account.id,
            })],
            **(extra_vals or {}),
        }
        return self.env['purchase.order'].create(vals)

    def _create_vendor_bill(self, po, price_unit, quantity=1.0):
        po_line = po.order_line[:1]
        return self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.vendor_po.id,
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

    def test_pr_price_diff_with_different_vendor_releases_remaining(self):
        """PR reserves 1500 (no vendor). PO confirmed 1000 (vendor=X).
        Bill 1000. Remaining 500 must NOT stay reserved on PR."""
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
                'quantity': 10.0,
                'uom': self.product.uom_id.id,
                'partner_id': self.vendor_pr.id,
                'unit_price': 150.0,
                'analytic_distribution': {str(self.analytic_account.id): 100.0},
            })],
        })
        pr.write({'state': 'approved'})
        pr._update_budget_moves()
        self.assertAlmostEqual(
            self._reserved_amount('employee.purchase.requisition', pr.id), 1500.0,
            msg='PR should reserve 1500 initially')

        po = self._create_po(100.0, quantity=10.0, extra_vals={
            'requisition_order': pr.name,
            'pr_number': pr.name,
        })
        po.write({'state': 'purchase'})
        po._update_budget_moves()

        self.assertAlmostEqual(
            self._reserved_amount('employee.purchase.requisition', pr.id), 0.0,
            msg='PR reservation must be fully released after PO confirmed')
        self.assertAlmostEqual(
            self._reserved_amount('purchase.order', po.id), 1000.0,
            msg='PO should reserve 1000')

        bill = self._create_vendor_bill(po, 100.0, quantity=10.0)

        self.assertAlmostEqual(
            self._reserved_amount('purchase.order', po.id), 0.0,
            msg='PO reservation must be 0 after full bill')
        self.assertAlmostEqual(
            self._used_amount('account.move', bill.id), 1000.0,
            msg='Bill should record 1000 used')
        self.assertAlmostEqual(
            self._reserved_amount('employee.purchase.requisition', pr.id), 0.0,
            msg='PR must still be 0 — no phantom 500 reservation')

    def test_pr_no_vendor_releases_after_po_lower_price(self):
        """PR line has NO vendor. PO with vendor confirms lower price.
        Difference must be released."""
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
                'quantity': 10.0,
                'uom': self.product.uom_id.id,
                'unit_price': 150.0,
                'analytic_distribution': {str(self.analytic_account.id): 100.0},
            })],
        })
        pr.write({'state': 'approved'})
        pr._update_budget_moves()
        self.assertAlmostEqual(
            self._reserved_amount('employee.purchase.requisition', pr.id), 1500.0)

        po = self._create_po(100.0, quantity=10.0, extra_vals={
            'requisition_order': pr.name,
            'pr_number': pr.name,
        })
        po.write({'state': 'purchase'})
        po._update_budget_moves()

        self.assertAlmostEqual(
            self._reserved_amount('employee.purchase.requisition', pr.id), 0.0,
            msg='PR with no vendor must release fully when PO confirmed')
        self.assertAlmostEqual(
            self._reserved_amount('purchase.order', po.id), 1000.0)

    def test_mr_partial_qty_releases_remaining(self):
        """MR qty=15 estimated_cost=100 (reserves 1500).
        PO confirmed qty=10 price=100 (reserves 1000).
        MR should hold only 500 for remaining qty=5."""
        mr = self.env['material.requisition'].create({
            'project_id': self.project.id,
            'employee_id': self.employee.id,
            'required_date': self.today,
            'payment_date': self.today,
            'line_ids': [fields.Command.create({
                'product_id': self.product.id,
                'description': self.product.name,
                'quantity': 15.0,
                'uom_id': self.product.uom_id.id,
                'estimated_cost': 100.0,
                'analytic_account_id': self.analytic_account.id,
                'vendor_id': self.vendor_pr.id,
                'requisition_action': 'purchase',
            })],
        })
        mr.write({'state': 'approved'})
        mr._update_budget_moves()
        self.assertAlmostEqual(
            self._reserved_amount('material.requisition', mr.id), 1500.0)

        po = self._create_po(100.0, quantity=10.0, extra_vals={
            'origin': mr.name,
            'material_requisition_id': mr.id,
        }, line_extra_vals=None) if False else self.env['purchase.order'].create({
            'partner_id': self.vendor_po.id,
            'company_id': self.company.id,
            'department_id': self.department.id,
            'date_order': self.today,
            'payment_date': self.today,
            'origin': mr.name,
            'material_requisition_id': mr.id,
            'order_line': [fields.Command.create({
                'product_id': self.product.id,
                'name': self.product.name,
                'product_qty': 10.0,
                'product_uom': self.product.uom_po_id.id,
                'date_planned': self.today,
                'price_unit': 100.0,
                'department_id': self.department.id,
                'analytic_account_id': self.analytic_account.id,
                'material_requisition_line_id': mr.line_ids.id,
            })],
        })
        po.write({'state': 'purchase'})
        po._update_budget_moves()

        self.assertAlmostEqual(
            self._reserved_amount('material.requisition', mr.id), 500.0,
            msg='MR should hold only 500 for remaining 5 units')
        self.assertAlmostEqual(
            self._reserved_amount('purchase.order', po.id), 1000.0)

        bill = self._create_vendor_bill(po, 100.0, quantity=10.0)

        self.assertAlmostEqual(
            self._reserved_amount('purchase.order', po.id), 0.0)
        self.assertAlmostEqual(
            self._used_amount('account.move', bill.id), 1000.0)
        self.assertAlmostEqual(
            self._reserved_amount('material.requisition', mr.id), 500.0,
            msg='MR should still hold 500 for unordered qty')
