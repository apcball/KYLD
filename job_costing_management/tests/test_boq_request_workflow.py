from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged('post_install', '-at_install')
class TestBOQRequestWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env['project.project'].create({
            'name': 'BOQ request test', 'company_id': cls.env.company.id,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'BOQ request material', 'detailed_type': 'consu',
        })
        cls.sheet = cls.env['job.cost.sheet'].create({'project_id': cls.project.id})
        cls.boq = cls.env['boq.boq'].create({
            'title': 'Request workflow', 'project_id': cls.project.id,
            'job_cost_sheet_id': cls.sheet.id, 'state': 'approved',
            'line_ids': [fields.Command.create({
                'product_id': cls.product.id, 'description': description,
                'quantity': 10, 'unit_cost': 25, 'uom_id': cls.product.uom_id.id,
            }) for description in ('Foundation', 'Roof')],
        })

    def _wizard(self, boq=None, source_line=None):
        boq = boq or self.boq
        action = (source_line.action_create_requisition() if source_line
                  else boq.action_create_material_requisition())
        return Form(boq.env['boq.material.requisition.wizard'].with_context(
            action['context'])).save()

    def test_one_page_selection_and_deselection(self):
        wizard = self._wizard()
        self.assertFalse(wizard.line_ids.filtered('selected'))
        self.assertEqual(len(wizard.line_ids), 2)
        first, second = wizard.line_ids
        first.write({'selected': True, 'requested_quantity': 3})
        second.write({'selected': True, 'requested_quantity': 4})
        self.assertEqual(wizard.selected_total_cost, 175)
        second.selected = False
        self.assertEqual(wizard.total_lines_count, 1)
        self.assertEqual(wizard.selected_total_cost, 75)
        action = wizard.action_create_requisition()
        requisition = self.env['material.requisition'].browse(action['res_id'])
        self.assertEqual(requisition.state, 'draft')
        self.assertEqual(requisition.line_ids.boq_line_id, first.boq_line_id)
        self.assertEqual(requisition.line_ids.quantity, 3)
        self.assertEqual(requisition.project_id, self.project)
        self.assertEqual(requisition.job_cost_sheet_id, self.sheet)
        self.assertEqual(requisition.company_id, self.boq.company_id)
        self.assertEqual(wizard.action_create_requisition()['res_id'], requisition.id)
        self.assertEqual(len(self.boq.line_ids.requisition_line_ids), 1)

    def test_line_entry_uses_same_wizard_and_cost_link(self):
        self.boq.action_create_job_cost_lines()
        source = self.boq.line_ids[1]
        wizard = self._wizard(source_line=source)
        self.assertEqual(wizard.line_ids.filtered('selected').boq_line_id, source)
        wizard.action_create_requisition()
        self.assertEqual(wizard.requisition_id.line_ids.job_cost_line_id,
                         source.cost_line_ids)

    def test_cancel_does_not_create_requisition(self):
        wizard = self._wizard()
        wizard.line_ids[0].selected = True
        wizard.unlink()
        self.assertFalse(self.boq.line_ids.requisition_line_ids)

    def test_empty_selection_and_invalid_quantities(self):
        wizard = self._wizard()
        with self.assertRaises(ValidationError):
            wizard.action_create_requisition()
        line = wizard.line_ids[0]
        line.selected = True
        for quantity in (0, -1):
            line.requested_quantity = quantity
            with self.assertRaises(ValidationError):
                wizard.action_create_requisition()
        self.assertFalse(wizard.requisition_id)

    def test_unselected_invalid_quantity_is_ignored(self):
        wizard = self._wizard(source_line=self.boq.line_ids[0])
        wizard.line_ids.filtered(lambda line: not line.selected).requested_quantity = -1
        wizard.action_create_requisition()
        self.assertEqual(len(wizard.requisition_id.line_ids), 1)

    def test_over_quantity_warns_but_is_allowed(self):
        wizard = self._wizard(source_line=self.boq.line_ids[0])
        line = wizard.line_ids.filtered('selected')
        line.requested_quantity = 12
        self.assertTrue(line.has_warning)
        self.assertIn('warning', line._onchange_requested_quantity())
        wizard.action_create_requisition()
        self.assertEqual(wizard.requisition_id.line_ids.quantity, 12)

    def test_stale_remaining_requires_review(self):
        source = self.boq.line_ids[0]
        waiting = self._wizard(source_line=source)
        other = self._wizard(source_line=source)
        other.line_ids.filtered('selected').requested_quantity = 2
        other.action_create_requisition()
        action = waiting.action_create_requisition()
        self.assertEqual(action['tag'], 'display_notification')
        self.assertFalse(waiting.requisition_id)
        self.assertEqual(waiting.line_ids.filtered('selected').remaining_quantity, 8)
        waiting.line_ids.filtered('selected').requested_quantity = 3
        waiting.action_create_requisition()
        self.assertEqual(waiting.requisition_id.line_ids.quantity, 3)

    def test_state_checked_on_open_and_confirmation(self):
        wizard = self._wizard(source_line=self.boq.line_ids[0])
        for state in ('draft', 'cancelled'):
            self.boq.state = state
            with self.assertRaises(ValidationError):
                self._wizard()
            with self.assertRaises(ValidationError):
                wizard.action_create_requisition()
        self.boq.state = 'locked'
        wizard.action_create_requisition()
        self.assertTrue(wizard.requisition_id)

    def test_foreign_boq_line_is_rejected(self):
        wizard = self._wizard(source_line=self.boq.line_ids[0])
        other_boq = self.env['boq.boq'].create({
            'title': 'Other BOQ', 'project_id': self.project.id,
        })
        foreign = self.boq.line_ids[0].copy({'boq_id': other_boq.id})
        wizard.line_ids.filtered('selected').boq_line_id = foreign
        with self.assertRaises(ValidationError):
            wizard.action_create_requisition()

    def test_changed_product_or_unit_requires_reopening(self):
        wizard = self._wizard(source_line=self.boq.line_ids[0])
        wizard.line_ids.filtered('selected').uom_id = self.env.ref('uom.product_uom_dozen')
        with self.assertRaises(ValidationError):
            wizard.action_create_requisition()

    def test_cost_creation_is_repeatable_and_preserves_baseline(self):
        # A manually entered row for the same product must never be hijacked.
        manual = self.env['job.cost.line'].create({
            'cost_sheet_id': self.sheet.id, 'product_id': self.product.id,
            'name': 'Manual budget', 'cost_type': 'material',
            'planned_qty': 7, 'unit_cost': 11, 'uom_id': self.product.uom_id.id,
        })
        first = self.boq.action_create_job_cost_lines()
        linked = self.boq.line_ids.cost_line_ids
        self.assertEqual(len(linked), 2)
        self.assertFalse(manual.boq_line_id)
        self.boq.line_ids[0].write({'quantity': 15, 'unit_cost': 30})
        second = self.boq.action_create_job_cost_lines()
        self.assertEqual(first['params']['next']['domain'],
                         second['params']['next']['domain'])
        self.assertEqual(self.boq.line_ids.cost_line_ids, linked)
        self.assertEqual(linked.mapped('boq_qty'), [10, 10])
        self.assertEqual(linked.mapped('boq_unit_cost'), [25, 25])
        self.assertEqual(manual.planned_qty, 7)

    def test_ambiguous_cost_link_is_rejected(self):
        self.boq.action_create_job_cost_lines()
        source = self.boq.line_ids[0]
        source.cost_line_ids.copy()
        wizard = self._wizard(source_line=source)
        with self.assertRaises(ValidationError):
            wizard.action_create_requisition()
        with self.assertRaises(ValidationError):
            self.boq.action_create_job_cost_lines()

    def test_cross_company_context_is_rejected(self):
        company = self.env['res.company'].create({'name': 'BOQ other company'})
        self.boq.company_id = company
        with self.assertRaises(ValidationError):
            self._wizard()
        with self.assertRaises(ValidationError):
            self.boq.with_context(allowed_company_ids=[self.env.company.id, company.id]).action_create_material_requisition()

    def test_user_and_manager_can_request_without_sudo(self):
        for role in ('user', 'manager'):
            user = new_test_user(
                self.env, login='boq_request_' + role,
                groups='job_costing_management.group_job_costing_' + role +
                       ',job_costing_management.group_material_requisition_' + role)
            wizard = self._wizard(boq=self.boq.with_user(user))
            # Form uses its own environment; explicitly use the actor below too.
            wizard = wizard.with_user(user)
            wizard.line_ids[0].write({'selected': True, 'requested_quantity': 1})
            wizard.action_create_requisition()
            self.assertEqual(wizard.requisition_id.create_uid, user)

    def test_other_user_cannot_confirm_owned_wizard(self):
        user = new_test_user(self.env, login='boq_other_user',
                             groups='job_costing_management.group_job_costing_user')
        wizard = self._wizard()
        with self.assertRaises(AccessError):
            wizard.with_user(user).action_create_requisition()

    def test_refresh_preserves_totals_and_respects_state(self):
        self.boq.action_create_job_cost_lines()
        before = (self.sheet.total_cost, self.sheet.boq_total_cost)
        with patch.object(type(self.sheet), 'action_sync_actual_costs') as sync:
            self.sheet.action_update_costs()
            sync.assert_not_called()
            self.sheet.state = 'approved'
            self.sheet.action_update_costs()
            sync.assert_called_once()
        self.assertEqual((self.sheet.total_cost, self.sheet.boq_total_cost), before)

    def test_inherited_views_and_navigation(self):
        for model, view_xmlid in (
            ('material.requisition', 'view_material_requisition_form'),
            ('job.cost.sheet', 'view_job_cost_sheet_form'),
            ('boq.boq', 'view_boq_form'),
        ):
            view = self.env.ref('job_costing_management.' + view_xmlid)
            self.assertTrue(self.env[model].get_view(view.id, 'form')['arch'])
        self.assertEqual(
            self.env.ref('job_costing_management.menu_job_projects').action,
            self.env.ref('project.open_view_project_all'))
        self.assertFalse(self.env.ref('job_costing_management.menu_projects').active)
        self.assertEqual(
            self.env.ref('job_costing_management.menu_boq_templates').parent_id,
            self.env.ref('job_costing_management.menu_job_configuration'))
