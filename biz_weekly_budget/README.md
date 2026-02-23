# Weekly Budget Control Module

## ภาพรวม (Overview)

**biz_weekly_budget** เป็นโมดูล Odoo 17 สำหรับควบคุมงบประมาณรายสัปดาห์สำหรับใบสั่งซื้อ (Purchase Orders) และใบขอซื้อ (Purchase Requisitions) โดยมีฟีเจอร์หลักคือการบล็อกการดำเนินการเมื่องบประมาณรายสัปดาห์ถูกใช้เกินกำหนด พร้อมระบบแจ้งเตือนและการติดตามการปรับเปลี่ยนงบประมาณ

## คุณสมบัติหลัก (Key Features)

### 1. การจัดการแผนงบประมาณรายสัปดาห์ (Weekly Budget Plan Management)
- สร้างแผนงบประมาณรายสัปดาห์ด้วยช่วงวันที่กำหนดเอง
- สนับสนุนทั้งงบประมาณบริษัทเดียว หรือทุกบริษัท (Multi-company)
- สร้างรหัสอ้างอิงอัตโนมัติ (WB/YYYY/NNNN)
- สถานะเวิร์คโฟลว์: Draft → Confirmed → Done/Cancelled

### 2. การสร้างงบประมาณรายสัปดาห์อัตโนมัติ (Auto-generate Weekly Lines)
- สร้างงบประมาณรายสัปดาห์อัตโนมัติจากช่วงวันที่ (Monday-Sunday)
- กำหนดงบประมาณเริ่มต้นรายสัปดาห์ได้
- แสดงสถานะ: Normal / Exceeded
- คำนวณยอดใช้งานจริงจาก PO ที่ยืนยันแล้ว

### 3. การบล็อกการดำเนินการเมื่องบเกิน (Budget Exceed Blocking)
- **Purchase Orders**: บล็อกตอนกด "Send for Review" และ "Confirm"
- **Purchase Requisitions**: บล็อกตอนกด "Head Approve"
- **Material Requisitions**: บล็อกตอนกด "Submit"
- แสดงข้อความแจ้งเตือนพร้อมรายละเอียดการเกินงบ

### 4. ระบบแจ้งเตือน (Notification System)
- ส่งอีเมลแจ้งเตือนเมื่องบประมาณเกินกำหนด
- โพสต์ข้อความใน chatter ของแผนงบประมาณ
- กำหนดผู้รับแจ้งเตือนได้ในแผนงบประมาณ

### 5. การปรับงบประมาณ (Budget Adjustment)
- Wizard สำหรับปรับงบประมาณรายสัปดาห์
- บันทึกประวัติการปรับเปลี่ยนพร้อมเหตุผล
- สิทธิ์: Budget Manager เท่านั้นที่ปรับได้

### 6. การแสดงข้อมูลงบประมาณ (Budget Information Display)
- แสดงข้อมูลงบประมาณในฟอร์ม PO, PR, และ MR
- ปุ่ม "Check Budget" สำหรับตรวจสอบงบประมาณ
- แสดงผลเป็น HTML Card พร้อมสถานะและสี

## โครงสร้างโมดูล (Module Structure)

```
biz_weekly_budget/
├── models/
│   ├── weekly_budget_plan.py      # โมเดลแผนงบประมาณรายสัปดาห์
│   ├── weekly_budget_line.py      # โมเดลรายการงบประมาณรายสัปดาห์
│   ├── purchase_order.py          # ส่วนขยาย PO (ตรวจสอบงบ)
│   ├── purchase_requisition.py    # ส่วนขยาย PR (แสดงงบ)
│   └── material_requisition.py    # ส่วนขยาย MR (แสดงงบ)
├── wizard/
│   └── budget_adjustment_wizard.py # Wizard ปรับงบประมาณ
├── views/
│   ├── weekly_budget_plan_views.xml
│   ├── weekly_budget_line_views.xml
│   ├── purchase_order_views.xml
│   ├── purchase_requisition_views.xml
│   ├── material_requisition_views.xml
│   └── menu_views.xml
├── security/
│   ├── budget_security.xml       # กลุ่มผู้ใช้และ Record Rules
│   └── ir.model.access.csv       # สิทธิ์การเข้าถึง
└── data/
    ├── sequence_data.xml          # Sequence สำหรับรหัสอ้างอิง
    └── mail_template_data.xml     # เทมเพลตอีเมลแจ้งเตือน
```

## การติดตั้ง (Installation)

### Dependencies
- `purchase` - ใบสั่งซื้อ
- `mail` - ระบบอีเมลและการแจ้งเตือน
- `employee_purchase_requisition` - ใบขอซื้อพนักงาน
- `job_costing_management` - การจัดการต้นทุนงาน (สำหรับ Material Requisition)
- `buz_po_portal` - พอร์ทัลใบสั่งซื้อ (สำหรับ Send for Review)

