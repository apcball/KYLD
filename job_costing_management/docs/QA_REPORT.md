# QA — job_costing_management

วันที่ตรวจ: 12 กันยายน 2026 · ขอบเขต: ตรวจครบและรายงาน ไม่แก้บั๊ก

**ผลรวม: ไม่ผ่าน QA สำหรับการยืนยันความถูกต้องของต้นทุนและการควบคุม workflow** แม้ชุดทดสอบเดิมผ่านทั้งติดตั้งใหม่และอัปเดต พบปัญหาที่ยืนยันจากการทดลอง/หน้าจอ 14 รายการ: P1 จำนวน 7 รายการ และ P2 จำนวน 7 รายการ

P1 = ควรแก้ก่อนใช้งานส่วนที่ได้รับผลกระทบ เพราะยอดเงิน สิทธิ์อนุมัติ หรือการสั่งซื้อผิดพลาด; P2 = workflow การใช้งานหรือรายงานผิดพลาด ไม่มี P0 ที่ยืนยันในการตรวจครั้งนี้

## สภาพแวดล้อมและหลักฐาน

| รายการ | ค่าที่ใช้ตรวจ |
| --- | --- |
| Source revision | `a38dd8f751250914ba47ee5c2fb04c976d700e3c` |
| Module version / author | `17.0.1.0.4` / Apichart Pangsalung ตาม manifest |
| Odoo | `17.0-20260630`, Docker image `odoo:17.0` |
| Image ID | `sha256:f88f646a0f5fc0b225995ee28953d9ce7367cc731b1756765114691fb97d18e5` |
| PostgreSQL | `16.14`, aarch64 |
| Compose project / database | `kyld-job-costing-qa-20260912` / `MOG_TEST` |
| การแยกข้อมูล | Postgres tmpfs ใหม่, addons mount read-only, ปิด cron |
| Browser | Chromium headless build 1243, desktop 1440×1000 |
| ผู้ใช้ UI | Job Costing/Material Requisition Manager พร้อมสิทธิ์ Purchase/Accounting, ผู้ขอทั่วไป, ผู้จัดการบริษัท B |
| สกุลเงิน fixture | บริษัท USD และสกุลทดสอบ QAZ อัตรา 1 QAZ = 2 USD; ไม่ใช่อัตราเงินจริง |

ใช้ `docker-compose.test.yml` ปัจจุบันซึ่งตั้ง `--init=job_costing_management` และ test tags ของโมดูลนี้แล้ว ไม่ต้องแก้ Compose ตามคำอธิบายเก่าใน AGENTS.md

หลักฐานที่เก็บใน repo:

- [ผลทดสอบและข้อความหลักฐาน](qa/qa_20260912_results.txt) รวม log สรุปจาก Odoo runner, ผล diagnostic และ browser/report observations
- [สคริปต์ทำซ้ำกรณี backend](qa/qa_20260912_reproduce.py) สำหรับ Odoo shell ใน Docker แยกเท่านั้น มี guard `MOG_TEST`/host `db` และ rollback ทุก scenario

การตรวจไม่เชื่อมต่อ DEV/PROD, ไม่ deploy, ไม่แก้ source code การทำงานหรือ tests เดิม การเพิ่มไฟล์จำกัดอยู่ใน `docs/` สคริปต์ diagnostic ไม่ถูก import โดย addon

## ผลตรวจตามขอบเขต

