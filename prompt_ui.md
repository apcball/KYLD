# 🎨 Prompt: Upgrade Weekly Budget UI → Department + Monthly Hybrid (OWL)

## 🎯 Objective

Upgrade existing UI to support:

* Department-based budget
* Monthly overview + Weekly drilldown
* Allocation by %
* Forecast visibility

---

# 🧭 MENU UPDATE

Purchase > Budget Control

NEW:

* Monthly Budget Plans
* Department Matrix (Monthly)

EXISTING:

* Weekly Plans
* Dashboard (upgrade)

---

# 📊 1. DASHBOARD (UPGRADE)

## KPI:

* Monthly Total Budget
* Used
* Reserved
* Forecast
* Available

---

## Chart 1: Department Overview

Bar Chart:

* X: Department
* Y: Amount
* Series:

  * Limit
  * Used
  * Reserved
  * Forecast

---

## Chart 2: Weekly Trend

Line Chart:

* Weekly usage inside selected month

---

## Chart 3: Budget Health

Pie:

* Used %
* Reserved %
* Available %

---

# 📋 2. MONTHLY PLAN FORM

## Header:

* Month / Year
* Total Budget

---

## Tab: Department Allocation

Editable Grid:

| Department | % | Amount |

---

## UX:

* auto compute amount
* validation = 100%

---

## Button:

* Generate Weekly Plans

---

# 🧮 3. DEPARTMENT MATRIX (MONTHLY)

## Layout:

| Department ↓ | Week 1 | Week 2 | Week 3 | Week 4 |
| ------------ | ------ | ------ | ------ | ------ |
| Sales        |        |        |        |        |

---

## Features:

* inline edit weekly budget
* color:

  * green = ok
  * yellow = >80%
  * red = exceeded

---

# 📊 4. WEEKLY VIEW (DRILL DOWN)

Add:

* Department filter

Columns:

* Limit
* Used
* Reserved
* Forecast
* Available

---

# ⚠️ 5. WARNING MODAL (UPGRADE)

```text
⚠️ Budget Exceeded

Department: Marketing
Weekly Available: 10,000
Monthly Available: 50,000

Requested: 25,000
```

---

# 📨 6. APPROVAL UI

Add:

* show department
* show monthly impact

---

# 🎯 UX PRINCIPLES

* Always show BOTH:

  * Weekly
  * Monthly

* Department must be visible everywhere

* Avoid:
  ❌ analytic references

---

# 🎨 STYLE

* Card-based dashboard
* Matrix grid with sticky header
* Smooth OWL state updates

---

# 🚀 FUTURE READY

Prepare for:

* multi-version budget
* CFO dashboard
* cashflow timeline

---

# 📌 NOTES

* Use API (avoid heavy ORM)
* All amounts formatted
* Optimize for large departments
