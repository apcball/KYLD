# -*- coding: utf-8 -*-
from odoo import fields
from odoo.tests.common import TransactionCase


class DashboardTestCase(TransactionCase):
    """Shared fixture builder: one company, one project, one job cost
    sheet with material/labour/overhead lines."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.currency = cls.company.currency_id

        product_template = cls.env['product.template'].create({
            'name': 'Dashboard Test Material',
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
            'uom_po_id': cls.env.ref('uom.product_uom_unit').id,
        })
        cls.product = product_template.product_variant_id

        cls.project = cls.env['project.project'].create({
            'name': 'Dashboard Test Project',
            'company_id': cls.company.id,
            'contract_amount': 1000000.0,
        })

    def _create_cost_sheet(self, project=None, state='approved',
                            material=(100.0, 10.0), labour=(50.0, 20.0),
                            overhead=(30.0, 5.0), date_start=None):
        """material/labour/overhead are (planned_qty, unit_cost) tuples."""
        project = project or self.project
        lines = []
        for cost_type, (qty, unit_cost) in (
            ('material', material), ('labour', labour), ('overhead', overhead),
        ):
            lines.append(fields.Command.create({
                'cost_type': cost_type,
                'name': '%s line' % cost_type,
                'product_id': self.product.id,
                'planned_qty': qty,
                'unit_cost': unit_cost,
            }))
        return self.env['job.cost.sheet'].create({
            'project_id': project.id,
            'company_id': self.company.id,
            'state': state,
            'date_start': date_start or fields.Date.today(),
            'material_cost_ids': [l for l in lines if l[2]['cost_type'] == 'material'],
            'labour_cost_ids': [l for l in lines if l[2]['cost_type'] == 'labour'],
            'overhead_cost_ids': [l for l in lines if l[2]['cost_type'] == 'overhead'],
        })