| หัวข้อ | ผล | หลักฐาน/ข้อจำกัด |
| --- | --- | --- |
| Python/XML และไฟล์ manifest | Pass | parse Python 39 ไฟล์, XML 39 ไฟล์; ไฟล์ data/demo ที่ประกาศมีครบ |
| ติดตั้งใหม่ | Pass | Odoo runner: **64 tests, 0 failed, 0 errors**, container exit 0 |
| อัปเดตโมดูลบน DB ทดสอบเดิม | Pass | `-u job_costing_management`: **64 tests, 0 failed, 0 errors**, exit 0 |
| BOQ request wizard | Pass ในกรณีที่ตรวจ | เลือก/ไม่เลือก, จำนวนไม่ถูกต้อง, stale data, state, ownership, หลายบริษัทจากชุดเดิม; UI สร้าง draft MR ได้ |
| BOQ → อนุมัติ MR ผ่าน UI ผู้จัดการ | Pass | Submit → Department Approve → Approve; อ่านกลับจาก DB ได้ `approved` |
| อนุมัติ MR ผ่าน API ผู้ขอ | **Fail** | QA-05 |
| Service PO | Pass ใน 18 tests เดิมและ UI drill-down | การแยก description, allocations, currency conversion ของแท็บ, access rules; ไม่ได้แปลว่ายอดรวม Actual ถูกต้อง ดู QA-03 |
| รับสินค้าตรงจาก PO | Pass ใน fixture | รับ 4/10 → Actual 400, รับครบ → 1,000, คืน 2 → 800 โดยสั่ง recompute เพื่อตรวจสูตร |
| Procurement pool | **Fail** | RFQ ซ้ำ, MR บางใบค้าง, คืนสินค้าไม่ลด allocation: QA-06 ถึง QA-08 |
| Timesheet / vendor bill / credit note | **Fail** | ยอดรวมไม่ตรงแหล่งต้นทุน: QA-01, QA-02 |
| เปลี่ยน analytic distribution หลังคำนวณ | **Fail** | stored Actual ไม่อัปเดต: QA-04 |
| หน่วยนับต่างกัน | **Fail** | 1 Dozen ไม่ถูกเทียบเท่า 12 Units: QA-09 |
| หลายบริษัท | Pass เฉพาะ read isolation; **Fail** ความสัมพันธ์ | record rules ซ่อน sheet ต่างบริษัทได้ แต่สร้าง sheet/project คนละบริษัทได้: QA-11 |
| Dashboard | Pass เฉพาะ UI/API behavior | หน้าไทย, ตัวกรองโครงการ, drill-down; ผู้ขอถูกปฏิเสธ API; ความถูกต้องของยอดขึ้นกับบั๊ก Actual |
| หน้าจอหลัก | Pass สำหรับผู้จัดการ; **Fail** ผู้ขอ | เปิด list/form, BOQ, MR, pool, allocation, orders, notes, subcontractors ได้; ผู้ขอเปิด sheet ไม่ได้: QA-10 |
| PDF/XLSX | สร้าง/ดาวน์โหลดได้; **Fail** บางเนื้อหา | PDF ภาษาไทย/เลขเอกสาร: QA-13, QA-14; BOQ XLSX ZIP และข้อความไทยผ่าน |
| pylint-odoo | **Fail (lint)** | 1,903 messages; ไม่ใช่จำนวน runtime bugs ดูรายละเอียดด้านล่าง |
| ข้อมูลจริง/ปริมาณมาก/concurrency | Not tested | ไม่ใช้ live DB, ไม่ทดสอบหลายผู้ใช้พร้อมกันหรือ load test |

64 tests เดิมประกอบด้วย BOQ request 17, BOQ sync 5, dashboard 9, actual costs 10, MR completion 5 และ Service PO 18 กรณี รวมการรันสองรอบเป็น 128 test executions ของ 64 กรณีเดิม ไม่ใช่ 128 กรณีที่ต่างกัน

## ปัญหาที่ยืนยันแล้ว

### QA-01 · P1 — โพสต์ Vendor Bill แล้ว Actual หาย

**ทำซ้ำ:** สร้าง confirmed service PO 10 × 100 พร้อม analytic distribution ของ sheet; สร้าง vendor bill ที่ผูก PO line เดิมแล้ว Post

**คาดหวัง:** Actual ยังคง 1,000 โดยไม่บวก PO และ bill ซ้ำ

**เกิดจริง:** ก่อน Post = 1,000; หลัง Post = 0 แม้ bill เป็น `posted` และ subtotal = 1,000 การออก credit note 200 ต่อจากนั้นยังได้ 0 แทน 800

