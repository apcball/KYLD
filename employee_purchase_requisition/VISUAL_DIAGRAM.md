# Visual Flow Diagram - PR Description Transfer

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PURCHASE REQUISITION (PR)                       │
│                  Model: employee.purchase.requisition               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                │ One2many
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     PR LINES (Requisition Order)                    │
│                      Model: requisition.order                       │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ Fields:                                                       │ │
│  │  • product_id        → Product                               │ │
│  │  • description       → Custom description (Text) ◄───────┐   │ │
│  │  • remark           → Additional notes (Text) ◄────────┐ │   │ │
│  │  • quantity         → Quantity                         │ │   │ │
│  │  • unit_price       → Price                            │ │   │ │
│  │  • partner_id       → Vendor                           │ │   │ │
│  └──────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                │ [User clicks "Create PO"]
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              METHOD: action_create_purchase_order()                 │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ NEW LOGIC:                                            USES:  │ │
│  │                                                              │ │
│  │ 1. Get description from PR line ─────────────────────┐      │ │
│  │    • If empty, use product.name                      │      │ │
│  │                                                       │      │ │
│  │ 2. Check if remark exists ──────────────────────┐    │      │ │
│  │    • If yes, append to description              │    │      │ │
│  │      with newline character                     │    │      │ │
│  │                                                  │    │      │ │
│  │ 3. Create PO line with combined text ◄──────────┴────┘      │ │
│  │                                                              │ │
│  └──────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       PURCHASE ORDER (PO)                           │
│                       Model: purchase.order                         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                │ One2many
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     PO LINES (Order Lines)                          │
│                   Model: purchase.order.line                        │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ Fields:                                                       │ │
│  │  • name ◄────────── RECEIVES: description + "\n" + remark    │ │
│  │  • product_id       → Same product                           │ │
│  │  • product_qty      → Same quantity                          │ │
│  │  • price_unit       → Same price                             │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Example Data Flow

```
SCENARIO 1: Description + Remark
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PR LINE INPUT:
┌────────────────────────────────────────────────────────┐
│ Product:     Steel Pipe 2"                             │
│ Description: "Grade A Steel - 2 inch diameter"         │
│ Remark:      "Urgent: Needed by Friday"                │
└────────────────────────────────────────────────────────┘
                        ↓
                [PROCESSING]
                        ↓
              description_text = "Grade A Steel - 2 inch diameter"
                        ↓
              remark exists? YES
                        ↓
              description_text = "Grade A Steel - 2 inch diameter\nUrgent: Needed by Friday"
                        ↓
PO LINE OUTPUT:
┌────────────────────────────────────────────────────────┐
│ Name:  Grade A Steel - 2 inch diameter                │
│        Urgent: Needed by Friday                        │
└────────────────────────────────────────────────────────┘


SCENARIO 2: Description Only
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PR LINE INPUT:
┌────────────────────────────────────────────────────────┐
│ Product:     Steel Pipe 2"                             │
│ Description: "High quality pipe for construction"      │
│ Remark:      (empty)                                   │
└────────────────────────────────────────────────────────┘
                        ↓
                [PROCESSING]
                        ↓
              description_text = "High quality pipe for construction"
                        ↓
              remark exists? NO
                        ↓
PO LINE OUTPUT:
┌────────────────────────────────────────────────────────┐
│ Name:  High quality pipe for construction             │
└────────────────────────────────────────────────────────┘


SCENARIO 3: No Description (Product Name Fallback)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PR LINE INPUT:
┌────────────────────────────────────────────────────────┐
│ Product:     Steel Pipe 2"                             │
│ Description: (empty)                                   │
│ Remark:      (empty)                                   │
└────────────────────────────────────────────────────────┘
                        ↓
                [PROCESSING]
                        ↓
              description_text = "Steel Pipe 2"" (from product.name)
                        ↓
              remark exists? NO
                        ↓
PO LINE OUTPUT:
┌────────────────────────────────────────────────────────┐
│ Name:  Steel Pipe 2"                                   │
└────────────────────────────────────────────────────────┘


SCENARIO 4: Remark Only (with Product Name)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PR LINE INPUT:
┌────────────────────────────────────────────────────────┐
│ Product:     Steel Pipe 2"                             │
│ Description: (empty)                                   │
│ Remark:      "Handle with care - fragile packaging"   │
└────────────────────────────────────────────────────────┘
                        ↓
                [PROCESSING]
                        ↓
              description_text = "Steel Pipe 2"" (from product.name)
                        ↓
              remark exists? YES
                        ↓
              description_text = "Steel Pipe 2"\nHandle with care - fragile packaging"
                        ↓
PO LINE OUTPUT:
┌────────────────────────────────────────────────────────┐
│ Name:  Steel Pipe 2"                                   │
│        Handle with care - fragile packaging           │
└────────────────────────────────────────────────────────┘
```

## Code Logic Flowchart

```
                          START
                            │
                            ▼
              ┌─────────────────────────────┐
              │ Loop through PR lines       │
              │ (requisition_order_ids)     │
              └──────────────┬──────────────┘
                            │
                            ▼
              ┌─────────────────────────────┐
              │ Check: rec.description      │
              │ has value?                  │
              └──────────┬──────────────────┘
                        │
              ┌─────────┴─────────┐
              │                   │
             YES                 NO
              │                   │
              ▼                   ▼
   ┌──────────────────┐  ┌──────────────────┐
   │ description_text │  │ description_text │
   │ = rec.description│  │ = product.name   │
   └──────┬───────────┘  └────────┬─────────┘
          │                       │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │ Check: rec.remark     │
          │ has value?            │
          └───────┬───────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
       YES                 NO
        │                   │
        ▼                   │
┌───────────────────┐       │
│ description_text  │       │
│ += "\n" + remark  │       │
└───────┬───────────┘       │
        │                   │
        └─────────┬─────────┘
                  │
                  ▼
      ┌───────────────────────┐
      │ Create PO line with   │
      │ name = description_text│
      └───────────┬───────────┘
                  │
                  ▼
                 END
```

## Test Coverage Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TEST SCENARIOS                               │
└─────────────────────────────────────────────────────────────────────┘

Test 1: test_description_transfer_with_description_only
  Input:  description = "Custom description"
          remark = None
  Output: PO line name = "Custom description"
  Status: ✅ PASS

Test 2: test_description_transfer_with_description_and_remark
  Input:  description = "Custom description"
          remark = "Important: Handle with care"
  Output: PO line name = "Custom description\nImportant: Handle with care"
  Status: ✅ PASS

Test 3: test_description_fallback_to_product_name
  Input:  description = None
          remark = None
  Output: PO line name = "Test Product" (product name)
  Status: ✅ PASS

Test 4: test_description_with_remark_only
  Input:  description = None
          remark = "Urgent order"
  Output: PO line name = "Test Product\nUrgent order"
  Status: ✅ PASS
```

## Integration Points

```
┌──────────────────┐
│  Odoo Standard   │
│  PO Module       │
└────────┬─────────┘
         │
         │ Inherits
         │
         ▼
┌──────────────────────────────────────────┐
│  Custom: employee_purchase_requisition   │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │ Models:                            │ │
│  │ • employee.purchase.requisition    │ │
│  │ • requisition.order                │ │
│  │ • purchase.order (inherited)       │ │
│  └────────────────────────────────────┘ │
│                                          │
│  ┌────────────────────────────────────┐ │
│  │ Key Method:                        │ │
│  │ action_create_purchase_order()     │ │
│  │   ↳ Modified for description       │ │
│  │     transfer                       │ │
│  └────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```
