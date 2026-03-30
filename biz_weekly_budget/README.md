# Weekly Budget Control Module

## ภาพรวม (Overview)

**biz_weekly_budget** เป็นโมดูล Odoo 17 สำหรับควบคุมงบประมาณรายสัปดาห์สำหรับใบสั่งซื้อ (Purchase Orders), ใบขอซื้อ (Purchase Requisitions), ใบเบิกวัสดุ (Material Requisitions) และ ระบบบัญชี (Vendor Bills) โดยมีฟีเจอร์หลักคือการควบคุมยอดการใช้งาน (Used), ยอดจอง (Reserved), และการบล็อกการดำเนินการเมื่องบประมาณรายสัปดาห์ถูกใช้เกินกำหนด พร้อมระบบแดชบอร์ด (Dashboard) และการแจ้งเตือน

โมดูลนี้ใช้แนวคิด **Accrual / Cashflow Budget Hybrid** โดยจำแนกอย่างชัดเจนระหว่างงบประมาณที่ถูกจองไว้ (Commitment) และงบประมาณที่มีกำหนดจ่ายชำระจริง (Cashflow)

## คุณสมบัติหลัก (Key Features)

### 1. การจัดการแผนงบประมาณรายสัปดาห์ (Weekly Budget Plan Management)
- สร้างแผนงบประมาณรายสัปดาห์ด้วยช่วงวันที่กำหนดเอง
- สนับสนุนทั้งงบประมาณบริษัทเดียว หรือทุกบริษัท (Multi-company)
- สร้างรหัสอ้างอิงอัตโนมัติ (WB/YYYY/NNNN)
- สถานะเวิร์คโฟลว์: Draft → Confirmed → Done/Cancelled

### 2. การคำนวณงบประมาณแบบ 3 ส่วน (Budget Calculation)
- **ยอดงบประมาณทั้งหมด (Budget Limit):** งบประมาณที่ตั้งไว้ประจำสัปดาห์
- **ยอดใช้งานจริง (Used Amount):** คำนวณจาก **Vendor Bills (Invoices)** ที่สร้างขึ้น (อิงจาก `invoice_date_due` หรือวันที่ครบกำหนดชำระ)
- **ยอดจองงบประมาณ (Reserved Amount):** คำนวณล่วงหน้าจาก:
  1. Purchase Requisitions (PR) ที่อนุมัติแล้ว
  2. Material Requisitions (MR) ที่ส่งคำขอแล้ว
  3. Standalone RFQs (PO สถานะ draft ที่ไม่ได้เชื่อมโยงกับ PR/MR)
  4. Purchase Orders (PO) ที่ยืนยันแล้ว (แต่ยังไม่ได้สร้าง Vendor Bill ทั้งหมด)
- **งบประมาณคงเหลือ (Available Amount):** คำนวณจาก `Budget Limit - Used Amount - Reserved Amount`

> **หมายเหตุ:** เมื่อมีการตั้งเบิก (Create Vendor Bill) ยอด Reserved จาก PO จะถูกเปลี่ยนเป็นยอด Used แบบอัตโนมัติ (และรองรับการทยอยตั้งเบิก Partial Bills)

### 3. แดชบอร์ดสรุปข้อมูลงบประมาณ (OWL Smart Dashboard)
- แดชบอร์ดแบบโต้ตอบ (Interactive Dashboard) พัฒนาด้วยเทคโนโลยี OWL และ Chart.js
- แสดงกราฟเปรียบเทียบงบประมาณที่ตั้งไว้ ยอดจอง และยอดค่าใช้จ่ายที่คาดว่าจะเกิดขึ้นจริง (Limit vs Reserved vs Forecasted Cashflow/Used)

### 4. การบล็อกการดำเนินการเมื่องบเกิน (Budget Exceed Blocking)
- **Purchase Orders**: บล็อกตอนกด "Send for Review" และ "Confirm"
- **Purchase Requisitions**: บล็อกตอนกด "Head Approve"
- **Material Requisitions**: บล็อกตอนกด "Submit"
- ระบบจะตรวจสอบยอดคงเหลือ (Available) ก่อนทำการอนุมัติ เพื่อป้องกันการใช้งบเกินกำหนด

