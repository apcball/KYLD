# Module Upgrade Instructions

The `employee_purchase_requisition` module has been updated to fix the company filtering issue.

## Error Fixed
- **Error**: `EvalError: Name 'env' is not defined` when opening Purchase Requisition menu
- **Cause**: Invalid client-side domain expression in action definition (cached in database)
- **Solution**: Added server-side record rule for company filtering

## Changes Made
1. Added `ir.rule` in `security/employee_purchase_requisition_security.xml`
   - Filters records to show only user's companies
   - Domain: `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`

2. Removed invalid domain from action view (if it existed)

## How to Apply Changes

### Method 1: Via Odoo Web Interface (Recommended)
1. Login to Odoo as Administrator
2. Go to **Apps** menu
3. Click the search filter icon and remove the "Apps" filter
4. Search for **"Employee Purchase Requisition"** or **"buz"**
5. Find the module in the list
6. Click the **⋮** (three dots) menu button
7. Select **Upgrade**
8. Wait for the upgrade to complete
9. **Clear your browser cache** (Ctrl+Shift+Delete or Cmd+Shift+Delete)
10. Refresh the page (F5 or Ctrl+R)

### Method 2: Via Command Line (if database access works)
```bash
cd /opt/instance1/odoo17
sudo -u postgres /opt/instance1/odoo17-venv/bin/python3 odoo-bin -c /etc/instance1.conf -d instance1 -u employee_purchase_requisition --stop-after-init
sudo systemctl restart instance1
```

### Method 3: Clear Specific View Cache (Advanced)
If the error persists after upgrade, the action cache may need to be cleared:

1. Login as Administrator
2. Activate Developer Mode: Settings → Activate Developer Mode
3. Go to Settings → Technical → Actions → Window Actions
4. Search for "c" or "employee_purchase_requisition_action"
5. Open the action record
6. Remove any `domain` field value if present
7. Save
8. Clear browser cache and refresh

## Verification
After upgrade, test:
1. Navigate to **Purchase Requisition** menu
2. The menu should open without errors
3. You should only see requisitions from your company/companies
4. Try switching companies (if multi-company) and verify filtering works

## Troubleshooting
- **Still seeing error after upgrade**: Clear browser cache completely
- **Module doesn't show upgrade button**: Module is already up to date, but views might be cached. Try Method 3 above
- **Can't access Apps menu**: Use direct URL: `http://your-domain/web#menu_id=&action=base.open_module_tree`
