# 🎨 UI Prompt — BOQ & Budget Fix

## 🎯 Objective

Add minimal UI to support new backend logic:

* Close Remaining (MR)
* Close Shortfall (PO)

---

## 🧩 1. MR Button

### Location:

material.requisition form view

### Button:

```
Close Remaining
```

### Behavior:

* visible when:
  state in ('approved', 'ordered')
* calls:
  action_close_remaining

---

## 🧩 2. PO Button

### Location:

purchase.order form

### Button:

```
Close Shortfall
```

### Behavior:

* visible when:
  state in ('purchase')
  AND any line has qty_received < product_qty

---

## 🧩 3. Shortfall Wizard (IMPORTANT)

### Model:

po.shortfall.wizard

### Fields:

* reason (required)
* note

### Flow:

PO → click button → open wizard → confirm → run action

---

## 🧩 4. UX Improvements

### MR:

* show:
  ordered_qty
  received_qty

### BOQ:

* show 3 columns:

  * Requested
  * Ordered
  * Received

---

## 🧩 5. Warning Messages

### MR:

if remaining exists:
→ show banner:
"Some quantities not yet ordered"

### PO:

if shortfall:
→ show banner:
"Supplier has not delivered full quantity"

---

## 🎯 Design Principle

* Minimal disruption
* No extra clicks unless needed
* Clear visibility of gap

---

## 🚫 DO NOT

* No complex UI
* No dashboard yet
* Keep form-based UX

---

## ✅ Deliverables

* Clean XML inherit
* OWL not required (optional later)

---
