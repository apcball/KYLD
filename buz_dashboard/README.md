# buz_dashboard — Dashboard API Engine

Read-only JSON API layer over `job_costing_management` data (materials, labour, overheads, profitability, variance, trends) for external frontends — React/Next.js executive dashboards, TV wallboards. This module does not build a dashboard UI inside Odoo, and it never modifies `job_costing_management`.

See `MODEL_MAP.md` for the full field-level source mapping and `docs/API.md` for endpoint request/response reference.

## Architecture

```
Odoo Business Data (job_costing_management)
        │
        ▼
services/  ── KPI calculation, aggregation, one class per endpoint,
               registered in SERVICE_REGISTRY
        │
        ▼
controllers/dashboard_api.py  ── thin JSON routing only, no business logic
        │
        ▼
JSON API  (/api/buz-dashboard/job-costing/*)
        │
        ▼
External frontend (React / Next.js)
```

- **`models/`** — dashboard configuration (`buz.dashboard`, `buz.dashboard.widget`), the DB-backed cache store, and the `ir.http` extension providing API-key auth + CORS.
- **`services/`** — all business logic. `DashboardFilter` parses/validates the request payload, `CurrencyResolver` handles safe cross-currency aggregation, `DashboardCacheService` abstracts the cache backend, and one service class per endpoint does the aggregation via `read_group`.
- **`controllers/`** — 10 routes, each ~6 lines, delegating to `_dispatch()` which resolves the service from the registry, runs it, and wraps the result in the standard envelope.

## Installation

```bash
rsync -az --delete ./buz_dashboard/ root@217.216.32.33:/srv/docker/odoo_kyld/custom-addons/buz_dashboard/
ssh root@217.216.32.33 "docker exec odoo_kyld odoo -d KYLD-DEV -i buz_dashboard --stop-after-init --no-http"
ssh root@217.216.32.33 "docker restart odoo_kyld"
```

## Dependencies

`base`, `project`, `job_costing_management`. Everything else (`purchase`, `stock`, `hr_timesheet`, `account`, `analytic`) is inherited transitively through `job_costing_management`.

## Configuration

Settings → Dashboard API:

| Setting | Parameter | Default |
|---|---|---|
| Cache backend | `buz_dashboard.cache_backend` | `db` (`none` disables caching) |
| Cache TTL (seconds) | `buz_dashboard.cache_ttl` | `60` |
| Cost progress warning threshold (%) | `buz_dashboard.threshold_warning` | `90` |
| Cost progress critical threshold (%) | `buz_dashboard.threshold_critical` | `100` |
| CORS allowed origins (comma-separated) | `buz_dashboard.cors_origins` | *(empty — same-origin only)* |

## API endpoints

All under `POST /api/buz-dashboard/job-costing/`:

`overview`, `projects`, `project-detail`, `cost-breakdown`, `materials`, `labour`, `overheads`, `profitability`, `variance`, `trends`.

### Common request filter

```json
{
    "date_from": "2026-01-01",
    "date_to": "2026-08-24",
    "company_id": 1,
    "project_ids": [],
    "manager_ids": [],
    "state": [],
    "limit": 50,
    "offset": 0
}
```

### Example

```http
POST /api/buz-dashboard/job-costing/overview
Content-Type: application/json
```
```json
{"jsonrpc": "2.0", "params": {"date_from": "2026-01-01", "date_to": "2026-08-24", "company_id": 1}}
```
```json
{
  "success": true,
  "data": {
    "total_projects": 20,
    "contract_amount": 100000000,
    "planned_cost": 70000000,
    "actual_cost": 62000000,
    "planned_profit": 30000000,
    "actual_profit": 38000000,
    "profit_margin": 38.0,
    "cost_variance": -8000000,
    "cost_variance_percent": -11.4,
    "material_cost": 40000000,
    "labour_cost": 15000000,
    "overhead_cost": 7000000
  },
  "meta": {
    "generated_at": "2026-08-24 10:00:00",
    "company_id": 1,
    "currency": "THB",
    "warnings": []
  }
}
```

## Security

- Every endpoint requires authentication — `auth='buz_dashboard'`: an Odoo session, or an `X-Odoo-Api-Key` header issued from *Preferences → Account Security → New API Key* (Odoo's built-in `res.users.apikeys`, no custom token model).
- All data access goes through `request.env[...]` — Odoo's own record rules and the multi-company rules already present on every job-costing model do the filtering. No global `sudo()`.
- The only two `sudo()` calls in this module: resolving the API key credential (a store that is by design unreadable to a normal user), and reading/writing the cache table (whose key is already uid- and company-scoped, so it cannot leak across users or companies).
- CORS is opt-in via an origin allowlist (`buz_dashboard.cors_origins`), empty by default. Never `Access-Control-Allow-Origin: *` — invalid with credentials, and a real leak.

## Performance

Every endpoint uses `read_group` for aggregation — no ORM query inside a loop, no N+1. Records fetched once per endpoint, joined in Python via id→dict maps. `limit`/`offset` are clamped (`limit` ≤ 500).

## Caching

`DashboardCacheService` is an abstract interface with a DB-backed default implementation (`buz.dashboard.cache`), not an in-process dict — Odoo runs multi-worker in production, so a per-process cache would give different workers different numbers. Cache keys are scoped by db, uid, company set, currency, and a hash of the request filters, so a cache entry can never cross a security boundary. Swapping to Redis later is a new `DashboardCacheService` subclass plus a new `buz_dashboard.cache_backend` value — no service-layer code changes.

## Extension guide

Adding a new business domain (sales, purchase, stock, manufacturing, accounting):

1. Create `services/<domain>_service.py` with one `DashboardService` subclass per endpoint, decorated `@register('<domain>.<endpoint>')`.
2. Add routes to `controllers/dashboard_api.py` that call `self._dispatch('<domain>.<endpoint>', payload)` — no other controller code needed.
3. Add the new module to `depends` if it isn't already inherited.

The controller layer never needs to change; `SERVICE_REGISTRY` is the only coupling point.

## Known limitations

1. **Overhead actuals are structurally ~0.** `job_costing_management`'s `job.cost.line._compute_actual_qty` hard-codes `actual_qty = 0` for `cost_type == 'overhead'` (source has a `# TODO: Define overhead quantity logic`). The Overhead Dashboard and the overhead slice of every breakdown will show planned figures against near-zero actuals — this is upstream behaviour in `job_costing_management`, not a bug in this module, and this module does not fix it (editing `job_costing_management` is out of scope).
2. **The job costing *user* record rule is narrow.** `rule_job_cost_sheet_user` limits non-managers to `create_uid = user OR project_id.user_id = user`. An executive dashboard is only meaningful for `group_job_costing_manager` (or `group_buz_dashboard_manager`, which implies it). Non-manager users get a correctly-scoped but near-empty response.
3. **`job.cost.sheet.currency_id` is nullable** on cost sheets created before the module's `create()` default was added. Those rows are assumed to be in company currency and flagged in `meta.warnings`.
4. **`project.cost_progress` is not stored** and cannot be filtered or grouped server-side; this dashboard recomputes progress from the stored planned/actual pair instead.
5. **Cached responses may omit currency-conversion warnings** — the warning is generated during `compute()`, not on a cache hit, so a cache-hit response's `meta.warnings` can be empty even where the underlying data had a currency gap. The first (uncached) call for a given filter set always carries the accurate warning list.
