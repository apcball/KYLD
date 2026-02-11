from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    po_reviewer_ids = fields.Many2many(
        'res.users', 
        related='company_id.po_reviewer_ids', 
        string='Default PO Reviewers', 
        readonly=False
    )
    po_approver_ids = fields.Many2many(
        'res.users', 
        related='company_id.po_approver_ids', 
        string='PO Approvers (Standard)', 
        readonly=False
    )
    po_approver_limit = fields.Monetary(
        related='company_id.po_approver_limit', 
        string='PO Approval Limit', 
        currency_field='currency_id', 
        readonly=False
    )
    po_approver_above_limit_id = fields.Many2one(
        'res.users', 
        related='company_id.po_approver_above_limit_id', 
        string='PO Approver (Above Limit)', 
        readonly=False
    )
