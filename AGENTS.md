# KYLD Odoo 17 Custom Addons

Odoo 17 addon repository for **apcball/KYLD** (Thai company). 149 modules across custom (`buz_*`), Thai localization (`l10n_th_*`), OCA, and other third-party addons.

## Repo layout

- Root is a flat directory of addon modules — each has `__manifest__.py`, no `__openerp__.py`.
- Odoo server is at `/opt/instance1/odoo17/`, config at `/etc/instance1.conf`, live DB is `KYLD-LIVE`.
- Primary venv: `/opt/instance1/odoo17-venv/`. A secondary `.venv/` exists in this repo.
- `data_file/` contains CSV/XLS bank statement fixtures for import testing.

## No testing / CI infrastructure

- No CI workflows, no pre-commit, no lint config, no test runner config at root.
- Individual OCA modules may have their own `pyproject.toml` but no unified test setup.
- Do not attempt to run tests or linters — they do not exist for this repo.

## Module upgrade

Use the existing scripts or equivalent:

```bash
cd /opt/instance1/odoo17
source /opt/instance1/odoo17-venv/bin/activate
python odoo-bin -c /etc/instance1.conf -d KYLD-LIVE -u <module> --stop-after-init
sudo systemctl restart instance1
```

Or use the Odoo shell method (`update_module.py` as reference).

## Git conventions

- Remote: `git@github.com:apcball/KYLD.git` (author: Apichart Ball)
- Active branch: `KYLD-COPILOT`
- Most commits use message `"ok"` — descriptive messages appear only for significant features.

## Module naming

| Prefix | Origin |
|--------|--------|
| `buz_*` | Custom company modules (Buzz) |
| `l10n_th_*` | Thai localization (Ecosoft/OCA) |
| `fieldservice*` | OCA fieldservice suite |
| Others | OCA, Odoo apps store, or bespoke custom |

## Check Database
cat /etc/instance1.conf
Database : KYLD_LIVE