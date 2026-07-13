from odoo.tests.common import TransactionCase


class TestAccountReceiptReport(TransactionCase):
    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({
            'name': 'Report Test Customer',
            'customer_rank': 1,
        })
        self.receipt = self.env['account.receipt'].create({
            'partner_id': self.partner.id,
        })

    def test_legacy_report_values_use_sudo(self):
        report = self.env['report.buz_accounting_addon.report_buz_accounting_addon']
        values = report._get_report_values(self.receipt.ids)

        self.assertEqual(values['doc_ids'], self.receipt.ids)
        self.assertEqual(values['doc_model'], 'account.receipt')
        self.assertEqual(values['docs'].ids, self.receipt.ids)
        self.assertEqual(values['docs'].env.uid, 1)