**ตำแหน่ง:** `models/job_cost_sheet.py:236`, `:259`, `:284`, `:298` — query ตัด PO ทิ้งเมื่อมี posted bill แต่ทั้งสองเส้นทางของ bill กรอง `aml.display_type IS NULL`; invoice product line จริงใน Odoo 17 มีค่า `product` จึงไม่ถูกนับ

**ผลกระทบ:** Actual และ dashboard แสดงต้นทุนต่ำกว่าจริงทันทีที่วางบิล หลักฐาน: `posted_bill`, `vendor_refund`

### QA-02 · P1 — ยอดรวมไม่รวมต้นทุน Timesheet

**ทำซ้ำ:** สร้างพนักงาน hourly cost 100, task ของโครงการ และ timesheet 2 ชั่วโมงที่ผูก labour cost line; recompute รายการย่อยและ sheet

**คาดหวัง:** Actual labour และ total ของ sheet = 200

**เกิดจริง:** timesheet amount = -200, cost line actual = 200 แต่ sheet actual = 0

**ตำแหน่ง:** `models/job_cost_sheet.py:155`, `:305`, `:317` — ยอดรวมใหม่อ่านเฉพาะ PO/bill ขณะที่ `:867` ยังรวม timesheet ในรายการย่อย

**ผลกระทบ:** ต้นทุนแรงงานภายในหายจากยอดรวมและไม่ตรงรายละเอียด หลักฐาน: `timesheet_total`

### QA-03 · P1 — Actual รวมยอดต่างสกุลเงินโดยไม่แปลง

**ทำซ้ำ:** บริษัทและ sheet ใช้ USD; สร้าง service PO 100 QAZ ซึ่งอัตรา ณ วัน PO เท่ากับ 200 USD แล้ว recompute

**คาดหวัง:** Actual = 200 USD

**เกิดจริง:** Actual = 100 ขณะที่ Odoo currency conversion ให้ 200

**ตำแหน่ง:** `models/job_cost_sheet.py:220`, `:247`, `:277`, `:292` — รวม `price_subtotal` ในสกุลเอกสารโดยไม่แปลงก่อนรวม

**ผลกระทบ:** ยอดรวมและ dashboard ใช้หน่วยเงินไม่ถูกต้อง แม้ logic แปลงเงินใน Service PO tab มี tests ผ่าน หลักฐาน: `foreign_currency`

### QA-04 · P1 — เปลี่ยน Analytic Distribution แล้วยอด Actual ที่เก็บไว้ค้าง

**ทำซ้ำ:** service PO 100 ผูก sheet ผ่าน distribution เท่านั้น ไม่มี `job_cost_line_id`; คำนวณยอดแล้วล้าง distribution, flush และ invalidate cache ก่อนอ่าน sheet อีกครั้ง

**คาดหวัง:** sheet เดิมไม่มีต้นทุนจาก PO นี้แล้ว ยอดควรเป็น 0

**เกิดจริง:** stored Actual ยัง 100 แต่ query คำนวณแหล่งข้อมูลใหม่ให้ผลว่าง

**ตำแหน่ง:** `models/job_cost_sheet.py:68`, `:316`; `models/purchase_order.py:374` — stored fields ไม่ได้ผูก dependency กับ analytic distribution และ write hook ไม่จัดการกรณีนี้

**ผลกระทบ:** โหลดหน้าใหม่ยังเห็นยอดเก่า ต้องมีการ recompute อื่นจึงเปลี่ยน หลักฐาน: `analytic_only_freshness`, `distribution_change`

### QA-05 · P1 — ผู้ขออนุมัติใบขอวัสดุเองผ่าน API ได้

**ทำซ้ำ:** ใช้ผู้ใช้ที่มีเฉพาะ `group_material_requisition_user` โดยไม่มี Department Manager หรือ Material Requisition Manager เรียก `action_dept_approve()` และ `action_approve()` บน MR draft อีกกรณีเรียก `write({'state': 'approved'})`

