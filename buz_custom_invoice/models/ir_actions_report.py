from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """
        Override to use sudo() for buz_custom_invoice reports to bypass multi-company restrictions.
        This allows users to view/print Invoices regardless of their current company context.
        """
        # Check if this is a report from buz_custom_invoice
        buz_invoice_reports = [
            'buz_custom_invoice.report_invoice',
            'buz_custom_invoice.report_invoice_tax',
            'buz_custom_invoice.report_credit_note',
            'buz_custom_invoice.report_vendor_credit_note',
            'buz_custom_invoice.report_ecommerce_receipt_report',
            'buz_custom_invoice.report_payment_receipt_modern',
            'buz_custom_invoice.action_report_invoice',
            'buz_custom_invoice.action_report_invoice_tax',
            'buz_custom_invoice.action_report_credit_note',
            'buz_custom_invoice.action_report_cerdit_notevendor_credit_note',
            'buz_custom_invoice.action_report_ecommerce_receipt_report',
            'buz_custom_invoice.action_report_payment_receipt_modern',
            'buz_accounting_addon.action_report_buz_accounting_addon',
        ]

        if report_ref in buz_invoice_reports:
            # Use sudo() to bypass multi-company restrictions
            return super(IrActionsReport, self.sudo())._render_qweb_pdf(
                report_ref, res_ids=res_ids, data=data
            )

        # For all other reports, use standard behavior
        return super(IrActionsReport, self)._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data
        )
