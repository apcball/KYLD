from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestJobCostSheetActualCosts(TransactionCase):
    """Covers JobCostSheet._compute_actual_costs / _get_bill_actual_cost_totals:
    actual cost is counted from POSTED VENDOR BILLS ONLY (2026-09-12 decision -
    confirmed-but-unbilled PO commitments and timesheets are not "actual" yet).
    Two sources, mutually exclusive per bill line: (1) job_cost_line_id set on
    the line -> attributed to that line's own cost_sheet_id, unambiguous; (2)
    no job_cost_line_id but analytic_distribution matches a sheet's account ->
    attributed by account id, which stays ambiguous when 2+ sheets share one
    account. Source (1) is what fixes the original bug where sheets sharing an
    analytic_account_id (e.g. a zone account covering several plots) all
    showed the same combined total."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        analytic_plan = cls.env['account.analytic.plan'].search([], limit=1) \
            or cls.env['account.analytic.plan'].create({'name': 'JCS actual cost test plan'})
        cls.account_a = cls.env['account.analytic.account'].create({
            'name': 'JCS actual cost test - account A', 'plan_id': analytic_plan.id,
        })
        cls.account_b = cls.env['account.analytic.account'].create({
            'name': 'JCS actual cost test - account B', 'plan_id': analytic_plan.id,
        })
        cls.project_a = cls.env['project.project'].create({
            'name': 'JCS actual cost test project A', 'company_id': cls.env.company.id,
        })
        cls.project_b = cls.env['project.project'].create({
            'name': 'JCS actual cost test project B', 'company_id': cls.env.company.id,
        })
        cls.sheet_a = cls.env['job.cost.sheet'].create({
            'project_id': cls.project_a.id, 'analytic_account_id': cls.account_a.id,
        })
        cls.sheet_b = cls.env['job.cost.sheet'].create({
            'project_id': cls.project_b.id, 'analytic_account_id': cls.account_b.id,
        })
        cls.material_product = cls.env['product.product'].create({
            'name': 'JCS actual cost test material', 'detailed_type': 'consu',
        })
        cls.service_product = cls.env['product.product'].create({
            'name': 'JCS actual cost test service', 'detailed_type': 'service',
        })
        cls.vendor = cls.env['res.partner'].create({'name': 'JCS actual cost test vendor'})

    def _bill_line(self, product, price, qty=1, analytic_distribution=None,
                    job_cost_line_id=None, move_type='in_invoice'):
        move = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': self.vendor.id,
            'invoice_date': '2026-01-15',
            'invoice_line_ids': [fields.Command.create({
                'product_id': product.id,
                'quantity': qty,
                'price_unit': price,
                'tax_ids': [fields.Command.clear()],
                'analytic_distribution': analytic_distribution or {},
            })],
        })
        move.action_post()
        line = move.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
        if job_cost_line_id:
            line.job_cost_line_id = job_cost_line_id
        return line

    def _cost_line(self, sheet, cost_type, product):
        return self.env['job.cost.line'].create({
            'cost_sheet_id': sheet.id, 'cost_type': cost_type, 'product_id': product.id,
            'name': product.name,
        })

    def test_single_full_distribution_by_product_type(self):
        self._bill_line(self.material_product, 1000,
                         analytic_distribution={str(self.account_a.id): 100.0})
        self._bill_line(self.service_product, 500,
                         analytic_distribution={str(self.account_a.id): 100.0})
        self.sheet_a._compute_actual_costs()
        self.assertEqual(self.sheet_a.actual_material_cost, 1000)
        self.assertEqual(self.sheet_a.actual_labour_cost, 500)
        self.assertEqual(self.sheet_a.actual_overhead_cost, 0)
        self.assertEqual(self.sheet_a.actual_total_cost, 1500)

    def test_pooled_line_splits_by_percentage_without_double_counting(self):
        self._bill_line(self.material_product, 1000, analytic_distribution={
            str(self.account_a.id): 60.0, str(self.account_b.id): 40.0,
        })
        (self.sheet_a | self.sheet_b)._compute_actual_costs()
        self.assertEqual(self.sheet_a.actual_material_cost, 600)
        self.assertEqual(self.sheet_b.actual_material_cost, 400)

    def test_partial_distribution_not_renormalized(self):
        self._bill_line(self.material_product, 1000,
                         analytic_distribution={str(self.account_a.id): 30.0})
        self.sheet_a._compute_actual_costs()
        self.assertEqual(self.sheet_a.actual_material_cost, 300)

    def test_refund_subtracts(self):
        self._bill_line(self.material_product, 1000,
                         analytic_distribution={str(self.account_a.id): 100.0})
        self._bill_line(self.material_product, 400, move_type='in_refund',
                         analytic_distribution={str(self.account_a.id): 100.0})
        self.sheet_a._compute_actual_costs()
        self.assertEqual(self.sheet_a.actual_material_cost, 600)

    def test_job_cost_line_link_attributes_to_its_own_sheet_not_shared_account(self):
        # The core regression test for the 2026-09-12 fix: sheet_a and a
        # second sheet sharing account_a (e.g. a zone account covering two
        # plots) must NOT both show a bill that is only linked to sheet_a's
        # own job.cost.line.
        sheet_a2 = self.env['job.cost.sheet'].create({
            'project_id': self.project_b.id, 'analytic_account_id': self.account_a.id,
        })
        cost_line = self._cost_line(self.sheet_a, 'labour', self.service_product)
        self._bill_line(self.service_product, 700, job_cost_line_id=cost_line.id)
        (self.sheet_a | sheet_a2)._compute_actual_costs()
        self.assertEqual(self.sheet_a.actual_labour_cost, 700)
        self.assertEqual(sheet_a2.actual_labour_cost, 0)

    def test_job_cost_line_link_takes_precedence_over_distribution_no_double_count(self):
        cost_line = self._cost_line(self.sheet_a, 'labour', self.service_product)
        self._bill_line(self.service_product, 700, job_cost_line_id=cost_line.id,
                         analytic_distribution={str(self.account_a.id): 100.0})
        self.sheet_a._compute_actual_costs()
        # Counted once (700) via the job_cost_line-linked source, not twice
        # (1400) even though the line also carries a matching distribution.
        self.assertEqual(self.sheet_a.actual_labour_cost, 700)

    def test_sheet_with_no_analytic_account_is_zero(self):
        sheet = self.env['job.cost.sheet'].create({'project_id': self.project_a.id})
        self._bill_line(self.material_product, 1000,
                         analytic_distribution={str(self.account_a.id): 100.0})
        sheet._compute_actual_costs()
        self.assertEqual(sheet.actual_total_cost, 0)
        self.assertEqual(sheet.actual_material_cost, 0)

    def test_invariant_total_equals_sum_of_buckets(self):
        self._bill_line(self.material_product, 1000,
                         analytic_distribution={str(self.account_a.id): 100.0})
        self._bill_line(self.service_product, 500,
                         analytic_distribution={str(self.account_a.id): 100.0})
        self.sheet_a._compute_actual_costs()
        self.assertEqual(
            self.sheet_a.actual_total_cost,
            self.sheet_a.actual_material_cost + self.sheet_a.actual_labour_cost
            + self.sheet_a.actual_overhead_cost,
        )

    def test_batched_across_recordset_matches_individual_results(self):
        self._bill_line(self.material_product, 1000,
                         analytic_distribution={str(self.account_a.id): 100.0})
        self._bill_line(self.material_product, 2000,
                         analytic_distribution={str(self.account_b.id): 100.0})
        (self.sheet_a | self.sheet_b)._compute_actual_costs()
        self.assertEqual(self.sheet_a.actual_material_cost, 1000)
        self.assertEqual(self.sheet_b.actual_material_cost, 2000)
