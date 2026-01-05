# PR Description Transfer - Implementation Summary (สรุปการพัฒนา)

## สรุปภาษาไทย

### สิ่งที่เปลี่ยนแปลง
ปรับปรุงระบบให้สามารถนำ **รายละเอียด (description)** และ **หมายเหตุ (remark)** จากใบขอซื้อ (PR) มาแสดงในใบสั่งซื้อ (PO) อย่างถูกต้อง

### วิธีการทำงาน

**เดิม:**
- ใบสั่งซื้อจะแสดงเฉพาะชื่อสินค้าเท่านั้น
- ข้อมูล description และ remark ที่กรอกในใบขอซื้อจะหายไป

**ใหม่:**
1. ถ้ามีการกรอก **Description** ในใบขอซื้อ → จะนำไปแสดงในใบสั่งซื้อ
2. ถ้าไม่กรอก Description → จะใช้ชื่อสินค้าแทน (เหมือนเดิม)
3. ถ้ามีการกรอก **Remark** → จะนำไปต่อท้าย Description/ชื่อสินค้า (ขึ้นบรรทัดใหม่)

### ตัวอย่างการใช้งาน

**ข้อมูลในใบขอซื้อ (PR):**
```
สินค้า: ท่อเหล็ก 2 นิ้ว
Description: ท่อเหล็กเกรด A ขนาด 2 นิ้ว สำหรับงานโครงสร้าง
Remark: ด่วน! ต้องใช้ภายในสัปดาห์หน้า สำหรับโปรเจค X
```

**ผลลัพธ์ในใบสั่งซื้อ (PO):**
```
ท่อเหล็กเกรด A ขนาด 2 นิ้ว สำหรับงานโครงสร้าง
ด่วน! ต้องใช้ภายในสัปดาห์หน้า สำหรับโปรเจค X
```

### ไฟล์ที่เปลี่ยนแปลง

1. **models/employee_purchase_requisition.py**
   - แก้ไข method `action_create_purchase_order()`
   - เพิ่มโค้ดดึง description และ remark จาก PR มาใส่ใน PO

2. **tests/test_pr_description_transfer.py** (ใหม่)
   - สร้างชุดทดสอบ 4 scenarios
   - ตรวจสอบว่าระบบทำงานถูกต้อง

3. **__manifest__.py**
   - อัพเดทเวอร์ชั่นเป็น 17.0.1.0.4

### วิธีทดสอบ

```bash
# Restart Odoo service
sudo systemctl restart odoo

# หรือ upgrade module
odoo-bin -c /path/to/odoo.conf -d your_database -u employee_purchase_requisition
```

### ข้อดี

✅ ข้อมูลครบถ้วน - รายละเอียดที่กรอกใน PR จะไม่หายไป
✅ สื่อสารชัดเจน - Vendor เห็นข้อมูลเพิ่มเติมและข้อกำหนดพิเศษ
✅ ตรวจสอบได้ - ย้อนดูข้อมูลจาก PR ถึง PO ได้ครบ
✅ ยืดหยุ่น - เลือกใช้ชื่อสินค้าหรือ description ก็ได้
✅ ปลอดภัย - ไม่กระทบข้อมูลเก่า ใช้งานได้ทันที

---

## English Summary

### Changes Made
Enhanced the system to properly transfer **description** and **remark** fields from Purchase Requisitions (PR) to Purchase Orders (PO).

### How It Works

**Before:**
- PO only showed product name
- Description and remark from PR were ignored

**After:**
1. If **Description** is filled in PR → transferred to PO
2. If Description is empty → uses product name (original behavior)
3. If **Remark** is filled → appended below Description/product name

### Example

**PR Line:**
```
Product: Steel Pipe 2 inch
Description: Grade A Steel Pipe - 2 inch for structural work
Remark: Urgent! Needed for Project X next week
```

**PO Line:**
```
Grade A Steel Pipe - 2 inch for structural work
Urgent! Needed for Project X next week
```

### Modified Files

1. **models/employee_purchase_requisition.py** - Core logic
2. **tests/test_pr_description_transfer.py** - Test suite (new)
3. **__manifest__.py** - Version update

### Benefits

✅ Complete information preservation
✅ Better vendor communication
✅ Full traceability
✅ Flexible (description or product name)
✅ Backward compatible

---

## Technical Details

### Code Change

**Location:** `models/employee_purchase_requisition.py` line 401-405

**Previous:**
```python
line_vals = {
    'name': rec.product_id.name,  # Only product name
    ...
}
```

**New:**
```python
# Use description from PR, fall back to product name if not set
description_text = rec.description or rec.product_id.name
if rec.remark:
    description_text = f"{description_text}\n{rec.remark}"

line_vals = {
    'name': description_text,  # Description + Remark
    ...
}
```

### Testing

4 test scenarios created:
1. ✅ Description only
2. ✅ Description + Remark
3. ✅ No description (fallback to product name)
4. ✅ Remark only (with product name)

### Version

- Previous: 17.0.1.0.3
- Current: **17.0.1.0.4**

---

## Installation/Upgrade

```bash
# Upgrade the module
odoo-bin -c /etc/odoo.conf -d your_database -u employee_purchase_requisition

# Or restart Odoo service
sudo systemctl restart odoo
```

## Date
Implementation completed: January 5, 2026
