
# AGENTS.md

## Project

~230 Odoo 17 addons for Mogen Co., Thailand. Flat in repo root — each subdirectory is one addon.

Hosted on Contabo VPS, Dockerized (`odoo:17.0` base). Postgres 16.

## Key architecture

- Custom modules: prefix `buz_` (e.g. `buz_commercial_invoice`)
- Thai localization: prefix `l10n_th_` (e.g. `l10n_th_account_tax`)
- OCA/third-party modules: no prefix — verify origin before editing
- Server-wide module: `mcp_db_resolver` (WSGI middleware, listed in `server_wide_modules`)
- MCP stack: `mcp_server` module + `mcp-odoo/mcp_odoo.py` (external client, stdio transport)
- Model namespace: `buz.<model_name>` (e.g. `buz.service.receipt`)
- XML IDs: module-prefixed (e.g. `buz_service_receipt.action_...`)

## Commands

```bash
# Deploy to DEV server
rsync -az --delete "./<module>/" root@217.216.32.33:/srv/docker/odoo_kyld/custom-addons/<module>/
ssh root@217.216.32.33 "docker exec odoo_kyld odoo -d KYLD-DEV -u <module> --stop-after-init --no-http"

# Deploy to PROD server 
rsync -az --delete "./<module>/" mogenit@119.13.29.46:/srv/docker/odoo_kyld/custom-addons/<module>/
ssh mogenit@119.13.29.46 "docker exec odoo odoo -d KYLD_LIVE -u <module> --stop-after-init --no-http"

# Test on live DB — IRREVERSIBLE SIDE EFFECTS. Use isolated test below instead.
ssh root@217.216.32.33 "docker exec odoo_kyld odoo -d KYLD-DEV -u <module> --test-enable --stop-after-init --no-http"

# Isolated test (local docker-compose with fresh Postgres)
docker compose -f docker-compose.test.yml up --abort-on-container-exit

# Lint
pip install pylint pylint-odoo
pylint --load-plugins=pylint_odoo <module>/
```

## CI flow (GitHub Actions + GitLab CI self-hosted)

`detect → lint → test → deploy`

Module detection (`detect` job):

```bash
git diff --name-only HEAD~1 HEAD | grep -oP '^[a-z][a-z0-9_]+(?=/)' | sort -u
```

For PRs: diff against base branch instead of `HEAD~1`.

- Lint uses `pylint-odoo` with `allow_failure: true`
- Tests run via `--test-enable` against the LIVE production DB container. Each module copy + update is one `docker exec` call.
- Deploy only on `main` / `Docker_Ball` branches, push events. rsync then `-u` update.
- GitLab CI deploy step is `manual` + `Docker_Ball` only.

## Module layout

Standard Odoo 17: `models/`, `views/`, `security/`, `data/`, `wizard/`, `report/`, `static/`. `__manifest__.py` defines deps and data.

## Conventions

- Multi-company: `company_id` with `_check_company=True`, `default=lambda self: self.env.company`
- Odoo 17 API only: `fields.Command` not `(0, 0, {...})` tuple syntax
- Security: `security/ir.model.access.csv` + `security/security.xml`
- DB names: `^MOG` pattern (MOG_DEV, MOG_TEST)
- Use `mail.thread` / `mail.activity.mixin` for models needing chatter

## Testing quirks

- Odoo `--test-enable` runs tests against the **actual DB** — side effects are irreversible
- Module must have `tests/` with `__init__.py` importing test classes
- No pytest, no unittest discover — Odoo test runner only
- `docker-compose.test.yml` creates isolated Postgres — **prefer this over live-DB testing**
  - Currently hardcoded to test `buz_commercial_invoice` — edit `command` for other modules
- Most modules do NOT have tests. Check for `tests/` before running.

## Never edit

`__pycache__/`, `*.pyc`, `uploads/`, `*.tar.gz`, `.env`, `.venv/`, lockfiles from other tools (`.thclaws/`, `.codewhale/`, `.deepseek/`). Module `README.*` files are Odoo app store descriptions only.

## Server paths

| Server                                                                                  | Host                     | Docker root                             |
| --------------------------------------------------------------------------------------- | ------------------------ | --------------------------------------- |
| DEV                                                                                     | `root@217.216.32.33`   | `/srv/docker/odoo_kyld/custom-addons` |
| PROD                                                                                    | `mogenit@119.13.29.46` | `/srv/docker/odoo_kyld/custom-addons` |
| Container addons path:`/mnt/custom-addons` (volume mapped from `./custom-addons/`). |                          |                                         |

Config: `%DOCKER_ROOT%/config/odoo.conf`

## Database access (PROD)

Postgres 16, Docker volume `postgres_pg_data` bind-mounted to `/mnt/database` on host.

SSH tunnel for pgAdmin / psql:

```bash
ssh -f -N -L 5433:localhost:5432 mogenit@119.13.29.46
# connect to localhost:5433
```

| Field    | Value                              |
| -------- | ---------------------------------- |
| Host     | `localhost`                      |
| Port     | `5433` (after tunnel)            |
| Database | `KYLD_BASE`, `KYLD_LIVE`       |
| User     | `odoo`                           |
| Password | `%DOCKER_ROOT%/config/odoo.conf` |

No local `psql` client needed for read-only checks: `ssh mogenit@119.13.29.46 "docker exec postgres psql -U odoo -d KYLD_LIVE -c '...'"` connects via the Postgres container's own socket (peer auth, no password), simpler than tunneling. Postgres container name on PROD is `postgres`, not `odoo` (that's the Odoo app container).

## Pending ops — job_costing_management (2026-09-12)

Bug found comparing code + real PROD data: `purchase.order.line`'s fallback
matcher (`models/purchase_order.py`, project-fallback block) linked PO lines
to job.cost.line by `product_id + name` only, scoped to the cost sheet but
**not** to `boq_line_id`. Two BOQ lines that share the same product and
identical description text (e.g. copy-pasted line text across BOQs) could
steal each other's actual cost. Confirmed live on sheet 10: PO line 3497
(from BOQ line 3906) had landed on the job.cost.line for BOQ line 1385.

- Code fix: commit `ae5e783` — fallback match now requires the candidate's
  `boq_line_id` to be blank or equal to the PO line's own BOQ line; new
  fallback-created cost lines now stamp `boq_line_id` too.
- Data-fix script: commit `f1cdc0a`, `scripts/fix_po_boq_line_mismatch.py` —
  one-time `odoo shell` script, defaults to `DRY_RUN = True` (prints only,
  no writes). Flip to `False` after reviewing the printed relink list, then
  re-run to apply + commit.
- Plan for the night: deploy `job_costing_management` to PROD (module
  update), then run the fix script against `KYLD_LIVE` per the usage notes
  at the top of the script file.
- Still open from the original BOQ-visibility review (see commit history:
  `9bdcad1`, `ae5e783`, `f1cdc0a`): no other module in the repo was audited
  for the same product+name-without-boq_line_id matching pattern — if a
  similar bug turns up elsewhere, check `service_po.py`'s
  `get_or_create_cost_line` fallback too (same shape, not fixed here since
  no confirmed instance was found for it).
