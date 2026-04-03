#!/usr/bin/env python3
import subprocess
import os

os.chdir('/opt/instance1/odoo17')

command = """
source /opt/instance1/odoo17-venv/bin/activate
python3 odoo-bin shell -c /etc/instance1.conf << 'EOF'
import time
print("Starting global budget recompute...")
start_time = time.time()
try:
    env['monthly.budget.plan'].action_recompute_all_budgets()
    env.cr.commit()
    print(f"Success! Time taken: {time.time() - start_time:.2f}s")
except Exception as e:
    print(f"Error during recompute: {str(e)}")
    env.cr.rollback()
EOF
"""

result = subprocess.run(command, shell=True, capture_output=True, text=True, executable='/bin/bash')
print("STDOUT:", result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