**คาดหวัง:** ปฏิเสธทั้งสิทธิ์ไม่เพียงพอและการข้ามสถานะ

**เกิดจริง:** ทั้งสองกรณีเปลี่ยนเป็น `approved` ได้ และบันทึกผู้ขอเป็นผู้อนุมัติ

**ตำแหน่ง:** `models/material_requisition.py:198`, `:203`, `:210`; `security/ir.model.access.csv` ของ MR user; `views/material_requisition_views.xml` จำกัด groups เฉพาะปุ่ม

**ผลกระทบ:** ข้ามขั้นตอนควบคุมจัดซื้อได้ แม้ปุ่มอนุมัติถูกซ่อนใน UI หลักฐาน: `requester_approval`, `requester_direct_state_write`

### QA-06 · P1 — Procurement Pool สร้าง RFQ ซ้ำเกินความต้องการ

**ทำซ้ำ:** รวม MR 4 และ 6 หน่วยเข้าหนึ่ง pool line, Confirm pool, Create RFQ แล้วเรียก Create RFQ อีกครั้ง โดย flush/invalidate ก่อนรอบสอง

**คาดหวัง:** RFQ รวม 10 หน่วย และปฏิเสธการสร้างเพิ่มเมื่อ demand ถูกครอบคลุมแล้ว

**เกิดจริง:** รอบแรก PO qty = 10 และ allocation = 10 แต่ stored `ordered_qty` ยัง 0; รอบสองได้ 2 PO รวม 20 หน่วย

**ตำแหน่ง:** `models/procurement_pool.py:138`, `:223`, `:390`; `models/purchase_allocation.py:76` — `_compute_quantities` เป็น stored compute ที่ search allocations แต่ dependencies ไม่มีการเปลี่ยน allocation

**ผลกระทบ:** สั่งซื้อซ้ำและสร้าง allocation เกิน demand โดยไม่ต้องมี concurrent requests หลักฐาน: `pool_rfq_initial`, `pool_rfq_repeat`

### QA-07 · P2 — คืนสินค้าจาก Pool แล้ว Received Allocation ไม่ลด

**ทำซ้ำ:** PO จาก pool รับ 4 หน่วยและ backorder อีก 6 จนครบ จากนั้นใช้ Return wizard คืนสินค้า 2 หน่วยและ Validate

**คาดหวัง:** รับสุทธิและ received allocation = 8, pool ไม่ควรแสดงครบรับ 10 ต่อไป

**เกิดจริง:** PO qty_received = 8 แต่ allocation received รวม = 10 และ pool ยัง `done`

**ตำแหน่ง:** `models/stock_picking.py:17`, `:33`; `models/purchase_allocation.py:83` — update ทำเฉพาะ incoming และไม่มีเส้นทาง reverse allocation สำหรับ supplier return

**ผลกระทบ:** จำนวนรับและสถานะ pool ไม่ตรง stock/PO หลักฐาน: `pool_return`

### QA-08 · P2 — MR ใบที่สองใน Pool ค้าง Ordered แม้ซื้อ/รับครบ

**ทำซ้ำ:** รวม MR 4 และ 6 หน่วยเป็น PO line เดียว แล้ว Confirm/รับครบ 10

**คาดหวัง:** MR ทั้งสองใบจบตาม allocation ที่ครอบคลุมจำนวนครบ

**เกิดจริง:** pool เป็น `done`, allocation รับครบ 10 แต่ MR states เป็น `['received', 'ordered']`

**ตำแหน่ง:** `models/procurement_pool.py:195`, `:212`; `models/purchase_order.py:109`; `models/material_requisition.py:171` — PO line ผูก FK กลับได้เพียง MR line แรก และ completion check ไม่อ่าน purchase allocations

**ผลกระทบ:** งานค้างเทียมและตัวติดตาม MR ไม่สอดคล้องการจัดซื้อจริง หลักฐาน: `pool_full_receipt`

