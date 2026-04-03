#!/usr/bin/env python3
import subprocess
import os

os.chdir('/opt/instance1/odoo17')

command = """
source /opt/instance1/odoo17-venv/bin/activate
python3 odoo-bin shell -c /etc/instance1.conf --shell-interface ipython << 'EOF'
moves = env['budget.move'].search([('company_id', '=', False)])
print(f"Found {len(moves)} budget moves to update.")
if moves:
    for move in moves:
        if move.allocation_id and move.allocation_id.company_id:
            move.company_id = move.allocation_id.company_id
    env.cr.commit()
    print("Company ID backfilled successfully!")
else:
    print("No moves need updating.")
exit()
EOF
"""

result = subprocess.run(command, shell=True, capture_output=True, text=True, executable='/bin/bash')
print("STDOUT:", result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
