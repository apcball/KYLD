from odoo import api, models


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    @api.model
    def _ensure_company_sequence(self, code, company):
        """Return a company-specific sequence for ``code``, copying the global
        template (company_id=False) on first use so each company gets its own
        independent number range."""
        self = self.sudo()
        seq = self.search([('code', '=', code), ('company_id', '=', company.id)], limit=1)
        if seq:
            return seq
        template = self.search([('code', '=', code), ('company_id', '=', False)], limit=1)
        if not template:
            return self.env['ir.sequence']
        return template.copy({
            'company_id': company.id,
            'name': '%s (%s)' % (template.name, company.name),
            'number_next': 1,
            'number_next_actual': 1,
        })

    @api.model
    def next_by_code_company(self, code, company, sequence_date=None):
        """Draw the next number from a sequence scoped to ``company``.

        Creates the company sequence on demand by cloning the global template,
        so multi-company documents get independent numbering per company.
        Falls back to the standard global lookup when no company is given."""
        if not company:
            return self.next_by_code(code, sequence_date=sequence_date)
        self._ensure_company_sequence(code, company)
        return self.sudo().with_company(company).next_by_code(code, sequence_date=sequence_date)
