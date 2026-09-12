from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestBOQSyncVisibility(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['project.project'].create({
            'name': 'BOQ sync visibility', 'company_id': cls.env.company.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'BOQ sync material', 'detailed_type': 'consu',
        })
        cls.sheet = cls.env['job.cost.sheet'].create({'project_id': cls.project.id})
        cls.boq_synced = cls.env['boq.boq'].create({
            'title': 'Synced BOQ', 'project_id': cls.project.id,
            'job_cost_sheet_id': cls.sheet.id, 'state': 'approved',
            'line_ids': [fields.Command.create({
                'product_id': cls.product.id, 'description': 'Synced line',
                'quantity': 10, 'unit_cost': 25, 'uom_id': cls.product.uom_id.id,
            })],
        })
        cls.boq_unsynced = cls.env['boq.boq'].create({
            'title': 'Unsynced BOQ', 'project_id': cls.project.id,
            'job_cost_sheet_id': cls.sheet.id, 'state': 'approved',
            'line_ids': [fields.Command.create({
                'product_id': cls.product.id, 'description': 'Unsynced line',
                'quantity': 5, 'unit_cost': 40, 'uom_id': cls.product.uom_id.id,
            })],
        })

    def test_boq_ids_lists_every_linked_boq(self):
        self.assertEqual(self.sheet.boq_count, 2)
        self.assertEqual(self.sheet.boq_ids, self.boq_synced | self.boq_unsynced)

    def test_unsynced_boq_hides_budget_and_is_flagged(self):
        self.boq_synced.action_create_job_cost_lines()
        # Only the synced BOQ's baseline (10 * 25 = 250) is reflected; the
        # unsynced BOQ's 5 * 40 = 200 budget is not yet materialized.
        self.assertEqual(self.sheet.boq_total_cost, 250)
        self.assertTrue(self.sheet.has_unsynced_boq)

    def test_syncing_all_boqs_clears_the_flag(self):
        self.boq_synced.action_create_job_cost_lines()
        self.boq_unsynced.action_create_job_cost_lines()
        self.assertEqual(self.sheet.boq_total_cost, 450)
        self.assertFalse(self.sheet.has_unsynced_boq)

    def test_approve_auto_syncs_job_cost_lines(self):
        boq = self.env['boq.boq'].create({
            'title': 'Approve-time sync', 'project_id': self.project.id,
            'job_cost_sheet_id': self.sheet.id, 'state': 'draft',
            'line_ids': [fields.Command.create({
                'product_id': self.product.id, 'description': 'Auto-synced line',
                'quantity': 4, 'unit_cost': 10, 'uom_id': self.product.uom_id.id,
            })],
        })
        self.assertFalse(boq.line_ids.cost_line_ids)
        boq.action_approve()
        self.assertTrue(boq.line_ids.cost_line_ids)
        self.assertEqual(boq.line_ids.cost_line_ids.boq_total_cost, 40)

    def test_approve_does_not_raise_without_products_or_sheet(self):
        no_products = self.env['boq.boq'].create({
            'title': 'No product lines', 'project_id': self.project.id,
            'job_cost_sheet_id': self.sheet.id, 'state': 'draft',
        })
        no_sheet = self.env['boq.boq'].create({
            'title': 'No cost sheet', 'project_id': self.project.id, 'state': 'draft',
            'line_ids': [fields.Command.create({
                'product_id': self.product.id, 'description': 'Orphan line',
                'quantity': 1, 'unit_cost': 5, 'uom_id': self.product.uom_id.id,
            })],
        })
        (no_products | no_sheet).action_approve()
        self.assertEqual((no_products | no_sheet).mapped('state'), ['approved', 'approved'])
