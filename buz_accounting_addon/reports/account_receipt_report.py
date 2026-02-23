# -*- coding: utf-8 -*-
from odoo import models, api


class AccountReceiptReportPDF(models.AbstractModel):
    _name = 'report.buz_accounting_addon.account_receipt_report_preprint'
    _description = 'Account Receipt Preprint PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.receipt'].sudo().browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'account.receipt',
            'docs': docs,
            'data': data,
        }


class AccountPaymentVoucherReportPDF(models.AbstractModel):
    _name = 'report.buz_accounting_addon.report_account_payment_voucher'
    _description = 'Account Payment Voucher Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.payment.voucher'].sudo().browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'account.payment.voucher',
            'docs': docs,
            'data': data,
        }


class AccountReceiptVoucherReportPDF(models.AbstractModel):
    _name = 'report.buz_accounting_addon.report_account_receipt_voucher'
    _description = 'Account Receipt Voucher Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.receipt.voucher'].sudo().browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'account.receipt.voucher',
            'docs': docs,
            'data': data,
        }


class PaymentTransferReportPDF(models.AbstractModel):
    _name = 'report.buz_accounting_addon.report_payment_transfer'
    _description = 'Payment Transfer Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.bank.transfer'].sudo().browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'account.bank.transfer',
            'docs': docs,
            'data': data,
        }


class AccountReceiptReportMainPDF(models.AbstractModel):
    _name = 'report.buz_accounting_addon.report_buz_accounting_addon'
    _description = 'Main Account Receipt Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.receipt'].sudo().browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'account.receipt',
            'docs': docs,
            'data': data,
        }
