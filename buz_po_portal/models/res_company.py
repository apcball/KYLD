from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    po_reviewer_ids = fields.Many2many('res.users', 'res_company_po_reviewer_rel', 'company_id', 'user_id', string='Default PO Reviewers')
    po_approver_ids = fields.Many2many('res.users', 'res_company_po_approver_rel', 'company_id', 'user_id', string='PO Approvers (Standard)')
    po_approver_limit = fields.Monetary(string='PO Approval Limit', default=50000.0)
    po_approver_above_limit_id = fields.Many2one('res.users', string='PO Approver (Above Limit)')