### QA-09 · P2 — Completion ของ MR ไม่แปลงหน่วยนับ

**ทำซ้ำ:** MR ขอ 12 Units; confirmed PO ที่ผูก MR line สั่ง 1 Dozen

**คาดหวัง:** สั่งซื้อครบตามนโยบายปัจจุบันของโมดูล และสถานะ MR เป็น `received` ซึ่ง UI เรียก Done

**เกิดจริง:** ยัง `ordered` เพราะเทียบเลข 1 กับ 12 โดยตรง

**ตำแหน่ง:** `models/material_requisition.py:175` รวม `product_qty` โดยไม่แปลง `product_uom` เป็น `line.uom_id`

**ผลกระทบ:** เหลือยอดค้างผิดเมื่อใช้หน่วยซื้อคนละหน่วยกับใบขอ หลักฐาน: `mr_uom`

### QA-10 · P2 — Job Costing User เปิดฟอร์ม Cost Sheet ไม่ได้

**ทำซ้ำ:** ผู้ใช้มี Job Costing User และ Material Requisition User แต่ไม่มี Purchase/Accounting/Timesheet roles เปิด Cost Sheet form

**คาดหวัง:** ผู้ใช้ที่มี read/write ACL ของ sheet เปิดฟอร์มได้ โดยข้อมูลที่ไม่มีสิทธิ์ต้องถูกจัดการตามสิทธิ์

**เกิดจริง:** ฟอร์มไม่ขึ้นและแสดง Access Error: `You are not allowed to access 'Analytic Line' (account.analytic.line) records.`

**ตำแหน่ง:** `models/job_cost_sheet.py:360` — `_compute_timesheet_count` ทำ search_count ด้วยสิทธิ์ผู้เปิดฟอร์ม; กลุ่ม Job Costing User ไม่ได้ให้ analytic-line access

**ผลกระทบ:** role ผู้ใช้งานพื้นฐานไม่สามารถใช้ฟอร์มหลักได้ ยืนยันด้วย browser และภาพหน้าจอ ไม่ได้อนุมานจาก ACL อย่างเดียว

### QA-11 · P1 — บันทึก Sheet และ Project คนละบริษัทได้

**ทำซ้ำ:** ผู้จัดการมีบริษัท A/B และเปิดทั้งสองบริษัท สร้าง Cost Sheet company=A แต่ project อยู่ company=B

**คาดหวัง:** ปฏิเสธความสัมพันธ์คนละบริษัท

**เกิดจริง:** บันทึกสำเร็จ; sheet_company=1 และ project_company=11 ในรอบหลักฐานสุดท้าย

**ตำแหน่ง:** `models/job_cost_sheet.py:18`, `:21` — ไม่มี company-consistency enforcement สำหรับ relation นี้

**ผลกระทบ:** ข้อมูลโครงการ/ต้นทุนข้ามบริษัทและอาจปรากฏผิดกลุ่มในรายงาน **ไม่ได้พบว่าการอ่าน sheet company=B ผ่าน context เฉพาะ A หลุด record rule**; กรณี read isolation นี้ผ่าน หลักฐาน: `cross_company_link`, `cross_company_read_rule`

### QA-12 · P2 — Internal Transfer ใช้ต้นทางเท่าปลายทาง และสร้างซ้ำผ่าน action ได้

**ทำซ้ำ:** เปิดใช้งาน internal picking type ของ warehouse; MR internal 10 หน่วย ไม่มี employee/department destination; เรียก `action_create_picking()` แล้วเรียก action ซ้ำจาก request อีกครั้ง

**คาดหวัง:** ต้องมีปลายทางที่เหมาะสม และป้องกันการสร้าง transfer ซ้ำเต็มจำนวนที่ถูกสร้างไปแล้ว

**เกิดจริง:** ทั้ง source/destination เป็น `WH/Stock`; มี 2 pickings รวม move demand 20 จาก MR 10

**ตำแหน่ง:** `models/material_requisition.py:392`, `:406`, `:418`, `:446` — fallback ใช้ stock location เดียวกัน และไม่มี guard สถานะ/จำนวนที่สร้างแล้วใน action

