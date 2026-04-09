# 🎨 UI Prompt V2 — Shortfall Wizard

## 🔧 Add Warning Banner

IF product.type == 'product':

Show:
"Receiving adjustment will create stock receipt automatically"

---

## 🔧 Column Update

Rename:

* Received → Current Received
* New Received → Adjust Received

---

## 🔧 Validation UX

IF new_received < current_received:

→ show error inline:
"Cannot reduce received quantity"

---

## 🔧 Action Type UI

Radio:

* Cancel Remaining (Return Budget)
* Create New PO for Remaining

Default:
→ Create New PO

---

## 🔧 Confirmation Dialog

Before submit:

Show summary:

* total shortfall
* action type
* affected PO

---
