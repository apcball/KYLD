# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class POShortfallWizard(models.TransientModel):
    _name = 'po.shortfall.wizard'
    _description = 'PO Shortfall Closure Wizard'

    po_id = fields.Many2one(
        'purchase.order', string='Purchase Order',
        required=True, readonly=True)
    reason = fields.Text(
        string='Reason', required=True,
        help='Explain why the supplier could not deliver the full quantity.')
    note = fields.Text(string='Additional Notes')

    # Display helpers
    shortfall_summary = fields.Html(
        string='Shortfall Details',
        compute='_compute_shortfall_summary',
    )

    @api.depends('po_id')
    def _compute_shortfall_summary(self):
        for rec in self:
            if not rec.po_id:
                rec.shortfall_summary = ''
                continue

            rows = []
            for line in rec.po_id.order_line:
                if line.display_type not in (False, 'product', ''):
                    continue
                shortfall = line.product_qty - line.qty_received
                if shortfall > 0:
                    rows.append(
                        '<tr><td>%s</td><td class="text-end">%.2f</td>'
                        '<td class="text-end">%.2f</td>'
                        '<td class="text-end text-danger"><strong>%.2f</strong></td></tr>' % (
                            line.product_id.display_name,
                            line.product_qty,
                            line.qty_received,
                            shortfall,
                        )
                    )

            if rows:
                rec.shortfall_summary = (
                    '<table class="table table-sm">'
                    '<thead><tr><th>Product</th><th class="text-end">Ordered</th>'
                    '<th class="text-end">Received</th>'
                    '<th class="text-end">Shortfall</th></tr></thead>'
                    '<tbody>%s</tbody></table>' % ''.join(rows)
                )
            else:
                rec.shortfall_summary = '<div class="alert alert-success">No shortfall found.</div>'

    def action_confirm(self):
        """Close shortfall: reduce PO line qty to received, cascade to MR."""
        self.ensure_one()
        po = self.po_id

        if po.state != 'purchase':
            raise ValidationError(_('Can only close shortfall on confirmed Purchase Orders.'))

        changes = []
        for line in po.order_line:
            if line.display_type not in (False, 'product', ''):
                continue

            shortfall = line.product_qty - line.qty_received
            if shortfall <= 0:
                continue

            old_qty = line.product_qty
            # Reduce PO line qty to actual received
            line.write({'product_qty': line.qty_received})
            changes.append(
                _('%s: %.2f → %.2f (shortfall %.2f)') % (
                    line.product_id.display_name,
                    old_qty, line.qty_received, shortfall,
                )
            )

            # Cascade: reduce linked MR line accordingly
            if line.material_requisition_line_id:
                mr_line = line.material_requisition_line_id
                new_mr_qty = max(0, mr_line.quantity - shortfall)
                if new_mr_qty != mr_line.quantity:
                    mr_line.write({'quantity': new_mr_qty})
                    _logger.info(
                        'Shortfall cascade: MR line %s qty %.2f → %.2f',
                        mr_line.id, mr_line.quantity + shortfall, new_mr_qty)

        # Post audit message on PO
        if changes:
            body = _(
                '<strong>Close Shortfall</strong><br/>'
                '<strong>Reason:</strong> %s<br/>'
                '%s<br/>'
                '<strong>Lines adjusted:</strong><br/>%s'
            ) % (
                self.reason,
                _('<strong>Note:</strong> %s') % self.note if self.note else '',
                '<br/>'.join(changes),
            )
            po.message_post(
                body=body,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )

        # Trigger budget recompute
        if hasattr(po, '_update_budget_moves'):
            po._update_budget_moves()

        # Trigger MR budget recompute
        mr_ids = set()
        for line in po.order_line:
            if line.material_requisition_line_id:
                mr_ids.add(line.material_requisition_line_id.requisition_id.id)
        if mr_ids:
            mrs = self.env['material.requisition'].browse(list(mr_ids))
            if hasattr(mrs, '_update_budget_moves'):
                mrs._update_budget_moves()

        # Recompute BOQ tracking
        boq_lines = po.order_line.mapped('material_requisition_line_id.boq_line_id')
        if boq_lines:
            boq_lines._compute_purchase_tracking()

        return {'type': 'ir.actions.act_window_close'}