### ขั้นตอนการติดตั้ง
1. คัดลอกโฟลเดอร์ `biz_weekly_budget` ไปยัง `custom-addons/`
2. รีสตาร์ท Odoo service
3. อัปเดตรายการแอป: Settings > Apps > Update Apps List
4. ค้นหา "Weekly Budget Control" และกด Install

## การใช้งาน (Usage Guide)

### 1. สร้างแผนงบประมาณรายสัปดาห์

**เส้นทาง:** Purchase > Budget Control > Weekly Budget Plans

1. กด **Create** เพื่อสร้างแผนงบประมาณใหม่
2. กรอกข้อมูล:
   - **Date From/To**: ช่วงวันที่ของแผนงบประมาณ
   - **Company**: เลือกบริษัท หรือเว้นว่างสำหรับทุกบริษัท
   - **Default Weekly Amount**: งบประมาณเริ่มต้นรายสัปดาห์
   - **Notify Users**: เลือกผู้ที่จะได้รับอีเมลแจ้งเตือน
3. กด **Generate Weeks** เพื่อสร้างงบประมาณรายสัปดาห์อัตโนมัติ
4. กด **Confirm** เพื่อเปิดใช้งานแผนงบประมาณ

### 2. ตรวจสอบและปรับงบประมาณรายสัปดาห์

**เส้นทาง:** Purchase > Budget Control > Budget Lines

1. ดูรายการงบประมาณรายสัปดาห์ทั้งหมด
2. ตรวจสอบสถานะ:
   - 🟢 **Normal**: ยอดใช้งานไม่เกินงบ
   - 🔴 **Exceeded**: ยอดใช้งานเกินงบ
3. ปรับงบประมาณ (เฉพาะ Budget Manager):
   - กดปุ่ม **Adjust** ในแถวที่ต้องการปรับ
   - กรอกยอดใหม่และเหตุผล
   - กด **Confirm**

### 3. การใช้งานกับ Purchase Orders

**เมื่อสร้าง PO:**
1. ในฟอร์ม PO ไปที่แท็บ **Budget Check**
2. กด **Check Budget** เพื่อตรวจสอบงบประมาณ
3. ระบบจะแสดง:
   - งบประมาณรายสัปดาห์ที่เกี่ยวข้อง
   - ยอดที่ใช้ไปแล้ว (PO ที่ยืนยันแล้ว)
   - ยอด PO ปัจจุบัน
   - ยอดคงเหลือหลังจากยืนยัน PO

**เมื่อกด Send for Review หรือ Confirm:**
- หากงบประมาณเกิน → แสดงข้อผิดพลาดและบล็อกการดำเนินการ
- หากงบประมาณไม่เกิน → ดำเนินการตามปกติ

### 4. การใช้งานกับ Purchase Requisitions

**เมื่อสร้าง PR:**
1. ในฟอร์ม PR ไปที่แท็บ **Budget Check**
2. กด **Check Budget** เพื่อตรวจสอบงบประมาณ
3. ระบบจะแสดงข้อมูลงบประมาณ (แบบประมาณเท่านั้น)

**เมื่อกด Head Approve:**
- หากงบประมาณเกิน → แสดงข้อผิดพลาดและบล็อกการอนุมัติ
- หากงบประมาณไม่เกิน → ดำเนินการตามปกติ

### 5. การใช้งานกับ Material Requisitions

**เมื่อสร้าง MR:**
1. ในฟอร์ม MR ไปที่แท็บ **Budget Check**
2. กด **Check Budget** เพื่อตรวจสอบงบประมาณ
3. ระบบจะแสดงข้อมูลงบประมาณ (แบบประมาณเท่านั้น)

**เมื่อกด Submit:**
- หากงบประมาณเกิน → แสดงข้อผิดพลาดและบล็อกการส่ง
- หากงบประมาณไม่เกิน → ดำเนินการตามปกติ

## สิทธิ์การใช้งาน (User Permissions)

### กลุ่มผู้ใช้ (User Groups)
- **Budget User**: ดูข้อมูลงบประมาณได้อย่างเดียว
- **Budget Manager**: จัดการงบประมาณได้ทุกอย่าง
- **Purchase Users**: ดูข้อมูลงบประมาณได้ (สำหรับตรวจสอบ)

### สิทธิ์การเข้าถึง (Access Rights)
- Budget User: อ่านข้อมูลทั้งหมด ไม่สามารถแก้ไข
- Budget Manager: อ่าน/เขียน/สร้าง/ลบ ข้อมูลทั้งหมด
- Purchase Users: อ่านข้อมูลงบประมาณสำหรับตรวจสอบ

