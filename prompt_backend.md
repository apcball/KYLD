# 🎯 Objective

พัฒนา Analytic Budget Engine สำหรับ Odoo 17 เพื่อควบคุมงบประมาณแบบ:

* Weekly (time dimension)
* Analytic-based (department / project)
* รองรับ Used / Reserved / Available
* รองรับ Partial billing และ analytic distribution

---

# 🧱 Core Concept

Budget = f(Week, Analytic Account, Department)

---

# 🗂️ Models Design

## 1. weekly_budget_plan (existing - extend)

* name
* date_from
* date_to
* company_id
* state

---

## 2. weekly_budget_line (REFACTOR - IMPORTANT)

Add dimensions:

* week_start (date)

* week_end (date)

* analytic_account_id (Many2one: account.analytic.account)

* department_id (Many2one: hr.department)

* analytic_tag_ids (Many2many)

Financial fields:

* budget_limit (float)
* used_amount (compute)
* reserved_amount (compute)
* available_amount (compute)

SQL constraint:

* unique(week_start, analytic_account_id, department_id, company_id)

---

## 3. budget_move (NEW - optional but recommended for performance)

Purpose:

* store pre-aggregated usage

Fields:

* source_model (po/pr/bill/mr)
* source_id
* analytic_account_id
* department_id
* amount
* type (reserved / used)
* date (cashflow date)

---

# ⚙️ Core Engine Logic

## 1. Budget Matching Function

```
def _get_budget_line(date, analytic_account_id, department_id, company_id):
    return search([
        ('week_start', '<=', date),
        ('week_end', '>=', date),
        ('analytic_account_id', '=', analytic_account_id),
        ('department_id', '=', department_id),
        ('company_id', '=', company_id),
    ], limit=1)
```

---

## 2. Reserved Calculation

Sources:

* PR
* MR
* PO (not fully billed)

Logic:

FOR each document line:
extract analytic distribution

IF analytic_distribution exists:
split amount by %
ELSE:
fallback to analytic_account_id

```
reserved += line_amount * percent
```

---

## 3. Used Calculation

Source:

* account.move (Vendor Bill)

Rule:

* only posted bills
* use invoice_date_due as budget date

Split logic same as reserved

---

## 4. Analytic Distribution Handling (CRITICAL)

Input example:

```
{
    "analytic_1": 0.7,
    "analytic_2": 0.3
}
```

Engine must:

* loop through each analytic
* allocate amount proportionally
* map to correct budget line

---

## 5. Available Calculation

```
available = budget_limit - used_amount - reserved_amount
```

---

# 🚨 Blocking Logic

Hook into:

* purchase.order → button_confirm
* purchase.requisition → approve
* material.requisition → submit

Validation:

FOR each line:
simulate reserved impact
find budget_line

IF available < required:
raise ValidationError

---

# 🧠 Smart Handling

## Partial Billing

PO:

* total = 100
* billed = 40

→ Used = 40
→ Reserved = 60

---

## Cancel Bill

* revert used → reserved

---

## Missing Analytic

Fallback priority:

1. line analytic
2. order analytic
3. department default analytic
4. ERROR (optional strict mode)

---

# ⚡ Performance Strategy

DO NOT compute from raw tables every time

Use:

Option A:

* computed stored fields

Option B (recommended):

* budget_move table (pre-aggregated)

Option C:

* SQL view / materialized view

---

# 🔁 Recompute Engine

Add method:

```
action_recompute_budget()
```

* delete budget_move
* rebuild from all source docs

---

# 🔐 Security

* Budget User → read only
* Budget Manager → adjust budget

---

# 🧪 Edge Cases

* multi-company
* timezone affecting week boundary
* currency conversion (optional future)
* analytic split rounding

---

# 🚀 Future Extensions

* budget reallocation
* carry forward unused budget
* approval override (VIP analytic)

---

# ✅ Deliverables

* models updated
* compute methods
* blocking hooks
* test cases:

  * over budget
  * partial billing
  * analytic split
  * multi department
