#!/usr/bin/env python3
"""
Script to check user-employee linkage and signature status in Odoo
This helps diagnose why some users can't use auto-approval feature
"""

import sys
import os

# Add Odoo to Python path
sys.path.append('/opt/instance1/odoo17')

import odoo
from odoo import api, SUPERUSER_ID

def check_users_signature_status(db_name):
    """Check all users for employee linkage and signature status"""
    
    odoo.tools.config.parse_config(['--database', db_name])
    
    with api.Environment.manage():
        registry = odoo.registry(db_name)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            
            print("=" * 80)
            print("User - Employee - Signature Status Report")
            print("=" * 80)
            
            users = env['res.users'].search([('active', '=', True)])
            
            issues_found = []
            ok_users = []
            
            for user in users:
                # Skip system users
                if user.id in [1, 2]:  # Admin and public user
                    continue
                    
                employee = user.employee_id
                status = []
                
                if not employee:
                    status.append("❌ NO EMPLOYEE LINKED")
                    issues_found.append({
                        'user': user.name,
                        'login': user.login,
                        'issue': 'No employee linked',
                        'recommendation': f'Link user to an employee record in HR/Employees'
                    })
                else:
                    if not employee.signature_image:
                        status.append("❌ NO SIGNATURE")
                        issues_found.append({
                            'user': user.name,
                            'login': user.login,
                            'employee': employee.name,
                            'issue': 'Employee has no signature',
                            'recommendation': f'Upload signature for employee {employee.name} in HR'
                        })
                    else:
                        status.append("✅ HAS SIGNATURE")
                        ok_users.append(user.name)
                
                employee_name = employee.name if employee else "None"
                print(f"User: {user.name:30} | Login: {user.login:25} | Employee: {employee_name:30} | {' '.join(status)}")
            
            print("\n" + "=" * 80)
            print("SUMMARY")
            print("=" * 80)
            print(f"Total active users checked: {len(users) - 2}")  # Exclude admin and public
            print(f"Users OK (can use auto-approval): {len(ok_users)}")
            print(f"Users with issues: {len(issues_found)}")
            
            if issues_found:
                print("\n" + "=" * 80)
                print("ISSUES REQUIRING ATTENTION")
                print("=" * 80)
                for idx, issue in enumerate(issues_found, 1):
                    print(f"\n{idx}. User: {issue['user']} ({issue.get('login', 'N/A')})")
                    if 'employee' in issue:
                        print(f"   Employee: {issue['employee']}")
                    print(f"   Issue: {issue['issue']}")
                    print(f"   Recommendation: {issue['recommendation']}")
            else:
                print("\n✅ All users are properly configured for auto-approval!")
            
            print("\n" + "=" * 80)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python check_signature_status.py <database_name>")
        print("Example: python check_signature_status.py MOG_Pretest2")
        sys.exit(1)
    
    db_name = sys.argv[1]
    check_users_signature_status(db_name)
