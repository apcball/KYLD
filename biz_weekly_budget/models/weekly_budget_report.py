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
    ], string='Document Type', readonly=True)
    name = fields.Char(string='Document Reference', readonly=True)
    res_model = fields.Char(string='Resource Model', readonly=True)
    res_id = fields.Integer(string='Resource ID', readonly=True)
    amount = fields.Float(string='Amount', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    state = fields.Char(string='Status', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () as id,
                    'po' as document_type,
                    po.name as name,
                    'purchase.order' as res_model,
                    po.id as res_id,
                    pol.price_subtotal as amount,
                    pol.date_planned::date as date,
                    po.state as state,
                    po.company_id as company_id,
                    wbl.id as budget_line_id,
                    wbl.plan_id as plan_id
                FROM purchase_order_line pol
                JOIN purchase_order po ON pol.order_id = po.id
                JOIN weekly_budget_line wbl ON 
                    pol.date_planned::date >= wbl.date_from AND 
                    pol.date_planned::date <= wbl.date_to
                JOIN weekly_budget_plan wbp ON wbl.plan_id = wbp.id
                WHERE po.state IN ('purchase', 'done')
                  AND (wbp.all_companies = TRUE OR wbp.company_id = po.company_id)
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

    def action_open_document(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self.res_model,
            'res_id': self.res_id,
            'view_mode': 'form',
            'target': 'current',
        }
