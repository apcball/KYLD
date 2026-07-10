# -*- coding: utf-8 -*-
from odoo import models, api


class AccountPaymentVoucherReportPDF(models.AbstractModel):
    _name = 'report.buz_accounting_addon.report_account_payment_voucher'
    _description = 'Payment Voucher PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.payment.voucher'].sudo().browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'account.payment.voucher',
            'docs': docs,
            'data': data,
        }
