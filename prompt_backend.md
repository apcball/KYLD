# 🧠 Backend Prompt — BOQ & Budget Fix (Patch Existing Modules)

## 🎯 Objective

Upgrade existing modules:

* job_costing_management
* biz_weekly_budget

To correctly support:

* Partial PO
* Short shipment
* Accurate BOQ tracking (PO-based)
* Partial budget reservation

⚠️ DO NOT rewrite modules. Only patch / extend.

---

## 🔧 1. BOQ Tracking Fix (CRITICAL)

### File:

job_costing_management/models/boq.py

### Modify:

_method: `_compute_purchase_tracking`

### Requirements:

1. Keep `total_requisitioned_qty` logic unchanged

2. Replace:

* total_ordered_qty → derive from purchase.order.line
* total_received_qty → derive from qty_received

### Logic:

* Find PO lines:

  * linked via `material_requisition_line_id`
  * state in: purchase, done
* Sum:

  * ordered = product_qty
  * received = qty_received

### Add optimization:

* Use grouped read (read_group) instead of search loop

---

## 🔧 2. Fix State Bug (VERY IMPORTANT)

### Problem:

MR cancel uses:

* 'cancel'
* but BOQ filters 'cancelled'

### Fix:

Standardize ALL to:

```
state = 'cancelled'
```

### Update:

* material_requisition
* purchase override
* any filter logic

---

## 🔧 3. Partial MR Budget Reservation

### File:

biz_weekly_budget/models/material_requisition.py

### Modify:

_method: `_update_budget_moves`

### New Logic:

For each MR:

1. Calculate:

```
mr_total = sum(line.total_cost)
```

2. Calculate PO covered:

* sum price_subtotal from PO lines (exclude cancelled PO)

3. Compute:

```
uncovered_amount = mr_total - po_covered_amount
```

4. Reserve ONLY uncovered_amount

### Edge Cases:

* if uncovered_amount <= 0 → remove reservation
* prevent duplicate budget.move

---

## 🔧 4. Add MR Action: Close Remaining

### Model:

material.requisition

### Method:

```
action_close_remaining()
```

### Logic:

For each line:

* find linked PO lines (exclude cancel)
* actual_ordered = sum(product_qty)

IF:

```
actual_ordered < line.quantity
```

THEN:

* reduce line.quantity → actual_ordered
* log message

After loop:

* call:

  * _update_budget_moves()
  * recompute BOQ

---

## 🔧 5. Add PO Action: Close Shortfall

### Model:

purchase.order

### Method:

```
action_close_shortfall()
```

### Logic:

For each line:

```
shortfall = product_qty - qty_received
```

IF shortfall > 0:

* set product_qty = qty_received

IF linked MR line exists:

* reduce MR line qty accordingly

After:

* trigger:

  * budget recompute
  * BOQ recompute

---

## 🔧 6. Fix PO Cancel Cascade

### File:

purchase_order.py

### Modify:

button_cancel()

### New Behavior:

DO NOT cancel MR immediately

Check:

* any other active PO linked to same MR?

IF YES:

* do nothing

IF NO:

* set MR → approved (NOT cancelled)

---

## 🔧 7. Data Integrity Safeguards

Add constraints:

1. MR line qty >= ordered qty
2. PO qty >= received qty
3. Cannot reduce below received

---

## 🔧 8. Logging / Audit

For ALL actions:

* message_post()
* include:

  * user
  * qty changed
  * reason (if available)

---

## 🧪 9. Test Scenarios (MUST PASS)

### Case 1:

MR 100 → PO 70
→ BOQ remaining = 30

### Case 2:

PO 70 → receive 50 → close shortfall
→ BOQ remaining increases by 20

### Case 3:

Cancel PO
→ MR returns to approved

### Case 4:

Budget reflects partial only

---

## ⚡ Performance Notes

* Avoid N+1 search
* Use read_group
* Add index:

  * material_requisition_line_id

---

## 🚫 DO NOT

* Do not remove MR logic
* Do not change existing workflows
* Do not break backward compatibility

---

## ✅ Deliverables

* Clean patch
* No duplicate records
* Migration safe

---
