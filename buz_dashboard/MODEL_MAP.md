# MODEL_MAP — buz_dashboard

Derived by reading `job_costing_management` source directly (no field or model name in this document was guessed). Business concept → Odoo model → field → relationship → dashboard KPI.

## Planned cost

| Business Concept | Model | Field | Relationship | Dashboard KPI |
|---|---|---|---|---|
| Planned material cost (project total) | `job.cost.sheet` | `total_material_cost` | `project_id → job.cost.sheet` (o2m `job_cost_sheet_ids`) | `overview.material_cost` component, `cost-breakdown.planned.materials` |
| Planned labour cost | `job.cost.sheet` | `total_labour_cost` | same | `cost-breakdown.planned.labour` |
| Planned overhead cost | `job.cost.sheet` | `total_overhead_cost` | same | `cost-breakdown.planned.overheads` |
| Planned total cost | `job.cost.sheet` | `total_cost` | same | `overview.planned_cost` |
| Planned cost per line | `job.cost.line` | `total_cost` = `planned_qty × unit_cost` | `cost_sheet_id → job.cost.line`, split by `cost_type` | `materials.top_materials`, `labour` breakdowns |

## Actual cost (and its provenance)

| Business Concept | Model | Field | Relationship | Dashboard KPI |
|---|---|---|---|---|
| Actual material cost | `job.cost.sheet` | `actual_material_cost` | computed from `job.cost.line` where `cost_type='material'`, from **received PO lines** (`purchase.order.line.qty_received`, `price_subtotal`, filtered `order_id.state in ('purchase','done')`) | `overview.material_cost`, `materials.summary.actual_cost` |
| Actual labour cost | `job.cost.sheet` | `actual_labour_cost` | from `account.analytic.line.amount` (timesheets, `abs()` applied — Odoo stores cost as negative) + subcontract PO lines | `labour.summary.actual_cost` |
| Actual overhead cost | `job.cost.sheet` | `actual_overhead_cost` | **`job.cost.line._compute_actual_qty` hard-codes `actual_qty = 0` for `cost_type='overhead'`** (source has a `TODO`) | `overheads.summary.actual_cost` — will read ~0; documented limitation |
| Vendor bill trigger | `account.move` | `action_post()` | posting a vendor bill recomputes `job.cost.sheet._compute_actual_costs()` on every linked sheet via `account.move.line.job_cost_line_id` | drives all "actual" figures |

## Variance

| Business Concept | Model | Field | Dashboard KPI |
|---|---|---|---|
| Material/Labour/Overhead/Total variance | `job.cost.sheet` | `material_variance`, `labour_variance`, `overhead_variance`, `total_variance` (= actual − planned) | `variance.by_type` |
| Per-line variance | `job.cost.line` | `qty_variance`, `cost_variance` | `materials.variance`, top-variance rankings |

## Project / contract

| Business Concept | Model | Field | Dashboard KPI |
|---|---|---|---|
| Contract amount | `project.project` | `contract_amount` (Float, no own currency field — uses project's related company currency) | `overview.contract_amount`, `profitability.contract_amount` |
| Project planned/actual roll-up | `project.project` | `total_planned_cost`, `total_actual_cost`, `cost_variance`, `budget_utilization` (all `store=True`) | `projects` list, `project-detail.summary` |
| Project cost progress | `project.project` | `cost_progress` — **not stored**, cannot be used in a domain or `read_group` | dashboard recomputes progress from stored planned/actual instead |
| Project manager | `project.project` | `project_manager_id` (Many2one `res.users`) | `projects[].manager` |
| Completed status | `project.project` | `last_update_status` (core field, feature-detected — not verified against this deployment offline) with fallback to "all cost sheets `state = 'done'`" | `overview.completed_projects`, `projects[].status` |

## Materials

| Business Concept | Model | Field | Dashboard KPI |
|---|---|---|---|
| Requested vs received qty | `material.requisition.line` | `quantity`, `received_qty` | `materials.consumption`, `materials.shortage` (= `quantity − received_qty`) |
| Procurement amount | `purchase.order.line` | `price_subtotal`, `qty_received`, joined via `job_cost_line_id` | `materials.procurement` |
| Top material cost/variance | `job.cost.line` grouped by `product_id`, `cost_type='material'` | `total_cost`, `actual_cost` | `materials.top_materials`, `materials.variance` |

## Labour

| Business Concept | Model | Field | Dashboard KPI |
|---|---|---|---|
| Hours worked | `account.analytic.line` | `unit_amount`, grouped by `employee_id`, filtered by `project_id` (stored related) | `labour.summary.actual_hours`, `labour.timesheet_summary` |
| Labour cost by employee | `account.analytic.line` | `amount` (negative; `abs()` applied) | `labour.top_labour` |
| Cost per hour | derived | `actual_cost / actual_hours`, guarded against zero (`None` when hours = 0) | `labour.summary.cost_per_hour` |

## Overheads

| Business Concept | Model | Field | Dashboard KPI |
|---|---|---|---|
| Overhead by category | `job.cost.line` grouped by `product_id`, `cost_type='overhead'` | `total_cost`, `actual_cost` | `overheads.by_category` |
| Overhead by project | `job.cost.line` joined via `cost_sheet_id → job.cost.sheet.project_id` | same | `overheads.by_project` |
| Overhead trend | `job.cost.sheet` grouped by `date_start:month` | `total_overhead_cost`, `actual_overhead_cost` | `overheads.trend` |

## Profitability

| Business Concept | Model | Field | Dashboard KPI |
|---|---|---|---|
| Gross profit | derived | `contract_amount − actual_total_cost` | `profitability.projects[].gross_profit` |
| Profit margin % | derived | `gross_profit / contract_amount × 100`, `None` when `contract_amount = 0` | `profitability.projects[].profit_margin` |
| Rankings | derived, sorted in memory over the project rollup (no query in a loop) | — | `most_profitable`, `least_profitable`, `highest_cost_variance`, `highest_revenue` |

## Known gaps (see README "Known limitations")

1. Overhead actuals are structurally ~0 (`job_cost_sheet.py`, `_compute_actual_qty`, `TODO: Define overhead quantity logic`).
2. `job.cost.sheet.currency_id` is nullable on rows created before the `create()` default logic was added.
3. `project.cost_progress` is a non-stored compute — recomputed here from stored fields instead of being queried.
4. `rule_job_cost_sheet_user` scopes non-managers to their own/managed projects only; this dashboard is meaningful primarily for `group_job_costing_manager`.