**ผลกระทบ:** เอกสารโอนอาจไม่มีการย้ายสถานที่จริงและมี demand ซ้ำ ปุ่มถูกซ่อนหลังเปลี่ยนสถานะใน UI แต่ action ยังเรียกซ้ำได้ หลักฐาน: `internal_transfer`

### QA-13 · P2 — Job Cost Sheet PDF แสดงภาษาไทยเป็นสี่เหลี่ยม

**ทำซ้ำ:** โครงการชื่อ `QA โครงการทดสอบ`, รายการ `วัสดุภาษาไทย`; กำหนด currency แล้ว Print Job Cost Sheet บน image ที่ใช้ทดสอบ

**คาดหวัง:** ชื่อโครงการและรายละเอียดไทยอ่านได้

**เกิดจริง:** PDF สร้างและดาวน์โหลดสำเร็จ แต่ตำแหน่งภาษาไทยเป็น square glyphs ยืนยันด้วยการ render PDF เป็นภาพและตรวจภาพจริง

**ตำแหน่ง:** `reports/job_cost_sheet_report.xml:19`, `:26`, `:55` — ใช้ external layout โดยไม่มี Thai font สำหรับ template นี้; PDF มี Lato/DejaVuSans ขณะที่ MR PDF ใน environment เดียวกันใช้ Sarabun และแสดงไทยได้

**ผลกระทบ:** เอกสารส่งต่ออ่านรายละเอียดภาษาไทยไม่ได้ ขอบเขตการยืนยันคือ official Odoo image ที่ระบุ; server ที่ติดตั้ง fonts เพิ่มอาจให้ผลต่างกัน

### QA-14 · P2 — MR PDF ไม่พิมพ์เลขที่เอกสาร และเลขหน้าขัดกัน

**ทำซ้ำ:** Print MR ที่มีชื่อ `MR/0052/2026` และหนึ่งรายการ

**คาดหวัง:** ช่องเลขที่เอกสารมีเลข MR และเลขหน้าตรงกับ PDF จริง

**เกิดจริง:** มีข้อความ `เลขที่เอกสาร:` แต่ไม่มีค่า; PDF มี 2 หน้า แต่ custom header หน้าแรกระบุ `1 / 1` ขณะที่ footer ระบุ `1 / 2`

**ตำแหน่ง:** `reports/material_requisition_report.xml:190` มี label อย่างเดียว ไม่มี field เลข MR; `:152` นับหน้าจาก chunks ไม่ใช่จำนวนหน้าที่ wkhtmltopdf render จริง

**ผลกระทบ:** เอกสารพิมพ์อ้างอิงกลับ MR ได้ยากและตรวจจำนวนหน้าไม่ตรง ไทยใน MR PDF อ่านได้ในสภาพแวดล้อมนี้

## ข้อสังเกตที่ยังไม่จัดเป็น runtime bug เพิ่ม

