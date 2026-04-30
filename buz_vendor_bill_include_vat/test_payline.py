import sys
from odoo.tools.misc import mute_logger

env = self.env
Move = env['account.move']

partner = env['res.partner'].search([], limit=1)
bill = Move.create({
    'move_type': 'in_invoice',
    'partner_id': partner.id,
    'invoice_date': '2023-01-01',
    'invoice_line_ids': [
        (0, 0, {
            'name': 'Test product',
            'quantity': 1,
            'price_unit': 1000.0,
        })
    ]
})

print(f"Bill created: {bill.id}")
print(f"Payable line credit before: {bill.line_ids.filtered(lambda l: l.display_type == 'payment_term').credit}")

bill.invoice_line_ids[0].price_unit = 2000.0
# Does the payable line update automatically?
print(f"Payable line credit after unit_price update: {bill.line_ids.filtered(lambda l: l.display_type == 'payment_term').credit}")

# What if check_move_validity=False is used?
bill.with_context(check_move_validity=False).write({'invoice_line_ids': [(1, bill.invoice_line_ids[0].id, {'price_unit': 3000.0})]})
print(f"Payable line credit after write with check_move_validity=False: {bill.line_ids.filtered(lambda l: l.display_type == 'payment_term').credit}")

env.cr.rollback()
