# Duplicate PR (Purchase Requisition) Feature

## Overview
This feature allows users to quickly duplicate an existing Purchase Requisition with all its line items in draft state. This is useful for creating similar requisitions without having to manually enter all the products again.

## Implementation Details

### What Gets Duplicated
When duplicating a PR, the following information is copied to the new requisition:
- **Employee**: Same employee who created the original PR
- **Department**: Same department
- **Manager User**: Same manager user ID
- **Responsible User**: Same responsible user
- **Company**: Same company
- **Request Plan**: Same planned purchase details
- **Requisition Deadline**: Same deadline date
- **Delivery Locations**: Same source and destination locations
- **Delivery Type**: Same delivery type settings
- **Description**: Same requisition description and purpose
- **All Requisition Lines**: Complete copy of all product items including:
  - Product
  - Description
  - Quantity
  - Unit of Measure
  - Unit Price
  - Analytic Distribution
  - Remarks

### What Gets Reset
The following fields are reset for the new requisition:
- **State**: Set to "draft" so it can be edited and resubmitted
- **Vendor/Partner**: Cleared to allow fresh vendor selection
- **Requisition Date**: Set to today's date
- **Reference Number**: Auto-generated new reference number

## How to Use

### Steps to Duplicate a PR:
1. Open an existing Purchase Requisition in any state (except cancelled)
2. Click the **"Duplicate PR"** button in the form header
3. The system will automatically:
   - Create a new requisition with the same data
   - Reset the state to "draft"
   - Clear vendor selections for fresh selection
   - Assign a new reference number
4. The new duplicated PR will be displayed in edit mode
5. You can now modify any details as needed and submit for approval

### Availability
- The "Duplicate PR" button is visible for all PR states except "cancelled"
- The button is located in the form header next to other action buttons

## Features
- ✅ Copies all product line items automatically
- ✅ Preserves analytical distribution codes
- ✅ Maintains employee and department information
- ✅ Resets to draft state for editing
- ✅ Clears vendor selections for fresh procurement
- ✅ Auto-generates new reference number
- ✅ Preserves delivery locations and settings

## User Workflow Example
1. Create and submit PR #001 with 5 items for monthly supplies
2. After receiving and processing, you need to create a similar PR
3. Open PR #001 and click "Duplicate PR"
4. A new draft PR #002 is created with the same 5 items
5. You can adjust quantities, prices, or select different vendors
6. Submit the new PR #002 for approval

## Technical Details

### Model: `employee.purchase.requisition`
**Method**: `action_duplicate_requisition()`
- Location: `/models/employee_purchase_requisition.py`
- Type: Object action
- Access: Available to all users who can view PRs

### View Button
- Location: `/views/employee_purchase_requisition_views.xml`
- Button Name: "Duplicate PR"
- Button Class: Standard button (non-highlighted)
- Visibility: Hidden when state = 'cancelled'

## Benefits
1. **Time Saving**: No need to manually re-enter product information
2. **Accuracy**: Ensures consistency across similar requisitions
3. **Efficiency**: Quick setup for recurring purchases
4. **Flexibility**: Can modify any details before submission
5. **Traceability**: Original and duplicated PRs remain separate for audit trail

## Notes
- The duplicate operation creates a completely independent requisition record
- The original PR is not affected by the duplication
- Multiple duplicates of the same PR can be created
- All approval workflows start fresh for the duplicated PR
