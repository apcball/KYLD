# PR Description Transfer to PO - Implementation Documentation

## Overview
This implementation ensures that when a Purchase Order (PO) is created from a Purchase Requisition (PR), the description and remark fields from the PR lines are properly transferred to the PO lines.

## What Changed

### File: `models/employee_purchase_requisition.py`

**Method Modified**: `action_create_purchase_order()`

**Previous Behavior**:
- Only the product name was used in the PO line's `name` field
- Custom descriptions and remarks from PR were ignored

**New Behavior**:
- **Description**: If a custom description is entered in the PR line, it will be used in the PO
- **Fallback**: If no description is entered, the product name is used (original behavior)
- **Remark**: If a remark is entered, it will be appended to the description/product name with a line break

### Logic Flow

```python
# Use description from PR, fall back to product name if not set
description_text = rec.description or rec.product_id.name
if rec.remark:
    description_text = f"{description_text}\n{rec.remark}"

line_vals = {
    'name': description_text,  # Now includes PR description + remark
    ...
}
```

## Test Scenarios

Four test scenarios have been created to verify the functionality:

### 1. Description Only
- **Input**: PR line with custom description
- **Expected Output**: PO line uses the custom description

### 2. Description + Remark
- **Input**: PR line with both description and remark
- **Expected Output**: PO line contains description + line break + remark

### 3. No Description (Fallback)
- **Input**: PR line without description
- **Expected Output**: PO line uses product name (original behavior)

### 4. Remark Only (with Product Name)
- **Input**: PR line with remark but no description
- **Expected Output**: PO line contains product name + line break + remark

## Testing

To run the tests:

```bash
odoo-bin -c /path/to/odoo.conf -d database_name -i employee_purchase_requisition --test-enable --stop-after-init
```

Or run specific test:

```bash
odoo-bin -c /path/to/odoo.conf -d database_name --test-tags employee_purchase_requisition.test_pr_description_transfer
```

## User Guide

### How to Use

1. **Create a Purchase Requisition**
   - Navigate to Purchase Requisition menu
   - Create a new requisition

2. **Add Products with Custom Descriptions**
   - In the requisition lines:
     - Select a product
     - **Description field**: Enter custom description (optional)
       - If empty, the product name will be used
     - **Remark field**: Add additional notes (optional)
       - This will be appended below the description

3. **Create Purchase Order**
   - After approval, click "Create Purchase Order"
   - The system will:
     - Transfer the description (or product name if empty)
     - Append the remark if entered
     - Create PO lines with the combined text

### Example

**PR Line Input:**
- Product: "Steel Pipe 2 inch"
- Description: "Grade A Steel Pipe - 2 inch diameter"
- Remark: "Urgent: Required for Project X"

**PO Line Output:**
```
Grade A Steel Pipe - 2 inch diameter
Urgent: Required for Project X
```

## Benefits

1. **Accurate Documentation**: Detailed descriptions from PR are preserved in PO
2. **Communication**: Important remarks reach vendors through PO
3. **Traceability**: Full context from requisition to purchase
4. **Flexibility**: Can use product name or custom description
5. **Additional Notes**: Remark field for special instructions

## Version History

- **v17.0.1.0.4** (2026-01-05)
  - Added PR description and remark transfer to PO
  - Created test suite for description transfer
  - Updated documentation

## Files Modified

1. `/models/employee_purchase_requisition.py` - Core logic
2. `/tests/test_pr_description_transfer.py` - Test cases (new)
3. `/tests/__init__.py` - Test module registration (new)
4. `__manifest__.py` - Version update

## Backward Compatibility

This change is **fully backward compatible**:
- Existing PRs without descriptions will continue to work (uses product name)
- No database migration required
- No changes to existing data structures
- Existing POs are not affected

## Technical Notes

### Field Mapping

| PR Field | PO Field | Priority |
|----------|----------|----------|
| `requisition.order.description` | `purchase.order.line.name` | Primary |
| `product.product.name` | `purchase.order.line.name` | Fallback |
| `requisition.order.remark` | Appended to `purchase.order.line.name` | Additional |

### Data Flow

```
PR Line (requisition.order)
    ├─ description (Text)
    ├─ remark (Text)
    └─ product_id.name (Char)
            ↓
    action_create_purchase_order()
            ↓
PO Line (purchase.order.line)
    └─ name = description or product_name + "\n" + remark
```

## Future Enhancements

Potential improvements for future versions:
1. Add configuration to choose description format
2. Support for HTML formatting in descriptions
3. Multi-language description support
4. Description templates
5. Description history/audit log