### 5. ระบบแจ้งเตือน (Notification System)
- ส่งอีเมลแจ้งเตือนเมื่องบประมาณเกินกำหนด
- โพสต์ข้อความใน chatter ของแผนงบประมาณ
- กำหนดผู้รับแจ้งเตือนได้ในแผนงบประมาณ

### 6. การปรับงบประมาณและประวัติ (Budget Adjustment & History)
- Wizard สำหรับปรับงบประมาณรายสัปดาห์
- บันทึกประวัติการปรับเปลี่ยน (Adjustment History) พร้อมเหตุผลและผู้ทำรายการ
- สิทธิ์: Budget Manager เท่านั้นที่ปรับได้

## โครงสร้างโมดูล (Module Structure)

```text
biz_weekly_budget/
├── models/
│   ├── weekly_budget_plan.py      # โมเดลแผนงบประมาณรายสัปดาห์
│   ├── weekly_budget_line.py      # โมเดลรายการงบประมาณและคำนวณยอด (Used/Reserved)
│   ├── purchase_order.py          # ส่วนขยาย PO
│   ├── purchase_requisition.py    # ส่วนขยาย PR
│   ├── material_requisition.py    # ส่วนขยาย MR
│   ├── account_move.py            # ส่วนขยาย Vendor Bill สำหรับคำนวณ Used
│   └── weekly_budget_report.py    # โมเดลสำหรับรายงาน
├── wizard/
│   └── budget_adjustment_wizard.py # Wizard ปรับงบประมาณ
├── views/
│   ├── weekly_budget_plan_views.xml
│   ├── weekly_budget_line_views.xml
│   ├── purchase_order_views.xml
│   ├── purchase_requisition_views.xml
│   ├── material_requisition_views.xml
│   ├── dashboard_views.xml        # วิวสำหรับแสดง Dashboard
│   ├── weekly_budget_report_views.xml
│   └── menu_views.xml
├── static/src/                    # โค้ดสำหรับ OWL Dashboard
│   ├── js/budget_dashboard.js
│   ├── scss/budget_dashboard.scss
│   └── xml/budget_dashboard.xml
├── security/
│   ├── budget_security.xml       # กลุ่มผู้ใช้และ Record Rules
│   └── ir.model.access.csv       # สิทธิ์การเข้าถึง
└── data/
    ├── sequence_data.xml          # Sequence สำหรับรหัสอ้างอิง
    └── mail_template_data.xml     # เทมเพลตอีเมลแจ้งเตือน
```

## การติดตั้ง (Installation)

### Dependencies
- `web` - สำหรับ OWL Dashboard
- `purchase` - ใบสั่งซื้อ
- `mail` - ระบบอีเมลและการแจ้งเตือน
- `employee_purchase_requisition` - ใบขอซื้อพนักงาน
- `job_costing_management` - การจัดการต้นทุนงาน (สำหรับ Material Requisition)
- `buz_po_portal` - พอร์ทัลใบสั่งซื้อ (สำหรับ Send for Review)

### ขั้นตอนการติดตั้ง
1. คัดลอกโฟลเดอร์ `biz_weekly_budget` ไปยัง `custom-addons/`
2. รีสตาร์ท Odoo service
3. อัปเดตรายการแอป: Settings > Apps > Update Apps List
4. ค้นหา "Weekly Budget Control" และกด Install หรือ Upgrade

## การใช้งาน (Usage Guide)

### 1. ดูภาพรวมงบประมาณผ่าน Dashboard
**เส้นทาง:** Purchase > Budget Control > Dashboard
- ตรวจสอบสถานะการใช้งบประมาณรายสัปดาห์ผ่านกราฟ (Chart.js)
- ดูเปรียบเทียบยอด Limit, Used (เงินจ่ายจริง/บิลแจ้งหนี้), และ Reserved (ยอดผูกพัน)

### 2. สร้างและจัดการแผนงบประมาณรายสัปดาห์
**เส้นทาง:** Purchase > Budget Control > Weekly Budget Plans
1. กด **Create** เพื่อสร้างแผนงบประมาณใหม่
2. กรอกข้อมูลช่วงวันที่ (Date From/To), บริษัท (Company/All Companies) และ Default Weekly Amount
3. กำหนด **Notify Users** ที่จะได้รับอีเมลแจ้งเตือน
4. กด **Generate Weeks** เพื่อสร้างงบประมาณรายสัปดาห์ย่อย (จันทร์ - อาทิตย์)
5. กด **Confirm** เพื่อเปิดใช้งานแผน

