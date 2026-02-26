# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools


class WeeklyBudgetReport(models.Model):
    _name = 'weekly.budget.report'
    _description = 'Weekly Budget Analysis Report'
    _auto = False
    _order = 'date desc'

    budget_line_id = fields.Many2one('weekly.budget.line', string='Budget Week', readonly=True)
    plan_id = fields.Many2one('weekly.budget.plan', string='Budget Plan', readonly=True)
    document_type = fields.Selection([
        ('po', 'Purchase Order'),
        ('pr', 'Employee PR'),
        ('mr', 'Material Requisition'),
    ], string='Document Type', readonly=True)
    name = fields.Char(string='Document Reference', readonly=True)
    res_model = fields.Char(string='Resource Model', readonly=True)
    res_id = fields.Integer(string='Resource ID', readonly=True)
    amount = fields.Float(string='Amount', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    state = fields.Char(string='Status', readonly=True)
    is_confirmed = fields.Boolean(string='Is Confirmed/Actual', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH document_lines AS (
                    -- PO Lines
                    SELECT 
                        'po' as document_type,
                        po.name as name,
                        'purchase.order' as res_model,
                        po.id as res_id,
                        pol.price_subtotal as amount,
                        pol.date_planned::date as date,
                        po.state as state,
                        po.company_id as company_id,
                        (po.state IN ('purchase', 'done')) as is_confirmed
                    FROM purchase_order_line pol
                    JOIN purchase_order po ON pol.order_id = po.id
                    WHERE po.state NOT IN ('cancel')

                    UNION ALL

                    -- Employee PR Lines
                    SELECT 
                        'pr' as document_type,
                        pr.name as name,
                        'employee.purchase.requisition' as res_model,
                        pr.id as res_id,
                        rol.price_subtotal as amount,
                        COALESCE(pr.requisition_deadline, pr.request_date) as date,
                        pr.state as state,
                        pr.company_id as company_id,
                        FALSE as is_confirmed
                    FROM requisition_order rol
                    JOIN employee_purchase_requisition pr ON rol.requisition_product_id = pr.id
                    WHERE pr.state NOT IN ('cancel', 'reject')

                    UNION ALL

                    -- Material Requisition Lines
                    SELECT 
                        'mr' as document_type,
                        mr.name as name,
                        'material.requisition' as res_model,
                        mr.id as res_id,
                        mrl.total_cost as amount,
                        mr.required_date as date,
                        mr.state as state,
                        mr.company_id as company_id,
                        FALSE as is_confirmed
                    FROM material_requisition_line mrl
                    JOIN material_requisition mr ON mrl.requisition_id = mr.id
                    WHERE mr.state NOT IN ('cancel', 'reject')
                )
                SELECT
                    row_number() OVER () as id,
                    dl.document_type,
                    dl.name,
                    dl.res_model,
                    dl.res_id,
                    dl.amount,
                    dl.date,
                    dl.state,
                    dl.company_id,
                    dl.is_confirmed,
                    wbl.id as budget_line_id,
                    wbl.plan_id as plan_id
                FROM document_lines dl
                JOIN weekly_budget_line wbl ON 
                    dl.date >= wbl.date_from AND 
                    dl.date <= wbl.date_to
                JOIN weekly_budget_plan wbp ON wbl.plan_id = wbp.id
                WHERE (wbp.all_companies = TRUE OR wbp.company_id = dl.company_id)
                  AND wbp.state = 'confirmed'
            )
        """ % self._table)

    def action_open_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }
