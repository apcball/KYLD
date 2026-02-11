from odoo import models


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        """
        Override to use sudo() for purchase.order reports to bypass multi-company restrictions.
        This allows users to view/print Purchase Orders regardless of their current company context.
        """
        # Check if this is a purchase order report from buz_po_portal
        if report_ref in ['buz_po_portal.report_purchaseorder_document_custom', 
                          'buz_po_portal.action_report_purchase_order_custom']:
            # Use sudo() to bypass multi-company restrictions
            return super(IrActionsReport, self.sudo())._render_qweb_pdf(
                report_ref, res_ids=res_ids, data=data
            )
        
        # For all other reports, use standard behavior
        return super(IrActionsReport, self)._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data
        )