### 3. ตรวจสอบการใช้งานและยอดจอง (Used & Reserved)
**เส้นทาง:** Purchase > Budget Control > Budget Lines
- ดูรายการงบย่อยรายสัปดาห์ พร้อมสถานะ (Normal / Exceeded)
- ระบบจำแนกยอดค่าใช้จ่ายเป็น:
  - **Used Amount**: บิล (Vendor Bill) ที่ถูกสร้างแล้ว 
  - **Reserved Amount**: ติดสถานะดำเนินการใน PR, MR, RFQ และ PO ที่ยังไม่ได้ออกบิล
  - **Available**: ยอดคงเหลือที่ใช้งานได้จริง
- ปรับเพิ่ม/ลดงบประมาณรายสัปดาห์ (เฉพาะ Budget Manager) โดยกดปุ่ม **Adjust**

### 4. การทำงานร่วมกับระบบจัดซื้อและรวบรวมยอด (PO, PR, MR, Bill)
ระบบคำนวณยอดโควตางบประมาณตามสัดส่วนการชำระหรือยอดที่เหลือ โดยอ้างอิงจาก **Expected Payment Date / Due Date**:
- **Partial Billing:** กรณีแจ้งเบิกบิลเพียงแค่ส่วนเดียว ยอดบิลที่เกิดจะวิ่งเข้างบเป็น Used ตาม Due Date ของบิล และยอด PO ที่ยังไม่ได้เบิก (Remaining to bill) จะยังคงค้างอยู่ในงบ Reserved ตาม Expected Payment Date ของ PO 
- **Cancel Bill:** หากบิลตีกลับหรือยกเลิก ยอดจะถูกดึงกลับมาจากงบ Used เข้าสู่งบ Reserved ตามเอกสารต้นทาง

## การตั้งค่า (Configuration)

### วันที่ที่ใช้ในการดึงงบประมาณ (Target Date / Cashflow Projection)
โมดูลนี้ใช้แนวคิด **Cash Outflow Date** ในการผูกข้อมูลเข้ากับสัปดาห์:
- **Vendor Bill**: อิงจาก `invoice_date_due` (วันครบกำหนดชำระ)
- **Purchase Orders**: อิงจาก `expected_payment_date` (วันที่คาดว่าจะจ่าย)
- **Purchase Requisitions**: อิงจาก Requisition Deadline (หรือบวกเพิ่มตามเงื่อนไขเครดิตรอบจ่าย)
- **Material Requisitions**: อิงจาก Required Date

## สิทธิ์การใช้งาน (User Permissions)

- **Budget User**: ดูข้อมูลงบประมาณและ Dashboard ได้ แต่แก้ไขไม่ได้
- **Budget Manager**: สร้างแผน, ดู Dashboard, และมีปุ่มปรับงบประมาณ (Adjust Budget) พร้อมเขียนคำอธิบาย
- **Purchase Users**: มีสิทธิ์ดูข้อมูล budget lines เพื่อให้ทำงานร่วมกับ PO/PR/MR ได้

## การแก้ไขปัญหา (Troubleshooting)

### ยอดงบประมาณไม่อัปเดตชั่วคราว
ในบางกรณีที่ข้อมูลมีการแก้ไขย้อนหลังจากระบบภายนอก สามารถกดปุ่ม **Recompute Used** ใน Weekly Budget Plan เพื่อบังคับให้ระบบคำนวณยอด Used และ Reserved ใหม่ 100%

### สร้างเอกสารแล้วไม่พบงบประมาณ
- ตรวจสอบฟิลด์วันที่รับรู้การจ่ายเงิน (Expected Payment Date / Due Date) ว่าอยู่ในช่วงวันที่ของแผนงบประมาณที่ Confirmed แล้วหรือไม่
- ตรวจสอบ Company ตรงกับเอกสาร หรือเลือกแผนงานเป็น All Companies หรือยัง

---
**หมายเหตุ**: โมดูลนี้เป็นการยกระดับการจัดการงบประมาณแบบ **Commitment Budget + Cashflow Budget** ทำให้ตัวเลขงบประมาณสะท้อนกระแสเงินสดขาออกในอนาคต (Cash Outflow Forecast) ได้อย่างแม่นยำยิ่งขึ้น
