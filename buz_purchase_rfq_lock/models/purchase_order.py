from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    buz_source_type = fields.Selection(
        [
            ('pr', 'Purchase Request'),
            ('mr', 'Material Request'),
            ('auto', 'Auto Procurement'),
            ('manual_allowed', 'Manual (Special Permission)')
        ],
        string='Source Type',
        copy=False,
    )


    @api.model_create_multi
    def create(self, vals_list):
        from_procurement = self.env.context.get('from_procurement') 
        allow_create_rfq = self.env.context.get('allow_create_rfq')
        is_admin = self.env.user.has_group('base.group_system')

        for vals in vals_list:
            is_from_pr = bool(vals.get('requisition_order')) or bool(vals.get('pr_number'))
            is_from_mr = bool(vals.get('material_requisition_id'))

            if not (from_procurement or allow_create_rfq or is_admin or is_from_pr or is_from_mr):
                raise UserError(_("You are not allowed to create RFQ manually. Please use Purchase Request or approved process."))
            
            if not vals.get('buz_source_type'):
                if is_from_pr:
                    vals['buz_source_type'] = 'pr'
                elif is_from_mr:
                    vals['buz_source_type'] = 'mr'
                elif from_procurement:
                    vals['buz_source_type'] = 'auto'
                elif is_admin:
                    vals['buz_source_type'] = 'manual_allowed'
                    
            if not vals.get('buz_source_type'):
                raise UserError(_("Source Type is required for RFQ creation."))

        return super(PurchaseOrder, self).create(vals_list)

    def copy(self, default=None):
        default = default or {}
        default['buz_source_type'] = 'manual_allowed'
        return super(PurchaseOrder, self.with_context(allow_create_rfq=True)).copy(default)

    def buz_action_duplicate(self):
        self.ensure_one()
        new_rfq = self.copy()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': new_rfq.id,
            'view_mode': 'form',
            'target': 'current',
        }

