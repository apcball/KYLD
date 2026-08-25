# -*- coding: utf-8 -*-
"""Currency resolution and safe cross-currency aggregation.

Rule: amounts are never summed across currencies. Every monetary read_group
must include currency_id in groupby; each bucket is converted here to a
single base currency before being summed into a KPI.
"""
from odoo import fields as odoo_fields


class CurrencyResolver:

    def __init__(self, env, filters):
        self.env = env
        self.filters = filters
        self.base_currency = self._resolve_base_currency()
        self.rate_date = filters.date_to or odoo_fields.Date.today()
        self.warnings = []

    def _resolve_base_currency(self):
        if self.filters.currency_id:
            currency = self.env['res.currency'].browse(self.filters.currency_id)
            if currency.exists():
                return currency
        return self.env.company.currency_id

    def convert_grouped_amount(self, amount, currency_id, company):
        """Convert one read_group bucket's amount to the base currency.

        currency_id may be False (legacy rows with no currency set); those
        are treated as already being in the company currency and flagged.
        """
        if not amount:
            return 0.0
        if not currency_id:
            self.warnings.append(
                "Some records have no currency set; assumed company currency.")
            source_currency = company.currency_id
        else:
            source_currency = self.env['res.currency'].browse(currency_id)

        if source_currency == self.base_currency:
            return amount

        return source_currency._convert(
            amount, self.base_currency, company, self.rate_date)

    def as_meta(self):
        return {
            'currency': self.base_currency.name,
            'warnings': self.warnings,
        }
