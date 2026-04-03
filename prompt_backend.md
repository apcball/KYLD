# 🧠 Prompt: Upgrade Weekly Budget Control → Department + Monthly Hybrid (Backend - Odoo 17)

## 🎯 Objective

Upgrade existing module `biz_weekly_budget` to support:

1. Department-based budgeting (replace analytic dependency)
2. Monthly budget layer (parent of weekly)
3. Department allocation by percentage
4. Backward compatibility with existing weekly engine
5. Advanced controls (forecast, aging, soft/hard)

---

# 🏗️ ARCHITECTURE (IMPORTANT)

## Existing (KEEP)

* weekly.budget.plan
* weekly.budget.line
* budget.move (ledger)

## New Layer (ADD)

```text
monthly.budget.plan
    ↓
monthly.budget.allocation (department %)
    ↓
weekly.budget.plan (generated from monthly)
```

👉 Weekly = execution layer
👉 Monthly = control layer

---

# 🧩 1. NEW MODELS

## 1.1 monthly.budget.plan

```python
name
year
month
date_from
date_to

company_id
total_budget

state = draft / confirmed / done

allocation_ids (department %)
weekly_plan_ids
```

---

## 1.2 monthly.budget.allocation

```python
plan_id
department_id
percentage
amount (computed)
```

### Constraint:

```python
sum(percentage) == 100
```

---

# 🔗 2. EXTEND EXISTING MODELS

## 2.1 weekly.budget.plan

Add:

```python
monthly_plan_id = fields.Many2one('monthly.budget.plan')
department_id = fields.Many2one('hr.department')
```

---

## 2.2 weekly.budget.line

REPLACE analytic logic with:

```python
department_id = fields.Many2one('hr.department', required=True)
```

---

## ⚠️ IMPORTANT

* REMOVE dependency on analytic_account_id
* Keep field temporarily for migration only

---

# 🧠 3. DEPARTMENT MAPPING

## Add to ALL source documents:

* purchase.order
* purchase.requisition
* material.requisition
* account.move

```python
department_id = fields.Many2one('hr.department', store=True)
```

---

## Mapping logic:

```python
def _get_department(self):
    if self.employee_id:
        return self.employee_id.department_id
    if self.env.user.employee_id:
        return self.env.user.employee_id.department_id
    return self.env.company.default_department_id
```

---

## On create:

* assign department_id (LOCK value)

---

# 💰 4. MONTHLY → WEEKLY DISTRIBUTION

## Generate Weekly Plans from Monthly

```python
for each department allocation:
    monthly_amount = total_budget * percentage

    weekly_amount = monthly_amount / number_of_weeks

    create weekly.budget.plan per week
```

---

## Store:

```python
weekly_plan.department_id
weekly_plan.monthly_plan_id
```

---

# 🔄 5. BUDGET MOVE (NO CHANGE CORE)

But extend:

```python
department_id (required)
month_key
week_key
```

---

# 📊 6. BUDGET CALCULATION (UPDATED)

## Group by:

```python
department_id + week
```

---

## Add Monthly Aggregation:

```python
monthly_used = sum(weekly_used)
monthly_reserved = sum(weekly_reserved)
```

---

# 🔥 7. FORECAST LAYER (NEW)

## Add field:

```python
forecast_amount
```

---

## Sources:

* PO expected payment
* recurring cost
* fixed cost

---

## Formula:

```python
available_strict = limit - used - reserved
available_forecast = limit - forecast
```

---

# ⏳ 8. AGING RESERVATION (NEW)

## Add:

```python
reservation_date
aging_days
```

---

## CRON:

```python
if aging_days > threshold:
    release_reserved_move()
```

---

# 🚫 9. BUDGET CONTROL (UPDATED)

## Check:

```python
line = get_weekly_line(department_id, date)

if control_type == 'hard':
    block

if control_type == 'soft':
    warn only
```

---

# ⚙️ 10. CONFIGURATION

## Company Settings:

```python
default_department_id
budget_control_type = hard / soft
enable_forecast = True/False
aging_days_limit
```

---

# 🔁 11. RECOMPUTE ENGINE (UPGRADE)

## Must support:

1. Delete all budget.move

2. Rebuild from:

   * PR
   * PO
   * Bills

3. Recalculate:

   * weekly
   * monthly aggregation

---

# 🔄 12. MIGRATION STRATEGY

## Step 1:

* Add department_id to all records

## Step 2:

* Map analytic → department (optional mapping table)

## Step 3:

* Recompute all budget.move

---

# 🧠 13. OPTIONAL (ADVANCED)

## Priority-based allocation

```python
priority = high / normal / low
```

---

## Carry Forward

```python
unused → next week
```

---

# 📌 RULES (STRICT)

* NEVER compute budget from source directly → always via budget.move
* department_id must be stored (no dynamic compute)
* system must support recompute safely
* backward compatibility must be maintained
