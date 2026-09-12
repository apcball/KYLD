from lxml import etree

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestServicePO(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['project.project'].create({
            'name': 'Service PO test', 'company_id': cls.env.company.id,
        })
        analytic_plan = cls.env['account.analytic.plan'].search([], limit=1) \
            or cls.env['account.analytic.plan'].create({'name': 'Service PO test plan'})
        cls.analytic_account = cls.env['account.analytic.account'].create({
            'name': 'Service PO test analytic account', 'plan_id': analytic_plan.id,
        })
        cls.other_analytic_account = cls.env['account.analytic.account'].create({
            'name': 'Service PO test analytic account (other sheet)', 'plan_id': analytic_plan.id,
        })
        cls.sheet = cls.env['job.cost.sheet'].create({
            'project_id': cls.project.id, 'currency_id': cls.env.company.currency_id.id,
            'analytic_account_id': cls.analytic_account.id,
        })
        cls.other_sheet = cls.env['job.cost.sheet'].create({
            'project_id': cls.project.id, 'currency_id': cls.env.company.currency_id.id,
            'analytic_account_id': cls.other_analytic_account.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Repeated service', 'detailed_type': 'service',
        })
        cls.vendor = cls.env['res.partner'].create({'name': 'Service PO vendor'})
        cls.buyer = new_test_user(
            cls.env, login='service_po_buyer',
            groups='purchase.group_purchase_user,job_costing_management.group_job_costing_user',
            company_id=cls.env.company.id,
        )

    def _po(self, descriptions=('Door', 'Window'), prices=(100, 200), **vals):
        po = self.env['purchase.order'].create(dict({
            'partner_id': self.vendor.id, 'job_cost_sheet_id': self.sheet.id,
            'currency_id': self.sheet.currency_id.id,
            'date_order': '2026-01-15 12:00:00',
        }, **vals))
        for sequence, (description, price) in enumerate(zip(descriptions, prices), 1):
            self.env['purchase.order.line'].create({
                'order_id': po.id, 'product_id': self.product.id, 'name': description,
                'product_qty': 1, 'price_unit': price,
                'product_uom': self.product.uom_id.id, 'sequence': sequence,
                'date_planned': '2026-01-20 12:00:00',
                'taxes_id': [fields.Command.clear()],
            })
        # The report consumes confirmed records; avoid unrelated stock/receipt
        # automation in fixtures. No live database is used by these tests.
        po.state = 'purchase'
        return po

    def _refresh(self, sheet=None):
        sheet = sheet or self.sheet
        sheet.invalidate_recordset([
            'service_po_line_ids', 'service_po_ordered_total',
            'service_po_warning', 'service_po_currency_id',
        ])
        return sheet

    def _allocate(self, line, sheet, qty):
        mr = self.env['material.requisition'].create({
            'project_id': self.project.id, 'job_cost_sheet_id': sheet.id,
            'required_date': '2026-01-20',
        })
        mr_line = self.env['material.requisition.line'].create({
            'requisition_id': mr.id, 'product_id': self.product.id,
            'description': 'Allocated service', 'quantity': qty,
            'uom_id': self.product.uom_id.id,
        })
        return self.env['purchase.allocation'].create({
            'po_line_id': line.id, 'mr_line_id': mr_line.id,
            'job_cost_sheet_id': sheet.id, 'qty': qty,
        })

    def test_duplicate_products_and_descriptions_are_distinct(self):
        first = self._po()
        second = self._po(descriptions=('Door',), prices=(50,))
        cost_lines = self.sheet.material_cost_ids
        before = self.sheet.read(['total_cost', 'boq_total_cost', 'actual_total_cost'])[0]
        self.assertEqual(self.sheet.service_po_line_ids, first.order_line | second.order_line)
        self.assertCountEqual(self.sheet.service_po_line_ids.mapped('name'), ['Door', 'Window', 'Door'])
        self.assertEqual(self.sheet.service_po_ordered_total, 350)
        self.assertEqual(self.sheet.material_cost_ids, cost_lines)
        self.assertEqual(self.sheet.read(list(before))[0], before)
        self.assertEqual(sum(first.order_line.mapped('qty_received')), 0)
        contextual = first.order_line.with_context(service_job_cost_sheet_id=self.sheet.id)
        self.assertEqual(contextual.mapped('service_jcs_amount'), [100, 200])

    def test_states_negative_amount_and_reload(self):
        po = self._po(prices=(100, -20))
        self.assertEqual(self.sheet.service_po_ordered_total, 80)
        po.order_line[0].price_unit = 120
        self.assertEqual(self._refresh().service_po_ordered_total, 100)
        for state, total in [('draft', 0), ('sent', 0), ('cancel', 0), ('done', 100)]:
            po.state = state
            self.assertEqual(self._refresh().service_po_ordered_total, total)

    def test_only_service_product_lines(self):
        po = self._po()
        product = self.env['product.product'].create({'name': 'Material', 'detailed_type': 'consu'})
        po.order_line[1].product_id = product
        self.env['purchase.order.line'].create({
            'order_id': po.id, 'display_type': 'line_note', 'name': 'Not a service',
            'product_qty': 0,
        })
        self.assertEqual(self.sheet.service_po_line_ids, po.order_line[:1])
        self.assertEqual(self.sheet.service_po_ordered_total, 100)

    def test_link_precedence_and_no_project_wide_fallback(self):
        po = self._po()
        line = po.order_line[0]
        line.job_cost_sheet_id = self.other_sheet
        self.assertEqual(self.sheet.service_po_line_ids, po.order_line[1:])
        self.assertEqual(self.other_sheet.service_po_line_ids, line)
        line.job_cost_sheet_id = False  # Cost-line ownership precedes header.
        self.assertIn(line, self._refresh().service_po_line_ids)
        line.job_cost_line_id = False  # Header-only legacy line.
        self.assertIn(line, self._refresh().service_po_line_ids)
        po.job_cost_sheet_id = False
        po.project_id = self.project
        self.assertNotIn(line, self._refresh().service_po_line_ids)

    def test_allocations_override_direct_links_and_context_isolated(self):
        po = self._po(descriptions=('Pooled service',), prices=(100,))
        line = po.order_line
        line.product_qty = 10
        self._allocate(line, self.sheet, 2)
        self._allocate(line, self.sheet, 3)
        self._allocate(line, self.other_sheet, 5)
        self.assertEqual(self.sheet.service_po_line_ids, line)
        self.assertEqual(self.sheet.service_po_ordered_total, 500)
        self.assertEqual(self.other_sheet.service_po_ordered_total, 500)
        self.assertEqual(line.with_context(service_job_cost_sheet_id=self.sheet.id).service_jcs_qty, 5)
        self.assertEqual(line.with_context(service_job_cost_sheet_id=self.other_sheet.id).service_jcs_amount, 500)
        self.assertEqual(line.service_jcs_amount, 0)

    def test_allocated_elsewhere_and_zero_ordered_warning(self):
        line = self._po(descriptions=('Allocated',), prices=(100,)).order_line
        self._allocate(line, self.other_sheet, 1)
        self.assertFalse(self.sheet.service_po_line_ids)
        line.product_qty = 0
        self.assertTrue(self.other_sheet.service_po_warning)
        self.assertEqual(self.other_sheet.service_po_ordered_total, 0)
        self.assertTrue(line.with_context(
            service_job_cost_sheet_id=self.other_sheet.id).service_jcs_invalid)

    def test_currency_conversion_uses_po_date(self):
        foreign = self.env['res.currency'].create({
            'name': 'XSP', 'symbol': 'S', 'rounding': 0.01,
            'rate_ids': [fields.Command.create({
                'name': '2026-01-01', 'rate': 2, 'company_id': self.env.company.id,
            }), fields.Command.create({
                'name': '2026-02-01', 'rate': 4, 'company_id': self.env.company.id,
            })],
        })
        po = self._po(descriptions=('Foreign',), prices=(100,), currency_id=foreign.id)
        self._po(descriptions=('Domestic',), prices=(25,))
        expected = foreign._convert(100, self.sheet.currency_id, self.env.company, '2026-01-15')
        self.assertEqual(self.sheet.service_po_ordered_total, expected + 25)
        contextual = po.order_line.with_context(service_job_cost_sheet_id=self.sheet.id)
        self.assertEqual(contextual.service_jcs_subtotal, 100)
        self.assertEqual(contextual.service_jcs_amount, expected)

    def test_purchase_rules_and_sheet_access(self):
        po = self._po()
        self.env['ir.rule'].create({
            'name': 'Hide service PO fixture',
            'model_id': self.env['ir.model']._get_id('purchase.order.line'),
            'domain_force': "[('id', 'not in', %s)]" % po.order_line.ids,
        })
        sheet = self.sheet.with_user(self.buyer)
        self.assertFalse(sheet.service_po_line_ids)
        self.assertEqual(sheet.service_po_ordered_total, 0)
        with self.assertRaises(AccessError):
            po.order_line[0].with_user(self.buyer).action_open_service_po()
        self.env['ir.rule'].create({
            'name': 'Hide service sheet fixture',
            'model_id': self.env['ir.model']._get_id('job.cost.sheet'),
            'domain_force': "[('id', '!=', %d)]" % self.sheet.id,
        })
        with self.assertRaises(AccessError):
            sheet._get_service_po_values()

    def test_hidden_allocations_do_not_charge_full_po(self):
        line = self._po(descriptions=('Restricted allocation',), prices=(100,)).order_line
        allocation = self._allocate(line, self.sheet, 0.5)
        self.env['ir.rule'].create({
            'name': 'Hide allocation fixture',
            'model_id': self.env['ir.model']._get_id('purchase.allocation'),
            'domain_force': "[('id', '!=', %d)]" % allocation.id,
        })
        sheet = self.sheet.with_user(self.buyer)
        self.assertFalse(sheet.service_po_line_ids)
        self.assertEqual(sheet.service_po_ordered_total, 0)

    def test_subtotal_excludes_tax(self):
        line = self._po(descriptions=('Taxed service',), prices=(100,)).order_line
        tax = self.env['account.tax'].create({
            'name': 'Service test tax', 'amount': 7, 'type_tax_use': 'purchase',
        })
        line.taxes_id = tax
        self.assertEqual(line.price_total, 107)
        self.assertEqual(self.sheet.service_po_ordered_total, 100)

    def test_company_filter_even_with_multiple_allowed_companies(self):
        company = self.env['res.company'].create({'name': 'Service PO other company'})
        po = self._po(descriptions=('Other company',), prices=(100,),
                      company_id=company.id)
        sheet = self.sheet.with_context(allowed_company_ids=[self.env.company.id, company.id])
        self.assertNotIn(po.order_line, sheet.service_po_line_ids)

    def test_confirm_auto_links_direct_service_line_to_labour(self):
        # No job_cost_sheet_id on the PO header at create time, so the
        # pre-existing (unrelated) material auto-link in
        # PurchaseOrderLine.create() never fires; job_cost_sheet_id is set
        # on the line afterwards, simulating a header link added post-hoc.
        po = self._po(descriptions=('Install wall labour',), prices=(500,), job_cost_sheet_id=False)
        po.state = 'draft'
        line = po.order_line[0]
        line.job_cost_sheet_id = self.sheet.id
        self.assertFalse(line.job_cost_line_id)
        po.button_confirm()
        self.assertTrue(line.job_cost_line_id)
        self.assertEqual(line.job_cost_line_id.cost_type, 'labour')
        self.assertEqual(line.job_cost_line_id.cost_sheet_id, self.sheet)
        self.assertEqual(self.sheet.total_labour_cost, 0)
        # Actual cost is bill-only since 2026-09-12 - confirming a PO is a
        # commitment, not yet an actual cost until a vendor bill posts.
        self.assertEqual(self.sheet.actual_labour_cost, 0)

    def test_allocation_created_after_confirm_auto_links_single_sheet(self):
        po = self._po(descriptions=('Pooled labour',), prices=(100,), job_cost_sheet_id=False)
        line = po.order_line[0]
        line.product_qty = 5
        self.assertFalse(line.job_cost_line_id)
        self._allocate(line, self.sheet, 5)
        self.assertTrue(line.job_cost_line_id)
        self.assertEqual(line.job_cost_line_id.cost_type, 'labour')
        # Actual cost is bill-only since 2026-09-12 - a PO commitment
        # (even allocated/confirmed) isn't actual until a bill posts.
        self.assertEqual(self._refresh().actual_labour_cost, 0)

    def test_split_allocation_does_not_auto_link(self):
        po = self._po(descriptions=('Split labour',), prices=(100,), job_cost_sheet_id=False)
        line = po.order_line[0]
        line.product_qty = 10
        self._allocate(line, self.sheet, 5)
        self._allocate(line, self.other_sheet, 5)
        self.assertFalse(line.job_cost_line_id)
        self.assertEqual(self.sheet.service_po_ordered_total, 500)
        self.assertEqual(self.other_sheet.service_po_ordered_total, 500)

    def test_manual_job_cost_line_not_overwritten(self):
        # A job_cost_line_id our code didn't create (no source_po_line_id
        # pointing back at this PO line) must never be touched or reassigned.
        po = self._po(descriptions=('Manually linked',), prices=(100,), job_cost_sheet_id=False)
        line = po.order_line[0]
        manual_line = self.env['job.cost.line'].create({
            'cost_sheet_id': self.other_sheet.id, 'cost_type': 'labour',
            'product_id': self.product.id, 'name': 'Manual labour line',
        })
        line.job_cost_line_id = manual_line.id
        line_count_before = self.env['job.cost.line'].search_count([])
        line._auto_link_labour_cost_line()
        self.assertEqual(line.job_cost_line_id, manual_line)
        self.assertEqual(self.env['job.cost.line'].search_count([]), line_count_before)

    def test_tab_is_readonly_and_opens_po(self):
        result = self.sheet.with_user(self.buyer).get_view(view_type='form')
        arch = etree.fromstring(result['arch'])
        tree = arch.xpath("//page[@name='labour_costs']//field[@name='service_po_line_ids']/tree")[0]
        self.assertEqual([tree.get(key) for key in ('create', 'edit', 'delete')], ['0'] * 3)
        po = self._po()
        action = po.order_line[0].with_user(self.buyer).action_open_service_po()
        self.assertEqual((action['res_model'], action['res_id']), ('purchase.order', po.id))

    def test_same_product_different_description_link_distinct_cost_lines(self):
        # Regression for a prod bug: BOQ correctly creates one job.cost.line
        # per BOQ item even when several share a product, but the PO
        # auto-link fallback used to match by product only and collapsed
        # every one of them onto whichever cost line it found first.
        door_line = self.env['job.cost.line'].create({
            'cost_sheet_id': self.sheet.id, 'cost_type': 'labour',
            'product_id': self.product.id, 'name': 'Door labour',
        })
        window_line = self.env['job.cost.line'].create({
            'cost_sheet_id': self.sheet.id, 'cost_type': 'labour',
            'product_id': self.product.id, 'name': 'Window labour',
        })
        po = self._po(descriptions=('Door labour', 'Window labour'), prices=(100, 200),
                       job_cost_sheet_id=False)
        po.order_line.job_cost_sheet_id = self.sheet.id
        po.order_line._auto_link_labour_cost_line()
        door_po_line, window_po_line = po.order_line
        self.assertEqual(door_po_line.job_cost_line_id, door_line)
        self.assertEqual(window_po_line.job_cost_line_id, window_line)
        self.assertNotEqual(door_po_line.job_cost_line_id, window_po_line.job_cost_line_id)

    def test_create_fallback_matches_description_and_sets_labour_type(self):
        # Same regression as above but for PurchaseOrderLine.create()'s own
        # "auto-link to job cost sheet" fallback (job_cost_sheet_id set at
        # create time), which used to match by product only and hardcode
        # cost_type='material' even for service products.
        door_line = self.env['job.cost.line'].create({
            'cost_sheet_id': self.sheet.id, 'cost_type': 'labour',
            'product_id': self.product.id, 'name': 'Door labour',
        })
        po = self._po(descriptions=('Door labour', 'New window labour'), prices=(100, 200))
        door_po_line, window_po_line = po.order_line
        self.assertEqual(door_po_line.job_cost_line_id, door_line)
        self.assertNotEqual(window_po_line.job_cost_line_id, door_line)
        self.assertEqual(window_po_line.job_cost_line_id.cost_type, 'labour')
        self.assertEqual(window_po_line.job_cost_line_id.name, 'New window labour')
