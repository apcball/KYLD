import sys
from odoo import api, SUPERUSER_ID

env = api.Environment(cr, SUPERUSER_ID, {})

reqs = env['employee.purchase.requisition'].search([], limit=5)
for req in reqs:
    print(f"Req: {req.name}, total_amount: {req.total_amount}, company_currency_id: {req.company_currency_id.name}")
    for line in req.requisition_order_ids:
        print(f"  Line qty: {line.quantity}, unit_price: {line.unit_price}, subtotal: {line.price_subtotal}")
