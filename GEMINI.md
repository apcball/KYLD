# Gemini CLI Project Context: KYLD Odoo 17 Custom Addons

This repository contains custom Odoo 17 modules (addons) developed for the KYLD project, focused on accounting, inventory management, and specialized purchasing controls.

## Project Overview

- **Platform:** Odoo 17.0 (Community/Enterprise)
- **Main Technologies:** Python 3.10+, PostgreSQL, XML (Odoo Views/Data), JavaScript (OWL/Odoo Web Client)
- **Key Modules:**
  - `biz_weekly_budget`: Weekly budget control for Purchase Orders (PR/PO/MR).
  - `buz_*`: Various custom enhancements for accounting, invoices, and inventory.
  - `account_invoice_fixed_discount`: OCA-based module for fixed discounts.
  - `inventory_advanced_reports`: Enhanced inventory reporting.
- **Project Structure:**
  - `/srv/docker/odoo_kyld/custom-addons/`: Root directory for custom modules.
  - Each subdirectory is an Odoo module following the standard structure (`models/`, `views/`, `security/`, `data/`, `__manifest__.py`).

## Environment & Configuration

- **OS:** Linux (Ubuntu/Debian based)
- **Odoo Config:** `/etc/instance1.conf`
- **Main Database:** `KYLD-LIVE`
- **Systemd Service:** `instance1`
- **Virtual Environment:** Typically at `/opt/instance1/odoo17-venv/` or `/srv/docker/odoo_kyld/custom-addons/.venv/`
- **Odoo Bin:** `/opt/instance1/odoo17/odoo-bin`

## Building and Running

### Module Management
To update or install a specific module (e.g., `biz_weekly_budget`):

```bash
# Using the provided shell script (runs for employee_purchase_requisition by default)
./upgrade_module.sh

# Manual update command
sudo -u odoo /opt/instance1/odoo17-venv/bin/python3 /opt/instance1/odoo17/odoo-bin \
    -c /etc/instance1.conf -d KYLD-LIVE -u <module_name> --stop-after-init
```

### Restarting the Service
After updating Python code or XML views, restart the Odoo service:
```bash
sudo systemctl restart instance1
```

### Troubleshooting / Odoo Shell
Use the Odoo shell for debugging or bulk data operations:
```bash
sudo -u odoo /opt/instance1/odoo17-venv/bin/python3 /opt/instance1/odoo17/odoo-bin \
    shell -c /etc/instance1.conf -d KYLD-LIVE
```

## Development Conventions

- **Module Naming:** Custom modules use `buz_` or `biz_` prefixes.
- **Licensing:** Most modules follow `AGPL-3` (standard for OCA-related modules).
- **Standards:**
  - Adhere to Odoo 17 API (Environment, Recordsets, `api.model`, `api.depends`).
  - XML files should be organized by purpose: `views/`, `security/` (ir.model.access.csv and groups), `data/` (records/sequences).
  - Use `buz_` prefix for custom fields in standard models (e.g., `x_` is for UI-added fields, but `buz_` is preferred for code-based custom fields in this project).
- **Automation Scripts:**
  - `update_module.py`: Python script for automated module upgrades via Odoo shell.
  - `delete_po.py`: Utility script to delete Purchase Orders related to specific Requisitions.
  - `upgrade_module.sh`: Bash script to update modules and restart the service.

## Key Files for Reference
- `prompt.md`: Design document for the Weekly Budget Control system.
- `update_module.py`: Example of using Odoo shell for administration.
- `/etc/instance1.conf`: System-wide Odoo configuration (Read-only for app logic).