- **Lint:** pylint 4.0.8 + pylint-odoo 10.0.11 ได้ exit 30, convention 1,060 / error 277 / refactor 79 / warning 486 / info 1 จำนวนมากเป็น inference ของ Odoo dynamic ORM เช่น `no-member` 214 และ `unsubscriptable-object` 34 จึงไม่นับเป็น runtime bugs ทั้งหมด
- **Undefined `_`:** `models/hr_timesheet.py:160` ใช้ `_()` แต่ไม่ได้ import; ยืนยันทาง static analysis ยังไม่ได้ยืนยันเส้นทางสร้าง timesheet ที่ name ว่างให้ถึง fallback นี้จริง
- **Credit-note sign หลังแก้ QA-01:** query ใช้ `price_subtotal` ของ `in_refund` โดยไม่กลับเครื่องหมาย ใน fixture refund subtotal เป็น +200 แต่ balance เป็น -200 ปัจจุบัน QA-01 ทำให้บรรทัดถูกกรองออกก่อน จึงยังไม่รายงานเป็นบั๊ก runtime ที่แยกจาก QA-01 ต้องเพิ่ม regression หลังแก้ selector
- **MR deletion policy:** ผู้ขอสามารถ unlink MR draft ได้จริง เพราะ ACL อนุญาต; `perm_unlink=False` ใน record rule ไม่ใช่ deny rule หากธุรกิจต้องการห้ามลบต้องแก้ ACL แต่ยังไม่ถือว่าผิดความต้องการจนกว่าจะกำหนดนโยบายลบให้ชัด
- **MR font dependency:** template อ้าง font จาก `/employee_purchase_requisition/static/fonts/Sarabun-Bold.ttf` แทนไฟล์ในโมดูลตัวเอง Repo ปัจจุบันมีไฟล์ดังกล่าว จึงไม่พบโหลด font ล้มเหลวในครั้งนี้
- ตรวจ Job Order/Notes/Subcontractor เฉพาะการเปิดหน้าจอและ source บางส่วน ไม่ได้ทดสอบวงจรงานทุกแบบ, scheduled reminders หรือการส่งข้อความภายนอก
- ยังไม่ทดสอบ multi-page BOQ XLSX จำนวนมาก, ขอบเขต rounding ทุก UoM/currency, browser/mobile อื่น, fiscal localization ไทยเต็มรูปแบบ, partial billing หลังแก้ QA-01 และ concurrent submissions

## การทำซ้ำและส่งต่องาน

รันจาก repo root โดยใช้ชื่อ Compose project แยกเสมอ:

```bash
docker compose -p kyld-job-costing-qa-20260912 -f docker-compose.test.yml up -d
docker compose -p kyld-job-costing-qa-20260912 -f docker-compose.test.yml logs odoo
```

รอ Odoo จบติดตั้งและ tests ก่อนเริ่มขั้นถัดไป; ตรวจทั้ง `odoo.tests.result` และ container exit code สคริปต์ diagnostic แสดงค่า actual/expected เพื่อยืนยันบั๊ก **exit 0 ของสคริปต์ไม่ได้หมายความว่าทุก scenario ผ่าน**

```bash
docker compose -p kyld-job-costing-qa-20260912 -f docker-compose.test.yml run --rm odoo \
  odoo --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/custom-addons \
  -d MOG_TEST -u job_costing_management --without-demo=all \
  --test-enable --test-tags=/job_costing_management --stop-after-init \
  --no-http --max-cron-threads=0 --workers=0

docker compose -p kyld-job-costing-qa-20260912 -f docker-compose.test.yml run --rm -T odoo \
  odoo shell --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/custom-addons \
  -d MOG_TEST --db_host=db --db_user=odoo --db_password=isolated-test --no-http \
  < job_costing_management/docs/qa/qa_20260912_reproduce.py
```

ส่วนทดสอบ PDF แบบโหลด assets ต้องมี Odoo HTTP ใน project เดียวกัน; รอบตรวจนี้ใช้ `kyld-job-costing-qa-web` บน localhost:18069 และ `web.base.url=http://127.0.0.1:8069` ใน DB ทดสอบ การรันเฉพาะ shell โดยไม่มี HTTP ไม่เพียงพอจะยืนยัน fonts/layout

ลำดับแก้ที่เสนอ: ปิดช่องอนุมัติและ RFQ ซ้ำ (QA-05/06), แก้ยอดต้นทุนและ dependency (QA-01–04), บังคับ company consistency (QA-11), แล้วแก้ stock/MR/UI/report ที่เหลือ เพิ่ม Odoo regression tests ที่สร้าง bill/receipt จริงและใช้ non-admin users ก่อน rerun ชุดเดิม

การตรวจรอบนี้จบด้วยการเก็บหลักฐานข้างต้นและปิด/ลบ Compose project QA ที่สร้างขึ้น ข้อมูลจำลองและผู้ใช้ทดสอบอยู่เฉพาะ DB ชั่วคราวนี้
