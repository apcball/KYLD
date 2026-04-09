# 🧠 Backend Prompt V2 — Shortfall Wizard (Safe Mode)

## 🎯 Objective

Enhance Shortfall Wizard with:

* Editable received qty (SAFE)
* Optional new PO creation
* Full consistency with stock + budget + BOQ

⚠️ CRITICAL: Must NOT break stock valuation or FIFO

---

## 🔧 1. Wizard Line Model

### New Model:

po.shortfall.wizard.line

Fields:

* product_id (readonly)
* product_qty (ordered)
* qty_received (readonly current)
* new_qty_received (editable)
* shortfall (computed)

---

## 🔧 2. Received Qty Update Logic (CRITICAL)

### DO NOT:

write directly to `qty_received` for storable products

---

### IMPLEMENT:

```
if product.type == 'product':

    diff = new_qty_received - qty_received

    IF diff > 0:
        → create stock.picking (incoming)
        → create stock.move (qty = diff)
        → validate picking

    IF diff < 0:
        → raise error (cannot reduce received)
```

---

### SERVICE PRODUCT:

```
if product.type == 'service':
    po_line.qty_received = new_qty_received
```

---

## 🔧 3. Action Type Logic

### Field:

action_type

Options:

* cancel
* create_po

---

## 🔧 4. Cancel Remaining Flow

FOR each line:

```
new_order_qty = new_qty_received
```

### Rules:

* must >= received
* write:

```
po_line.product_qty = new_order_qty
```

### MR Sync:

```
mr_line.quantity = new_order_qty
```

---

## 🔧 5. Create New PO Flow (IMPORTANT)

### Step 1: Close current PO

```
po_line.product_qty = new_qty_received
```

---

### Step 2: Calculate shortfall

```
shortfall = original_qty - new_qty_received
```

---

### Step 3: Create new PO

```
new_po = purchase.order.create({
    partner_id: same,
    origin: old_po.name,
})
```

### Add lines:

```
product_qty = shortfall
price_unit = same
material_requisition_line_id = same
```

---

### Step 4: IMPORTANT RULE

DO NOT modify MR quantity

→ keep demand intact

---

## 🔧 6. Budget Sync

After BOTH flows:

```
_update_budget_moves()
```

---

## 🔧 7. BOQ Sync

Trigger recompute:

* ordered_qty
* received_qty

---

## 🔧 8. Constraints

* new_received <= ordered
* cannot reduce received
* cannot create negative shortfall

---

## 🔧 9. Audit Log

message_post:

* before qty
* after qty
* action_type
* reason

---

## 🧪 10. Test Cases

### Case A:

0 received → user input 10 → system creates picking

### Case B:

received 50 / ordered 70 → create_po
→ new PO 20

### Case C:

cancel mode → MR reduced

---

## 🚫 DO NOT

* DO NOT write qty_received directly (product)
* DO NOT bypass stock.move
* DO NOT break valuation layer

---
