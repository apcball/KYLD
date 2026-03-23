# 🧠 Prompt: RFQ Lock Control Module (Odoo)

## 🎯 Objective

Develop an Odoo module to **restrict manual RFQ (Request for Quotation) creation**.

RFQs must only be created from:

* Purchase Request (PR)
* Material Request (MR)
* Automated Procurement (Reordering Rules / Scheduler / MTO)
* Other approved modules via context control

Manual creation from UI, import, or API must be blocked.

---

## 🏗️ Module Name

`buz_purchase_rfq_lock`

---

## ⚙️ Functional Requirements

### 1. Block Manual RFQ Creation

Override `purchase.order.create()`:

* If context does NOT include `allow_create_rfq=True`
* AND not from automated procurement
  → Raise Error

Example error:
"You are not allowed to create RFQ manually. Please use Purchase Request or approved process."

---

### 2. Allow Controlled Creation via Context

Allowed flows must pass:

```python
with_context(allow_create_rfq=True)
```

Also allow:

```python
context.get('from_procurement')
```

---

### 3. Add Source Tracking (Important)

Add field in `purchase.order`:

```python
source_type = fields.Selection([
    ('pr', 'Purchase Request'),
    ('mr', 'Material Request'),
    ('auto', 'Auto Procurement'),
    ('manual_allowed', 'Manual (Special Permission)')
], required=True)
```

Validation:

* RFQ must always have `source_type`
* Reject creation if missing

---

### 4. UI Restriction

Modify views:

* Disable Create button in:

  * tree view
  * form view

```xml
<attribute name="create">false</attribute>
```

---

### 5. Admin Bypass

System Admin (group_system):

* Can create RFQ without restriction
* Must still set `source_type = manual_allowed`

---

### 6. Compatibility

Must NOT break:

* Reordering Rules
* MTO
* Scheduler
* Dropshipping
* Existing purchase workflows

---

### 7. Error Handling

Raise `UserError` when:

* RFQ created without proper context
* Missing source_type

---

## 🧩 Technical Requirements

### Python

* Inherit: `purchase.order`
* Override: `create()`

### XML

* Inherit purchase views
* Disable create

---

## 🧪 Test Cases

### ❌ Should Fail

* User clicks "Create RFQ" manually
* Import RFQ without context
* API create without context

### ✅ Should Pass

* PR → RFQ
* MR → RFQ
* Scheduler creates RFQ
* Reordering Rule creates RFQ
* Admin creates RFQ

---

## 🔐 Security Considerations

* Prevent bypass via RPC/API
* Context must be explicitly validated
* Do NOT rely only on UI restriction

---

## 🚀 Optional Enhancements

### 1. Audit Trail

* Log source document reference (PR/MR ID)

### 2. Approval Layer

* Require approval before RFQ confirmation

### 3. Configurable Mode

* Toggle strict mode ON/OFF via settings

---

## 📦 Deliverables

* Full Odoo module structure:

  * `__manifest__.py`
  * `models/purchase_order.py`
  * `views/purchase_order_views.xml`
  * `security/ir.model.access.csv`

* Clean, production-ready code

---

## 🧠 Notes for AI / Developer

* This module enforces **Procurement Governance**
* Must ensure **data integrity + auditability**
* Avoid breaking standard Odoo flows
* Prefer clean override with minimal side effects

---

## ✅ Expected Outcome

After installation:

* Users cannot create RFQ manually
* All RFQs are traceable to a source
* Procurement flow is fully controlled
* System is audit-ready (ISO 9001 aligned)

---
