#!/usr/bin/env python3
"""
Script to update employee_purchase_requisition module via Odoo shell
"""
import subprocess
import sys
import os

# Change to Odoo directory
os.chdir('/opt/instance1/odoo17')

# Activate virtual environment and run odoo shell
command = """
source /opt/instance1/odoo17-venv/bin/activate
python3 odoo-bin shell -c /etc/instance1.conf --shell-interface ipython << 'EOF'
# Update the employee_purchase_requisition module
module = env['ir.module.module'].search([('name', '=', 'employee_purchase_requisition')])
if module:
    print(f"Found module: {module.name}, state: {module.state}")
    if module.state == 'installed':
        module.button_immediate_upgrade()
        print("Module upgraded successfully")
    else:
        print("Module is not installed")
else:
    print("Module not found")

# Check if our rules exist
rules = env['ir.rule'].search([('name', 'in', ['Location multi-company', 'stock.location multi-company', 'Stock Location Admin Access'])])
for rule in rules:
    print(f"Rule: {rule.name}, Model: {rule.model_id.model}, Active: {rule.active}")

exit()
EOF
"""

# Execute the command
result = subprocess.run(command, shell=True, capture_output=True, text=True, executable='/bin/bash')
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr)
print("Return code:", result.returncode)
