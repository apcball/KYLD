#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import odoo
from odoo import api, SUPERUSER_ID

# Configuration
config_file = '/etc/instance1.conf'
db_name = 'KYLD-LIVE'
pr_number = 'KPO2500039'

# Load Odoo configuration
odoo.tools.config.parse_config(['-c', config_file])

# Connect to database
registry = odoo.registry(db_name)

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Find all POs related to this PR
    pos = env['purchase.order'].sudo().search([
        ('requisition_order', '=', pr_number)
    ])
    
    if pos:
        print(f"Found {len(pos)} PO(s) for PR {pr_number}:")
        for po in pos:
            print(f"  - {po.name} (ID: {po.id})")
        
        # Delete all related POs
        pos.unlink()
        cr.commit()
        print(f"\nSuccessfully deleted {len(pos)} PO(s)")
    else:
        print(f"No POs found for PR {pr_number}")