## การตั้งค่า (Configuration)

### 1. กำหนดผู้รับแจ้งเตือน
ในแผนงบประมาณ > เลือก **Notify Users** ที่จะได้รับอีเมลเมื่องบเกิน

### 2. กำหนดงบประมาณรายสัปดาห์
- ใช้ **Default Weekly Amount** สำหรับทุกสัปดาห์
- หรือปรับแต่ละสัปดาห์แยกกันหลังจาก Generate Weeks

### 3. กำหนดขอบเขตบริษัท
- **Single Company**: เลือกบริษัทในช่อง Company
- **All Companies**: ติ๊ก **All Companies** checkbox

## การทำงานของระบบ (How It Works)

### การคำนวณงบประมาณที่ใช้ไป
ระบบจะคำนวณยอดใช้งานจาก:
- **Purchase Orders** ที่มีสถานะ `purchase` หรือ `done`
- ใช้ `date_planned` ของ PO line เพื่อจัดกลุ่มตามสัปดาห์
- รวมเฉพาะ PO ที่อยู่ในขอบเขตบริษัทเดียวกัน

### การตรวจสอบงบประมาณ
ระบบจะ:
1. หา Budget Line ที่ครอบคลุมวันที่ของเอกสาร
2. คำนวณ: `ยอดใช้ไป + ยอดเอกสารปัจจุบัน`
3. ตรวจสอบว่าเกินงบประมาณหรือไม่
4. ถ้าเกิน → บล็อกการดำเนินการและแจ้งเตือน

### การแจ้งเตือนเมื่องบเกิน
เมื่อมีการพยายามดำเนินการที่ทำให้งบเกิน:
1. ส่งอีเมลไปยัง Notify Users ในแผนงบประมาณ
2. โพสต์ข้อความใน chatter ของแผนงบประมาณ
3. แสดงข้อผิดพลาดแก่ผู้ใช้

## ข้อควรทราบ (Important Notes)

### วันที่ที่ใช้ในการตรวจสอบ
- **Purchase Orders**: `date_planned` ของ PO line
- **Purchase Requisitions**: `requisition_deadline` หรือ `request_date`
- **Material Requisitions**: `required_date`

### สัปดาห์ที่ใช้ในระบบ
- ระบบใช้สัปดาห์จันทรุษัย (Monday - Sunday)
- Generate Weeks จะสร้างตั้งแต่วันจันทร์แรกของช่วง Date From

### การบล็อกการดำเนินการ
- **PO**: บล็อกทั้ง Send for Review และ Confirm
- **PR**: บล็อกเฉพาะ Head Approve (ไม่บล็อกการสร้าง)
- **MR**: บล็อกเฉพาะ Submit (ไม่บล็อกการสร้าง)

### การปรับงบประมาณ
- ต้องมีสิทธิ์ Budget Manager เท่านั้น
- บันทึกประวัติการปรับเปลี่ยนทุกครั้ง
- สามารถปรับได้เฉพาะในสถานะ Confirmed

## การแก้ไขปัญหา (Troubleshooting)

### ไม่พบงบประมาณ
- ตรวจสอบว่ามีแผนงบประมาณที่ Confirmed แล้ว
- ตรวจสอบวันที่ของเอกสารอยู่ในช่วงของแผนงบประมาณ
- ตรวจสอบขอบเขตบริษัท (Company/All Companies)

### งบประมาณไม่อัปเดต
- กดปุ่ม **Recompute Used** ในแผนงบประมาณ
- ตรวจสอบว่า PO มีสถานะ purchase/done แล้ว
- ตรวจสอบวันที่ date_planned ของ PO line

### ไม่สามารถปรับงบประมาณ
- ตรวจสอบว่าอยู่ในกลุ่ม Budget Manager
- ตรวจสอบว่าแผนงบประมาณอยู่ในสถานะ Confirmed

## เวอร์ชันและความเข้ากันได้ (Version & Compatibility)

- **Odoo Version**: 17.0
- **Module Version**: 17.0.1.0.0
- **License**: LGPL-3
- **Author**: KYLD

## การอัปเดตและบำรุงรักษา (Updates & Maintenance)

- อัปเดตโมดูลผ่าน Apps > Upgrade
- สำรองข้อมูลก่อนอัปเดต
- ตรวจสอบความเข้ากันได้กับโมดูลอื่นหลังอัปเดต

---

**หมายเหตุ**: โมดูลนี้พัฒนาขึ้นสำหรับระบบงานเฉพาะที่ KYLD และอาจต้องปรับแต่งให้เข้ากับการใช้งานจริงขององค์กร
