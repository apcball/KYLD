from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestJobCostSheetActualCosts(TransactionCase):
    """Covers JobCostSheet._compute_actual_costs / _get_analytic_actual_cost_totals:
    the hybrid analytic_distribution + job.cost.line-fallback design fixed on
    2026-09-12 to stop undercounting real spend (confirmed on PROD: pooled POs
    that split cost across projects via per-line analytic_distribution were
    invisible to the sheet's actual-cost total, since job.cost.line requires
    an explicit per-line FK link a pooled PO's header can't provide)."""

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

    def _po_line(self, product, price, qty=1, qty_received=None, analytic_distribution=None,
                 job_cost_line_id=None, state='purchase'):
        po = self.env['purchase.order'].create({
            'partner_id': self.vendor.id, 'date_order': '2026-01-15 12:00:00',
        })
        line = self.env['purchase.order.line'].create({
            'order_id': po.id, 'product_id': product.id, 'name': product.name,
            'product_qty': qty, 'price_unit': price, 'product_uom': product.uom_id.id,
            'date_planned': '2026-01-20 12:00:00',
            'taxes_id': [fields.Command.clear()],
            'analytic_distribution': analytic_distribution or {},
        })
        if job_cost_line_id:
            line.job_cost_line_id = job_cost_line_id
        po.state = state
        if qty_received is not None:
            line.qty_received = qty_received
        return line

    def _cost_line(self, sheet, cost_type, product):
        return self.env['job.cost.line'].create({
            'cost_sheet_id': sheet.id, 'cost_type': cost_type, 'product_id': product.id,
            'name': product.name,
        })

    def test_single_full_distribution_by_product_type(self):
        self._po_line(self.material_product, 1000, qty=1, qty_received=1,
                       analytic_distribution={str(self.account_a.id): 100.0})
        self._po_line(self.service_product, 500,
                       analytic_distribution={str(self.account_a.id): 100.0})
        self.sheet_a._compute_actual_costs()
        self.assertEqual(self.sheet_a.actual_material_cost, 1000)
        self.assertEqual(self.sheet_a.actual_labour_cost, 500)
        self.assertEqual(self.sheet_a.actual_overhead_cost, 0)
        self.assertEqual(self.sheet_a.actual_total_cost, 1500)

    def test_pooled_line_splits_by_percentage_without_double_counting(self):
        self._po_line(self.material_product, 1000, qty=1, qty_received=1, analytic_distribution={
            str(self.account_a.id): 60.0, str(self.account_b.id): 40.0,
        })
        (self.sheet_a | self.sheet_b)._compute_actual_costs()
        self.assertEqual(self.sheet_a.actual_material_cost, 600)
        self.assertEqual(self.sheet_b.actual_material_cost, 400)

    def test_partial_distribution_not_renormalized(self):
        self._po_line(self.material_product, 1000, qty=1, qty_received=1,
                       analytic_distribution={str(self.account_a.id): 30.0})
        self.sheet_a._compute_actual_costs()
        self.assertEqual(self.sheet_a.actual_material_cost, 300)

    def test_material_scaled_by_received_ratio(self):
        # price_unit=1000, qty=4 -> price_subtotal=4000; qty_received=1 of 4
        # -> scaled to 1/4 of the subtotal, matching update_actual_costs_from_purchases.
        self._po_line(self.material_product, 1000, qty=4, qty_received=1,
                       analytic_distribution={str(self.account_a.id): 100.0})
        self.sheet_a._compute_actual_costs()
        self.assertEqual(self.sheet_a.actual_material_cost, 1000)

    def test_labour_full_amount_regardless_of_receipt(self):
        # price_unit=1000, qty=4 -> price_subtotal=4000, taken in full since
        # service lines have no receipt milestone to scale against.
        self._po_line(self.service_product, 1000, qty=4, qty_received=0,
                       analytic_distribution={str(self.account_a.id): 100.0})
        self.sheet_a._compute_actual_costs()
        self.assertEqual(self.sheet_a.actual_labour_cost, 4000)

    def test_fallback_to_job_cost_line_when_no_distribution(self):
        cost_line = self._cost_line(self.sheet_a, 'labour', self.service_product)
        self._po_line(self.service_product, 700, job_cost_line_id=cost_line.id)
        self.sheet_a._compute_actual_costs()
        self.assertEqual(self.sheet_a.actual_labour_cost, 700)

    def test_distribution_present_takes_precedence_over_job_cost_line_no_double_count(self):
        cost_line = self._cost_line(self.sheet_a, 'labour', self.service_product)
        self._po_line(self.service_product, 700, job_cost_line_id=cost_line.id,
                      analytic_distribution={str(self.account_a.id): 100.0})
        self.sheet_a._compute_actual_costs()
        # Counted once (700), not twice (1400) even though both signals exist.
        self.assertEqual(self.sheet_a.actual_labour_cost, 700)

    def test_sheet_with_no_analytic_account_is_zero(self):
        sheet = self.env['job.cost.sheet'].create({'project_id': self.project_a.id})
        self._po_line(self.material_product, 1000, qty=1, qty_received=1,
                      analytic_distribution={str(self.account_a.id): 100.0})
        sheet._compute_actual_costs()
        self.assertEqual(sheet.actual_total_cost, 0)
        self.assertEqual(sheet.actual_material_cost, 0)

    def test_invariant_total_equals_sum_of_buckets(self):
        self._po_line(self.material_product, 1000, qty=1, qty_received=1,
                       analytic_distribution={str(self.account_a.id): 100.0})
        self._po_line(self.service_product, 500,
                       analytic_distribution={str(self.account_a.id): 100.0})
        self.sheet_a._compute_actual_costs()
        self.assertEqual(
            self.sheet_a.actual_total_cost,
            self.sheet_a.actual_material_cost + self.sheet_a.actual_labour_cost
            + self.sheet_a.actual_overhead_cost,
        )

    def test_batched_across_recordset_matches_individual_results(self):
        self._po_line(self.material_product, 1000, qty=1, qty_received=1,
                       analytic_distribution={str(self.account_a.id): 100.0})
        self._po_line(self.material_product, 2000, qty=1, qty_received=1,
                       analytic_distribution={str(self.account_b.id): 100.0})
        (self.sheet_a | self.sheet_b)._compute_actual_costs()
        self.assertEqual(self.sheet_a.actual_material_cost, 1000)
        self.assertEqual(self.sheet_b.actual_material_cost, 2000)
