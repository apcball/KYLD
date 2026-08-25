# buz_dashboard API Reference

Base path: `/api/buz-dashboard/job-costing/`
All routes: `POST`, `type='json'`, `auth='buz_dashboard'` (session cookie or `X-Odoo-Api-Key` header).

## Envelope

Success:
```json
{"success": true, "data": {...}, "meta": {"generated_at": "...", "company_id": 1, "currency": "THB", "warnings": []}}
```

Error:
```json
{"success": false, "error": {"code": "PROJECT_NOT_FOUND", "message": "Project not found"}}
```

Error codes: `INVALID_REQUEST`, `FORBIDDEN`, `PROJECT_NOT_FOUND`, `NOT_FOUND`, `INTERNAL_ERROR`. No traceback is ever returned.

## Common request filter

Every endpoint accepts (all optional except where noted):

| Field | Type | Notes |
|---|---|---|
| `date_from`, `date_to` | `YYYY-MM-DD` | Filters `job.cost.sheet.date_start` |
| `company_id` | int | Must be a company the caller has access to, or `FORBIDDEN` |
| `project_ids` | int[] | |
| `manager_ids` | int[] | Filters on `project.project.project_manager_id` |
| `state` | string[] | Cost sheet state: `draft`, `approved`, `done`, `cancelled` |
| `limit` | int | Default 50, max 500 |
| `offset` | int | Default 0 |
| `currency_id` | int | Base currency for the response; defaults to the caller's company currency |

---

## `overview`

Executive KPI summary.

**Response `data`:** `total_projects`, `active_projects`, `completed_projects`, `contract_amount`, `planned_cost`, `actual_cost`, `planned_profit`, `actual_profit`, `profit_margin`, `cost_variance`, `cost_variance_percent`, `material_cost`, `labour_cost`, `overhead_cost`.

`profit_margin` and `cost_variance_percent` are `null` when their denominator is zero — never a fabricated `0`.

---

## `projects`

Paginated project list with KPIs.

**Response `data`:** `{items: [...], total_count, limit, offset}`. Each item: `id`, `name`, `manager {id, name}`, `contract_amount`, `planned_cost`, `actual_cost`, `planned_profit`, `actual_profit`, `cost_progress`, `profit_margin`, `variance`, `status` (`on_track`|`warning`|`critical`|`completed`), `drilldown {model, res_id}`, `odoo_action {...}`.

---

## `project-detail`

**Request:** `{"project_id": 101}` — required.

**Errors:** missing `project_id` → `INVALID_REQUEST`; unknown or inaccessible project → `PROJECT_NOT_FOUND` (record rules already hide the project, so there is no separate "forbidden" case here).

**Response `data`:** `project`, `contract`, `summary`, `materials`, `labour`, `overheads`, `procurement`, `inventory`, `profitability`, `variance`, `progress`.

---

## `cost-breakdown`

**Response `data`:** `{planned: {materials, labour, overheads, total}, actual: {materials, labour, overheads, total}}`.

---

## `materials`

**Response `data`:** `summary`, `top_materials[]`, `variance[]`, `consumption[]`, `shortage[]`, `procurement[]`.

`shortage` = requisitioned quantity minus received quantity per product, only where positive.

---

## `labour`

**Response `data`:** `summary` (includes `cost_per_hour`, `null` when zero hours), `top_labour[]`, `timesheet_summary[]`.

---

## `overheads`

**Response `data`:** `summary`, `by_category[]`, `by_project[]`, `trend[]`.

**Note:** actual overhead cost is structurally near-zero — see README "Known limitations" #1.

---

## `profitability`

**Response `data`:** `projects[]` (full rollup), plus `most_profitable`, `least_profitable`, `highest_cost_variance`, `highest_revenue` (each top 10, ranked in memory over the same rollup — no extra queries).

---

## `variance`

**Response `data`:** `by_type` (`material`, `labour`, `overhead`, `total`, each `{planned, actual, variance, variance_percent}`), `by_project[]`.

---

## `trends`

**Request:** adds `group_by`: `day`|`week`|`month`|`quarter`|`year` (default `month`). Any other value → `INVALID_REQUEST`.

**Response `data`:** `{group_by, periods: [...], series: [{name, data: [...]}]}` for `Planned Cost`, `Actual Cost`, `Revenue`, `Profit` — ready for ECharts/Recharts without gaps.
