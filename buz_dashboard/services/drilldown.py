# -*- coding: utf-8 -*-
"""Helpers for record drill-down and Odoo deep-link generation, per the
'drilldown' / 'odoo_action' response fields used across every endpoint."""


def drilldown(model, res_id):
    if not res_id:
        return None
    return {
        'model': model,
        'res_id': res_id,
    }


def odoo_action(model, res_id, view_mode='form'):
    if not res_id:
        return None
    return {
        'type': 'ir.actions.act_window',
        'res_model': model,
        'res_id': res_id,
        'view_mode': view_mode,
    }
