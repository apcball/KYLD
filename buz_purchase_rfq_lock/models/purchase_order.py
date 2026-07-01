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

    def _buz_is_allowed_rfq_source(self, vals):
        """Allow RFQ creation only from approved source documents or trusted flows."""
        from_procurement = self.env.context.get('from_procurement')
        allow_create_rfq = self.env.context.get('allow_create_rfq')
        is_admin = self.env.user.has_group('base.group_system')

        is_from_pr = bool(vals.get('requisition_order')) or bool(vals.get('pr_number'))
        is_from_mr = bool(vals.get('material_requisition_id'))
        is_from_pool = bool(vals.get('procurement_pool_id'))

        return bool(
            from_procurement
            or allow_create_rfq
            or is_admin
            or is_from_pr
            or is_from_mr
            or is_from_pool
        )

    def _buz_default_source_type(self, vals):
        """Set a stable source marker for downstream reporting and debugging."""
        from_procurement = self.env.context.get('from_procurement')
        is_admin = self.env.user.has_group('base.group_system')

        if vals.get('buz_source_type'):
            return vals['buz_source_type']
        if vals.get('requisition_order') or vals.get('pr_number'):
            return 'pr'
        if vals.get('material_requisition_id'):
            return 'mr'
        if vals.get('procurement_pool_id') or from_procurement:
            return 'auto'
        if is_admin:
            return 'manual_allowed'
        return False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not self._buz_is_allowed_rfq_source(vals):
                raise UserError(_("You are not allowed to create RFQ manually. Please use Purchase Request or approved process."))

            if not vals.get('buz_source_type'):
                vals['buz_source_type'] = self._buz_default_source_type(vals)

            if not vals.get('buz_source_type'):
                raise UserError(_("Source Type is required for RFQ creation."))

        return super(PurchaseOrder, self).create(vals_list)

    def copy(self, default=None):
        default = default or {}
        default['buz_source_type'] = 'manual_allowed'
        return super(PurchaseOrder, self.with_context(allow_create_rfq=True)).copy(default)


