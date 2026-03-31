# 🎯 Objective

สร้าง UI สำหรับ:

1. Budget Planning แบบ Matrix (Department x Week)
2. Dashboard แบบ Analytic Insight
3. UX ต้องเข้าใจง่ายสำหรับ non-accounting user

Tech:

* OWL (Odoo 17)
* Chart.js

---

# 🧩 1. Budget Planning Matrix

## Concept

Table:

```
        Week1   Week2   Week3
```

Marketing    100k    80k     50k
Sales        200k    150k    100k

---

## Component: budget_matrix_planner

Features:

* Editable grid
* Inline edit (เหมือน Excel)
* Auto save / manual save

Columns:

* Weeks (dynamic from plan)

Rows:

* Department / Analytic

Cell:

* budget_limit

---

## UX Rules

* สีเขียว = available เยอะ
* สีแดง = over budget
* hover → show:

  * used
  * reserved
  * available

---

## Interaction

* click cell → edit
* tab → next cell
* paste (bulk input)

---

# 📊 2. Dashboard

## Component: budget_dashboard_v2

---

## Charts

### 1. Budget vs Used vs Reserved (stacked bar)

* x-axis: week
* y-axis: amount

---

### 2. Department Consumption

* pie chart
* filter by week

---

### 3. Burn Rate

* line chart
* trend per analytic

---

### 4. Over Budget Heatmap (🔥 highlight)

Grid:

```
        Week1   Week2
```

Marketing    OK      OVER
Sales        OK      OK

---

# 🎛️ Filters

Top bar:

* company
* date range
* department
* analytic account

---

# ⚡ Drill Down

Click chart → open list view:

* related PO / PR / Bills

---

# 🔔 Notification UI

* badge alert:

  * “Marketing exceeded budget Week 2”

* clickable → open detail

---

# 🧠 Smart UX

## Suggestion Engine

If budget almost exceeded:

→ show hint:
"Reduce PO amount or move to next week"

---

## Inline Forecast

When user edit budget:

→ preview:

* projected available
* warning before save

---

# 🎨 Visual Design

* modern card layout
* soft shadow
* spacing (padding-lg)
* responsive

---

# 📱 Mobile Behavior

* collapse matrix → list view
* dashboard → scroll cards

---

# 🔌 API Integration

Endpoints:

1. get_budget_matrix
2. update_budget_cell
3. get_dashboard_data
4. get_budget_alerts

---

# 🚀 Performance

* lazy load charts
* debounce input
* batch update (not per cell)

---

# 🧪 UX Edge Cases

* no data → empty state illustration
* large dataset → virtual scroll
* slow compute → loading skeleton

---

# ✅ Deliverables

* OWL components:

  * BudgetMatrixPlanner
  * BudgetDashboardV2

* Chart.js integration

* API controllers

* responsive design
