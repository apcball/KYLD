import sys
from odoo.tools.misc import mute_logger

env = self.env
line = env['account.move.line'].browse()
print(line._fields['price_subtotal'].compute)
print(line._fields['balance'].compute)
