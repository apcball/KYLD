from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    partner_code = fields.Char(
        string='Partner Code',
        readonly=True,
        copy=False,
        index=True,
        help="Auto-generated code: Customer -> Cxxxxx, Vendor -> Vxxxxx."
    )
    old_code_partner = fields.Char(string='Old Code Partner')
    office = fields.Char(string='Office')
    partner_group = fields.Char(string='Partner Group')
    partner_type = fields.Char(string='Partner Type')

    _sql_constraints = [
        ('partner_code_uniq', 'unique(partner_code)', 'Partner Code must be unique!')
    ]

    def _get_target_sequence_code(self, vals=None):
        self.ensure_one()
        vals = vals or {}
        supplier_rank = vals.get('supplier_rank', self.supplier_rank)
        customer_rank = vals.get('customer_rank', self.customer_rank)
        if supplier_rank or self.env.context.get('default_supplier_rank'):
            return 'custom_partner_code.vendor'
        if customer_rank or self.env.context.get('default_customer_rank'):
            return 'custom_partner_code.customer'
        return False

    def _assign_partner_code_if_needed(self, vals=None):
        for partner in self:
            if not partner.partner_code:
                seq_code = partner._get_target_sequence_code(vals=vals or {})
                if seq_code:
                    code = self.env['ir.sequence'].next_by_code(seq_code)
                    if code:
                        self.env.cr.execute(
                            "UPDATE res_partner SET partner_code = %s WHERE id = %s",
                            [code, partner.id]
                        )

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        for partner, vals in zip(partners, vals_list):
            partner._assign_partner_code_if_needed(vals=vals)
        return partners

    def write(self, vals):
        res = super().write(vals)
        self._assign_partner_code_if_needed(vals=vals)
        return res
