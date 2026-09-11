# ภาพรวมต้นทุนสำหรับผู้บริหาร

เข้า **Job Costing → ภาพรวมต้นทุน** ด้วยสิทธิ์ Job Costing Manager หลังอัปเกรดโมดูลเป็น `17.0.1.0.4` และรีโหลดหน้าเว็บเพื่อรับ assets ใหม่

## ความหมายของตัวเลข

- งบ BOQ ใช้ `boq_total_cost` ปัจจุบันของ Cost Sheet ไม่ใช่ historical snapshot
- ต้นทุนจริงทั้งหมดใช้ `actual_total_cost` รวมเอกสารไม่มีงบด้วย ไม่ใช่ยอดจ่ายเงิน
- งบคงเหลือและเปอร์เซ็นต์ใช้งบคำนวณเฉพาะเอกสารที่งบ BOQ มากกว่าศูนย์ ต้นทุนของเอกสารไม่มีงบแสดงแยก
- กราฟแยกประเภทใช้ BOQ และต้นทุนจริงจากฟิลด์วัสดุ แรงงาน ค่าใช้จ่ายของเอกสารที่มีงบ
- งานเกินงบคือต้นทุนจริงมากกว่างบ งานใกล้เต็มคือใช้งบตั้งแต่ 90% ถึง 100% รายการติดตามเรียงเกินงบ → ใกล้เต็ม → ไม่มีงบ และแบ่งหน้าละ 20 รายการ
- แต่ละสกุลเงินแสดงแยกกัน เอกสารไม่ระบุสกุลเงินใช้สกุลเงินบริษัทพร้อมแจ้งจำนวนเอกสาร
- วันที่กรองวันเริ่ม Cost Sheet แต่ยอดเป็นยอดสะสมปัจจุบัน ค่าเริ่มต้นเลือกบริษัทปัจจุบันและสถานะอนุมัติแล้ว
- คลิกการ์ดหรือชื่อโครงการเพื่อเปิดรายการ Cost Sheet ตามตัวกรอง คลิกเลขเอกสารในรายการติดตามเพื่อเปิดฟอร์ม

## Implementation

OWL client action `job_costing_management.executive_dashboard` เรียกเมธอดอ่านอย่างเดียว `job.cost.sheet.get_executive_dashboard(filters=None, page=0)` ผ่าน ORM

Filters: `company_id`, `project_id`, `states` (approved/done/draft), `date_from`, `date_to`. Response: currency groups/KPIs/categories/projects, company/project choices, drill-down domain, paginated attention rows, and snapshot time in UTC.

Server ตรวจกลุ่มผู้ใช้ บริษัทที่เปิดใช้งาน และ record rules โดยไม่ใช้ sudo. Client ป้องกันผลตอบกลับคำขอเก่าทับตัวกรองใหม่ และรองรับ loading/error/retry/empty states.

ไม่เพิ่ม dependency ต่อ buz_dashboard และไม่เปลี่ยน API หรือสูตรต้นทุนเดิม. Snapshot อ่าน Cost Sheet ที่เข้าถึงได้ทั้งหมดในตัวกรองเพื่อคำนวณยอดรวม; เฉพาะรายการติดตามแบ่งหน้า จึงควรใช้ตัวกรองโครงการ/วันที่เมื่อข้อมูลมีจำนวนมาก.

## Validation

- Odoo 17 / PostgreSQL 16 บน Docker project แยก `kyld-executive-dashboard-test` ใช้ Postgres tmpfs
- ติดตั้งโมดูลบนฐานใหม่สำเร็จ และรันอัปเกรดพร้อม tests รอบสุดท้าย: **31 tests, 0 failures, 0 errors** (รวม dashboard tests ใหม่ 9 tests)
- ตรวจ Python AST, XML, JavaScript syntax และ `git diff --check`
- Headless Chrome: ตรวจ OWL rendering, KPI ต้นทุน 2,350 จากงบ 2,000 (ต้นทุนงานมีงบ 2,050 และไม่มีงบ 300), desktop/tablet, drill-down งานเกินงบ และตัวกรองไม่มีข้อมูล
- Browser ตรวจ error/retry, loading และเปลี่ยนตัวกรองระหว่างคำขอที่หน่วงเวลาเพื่อยืนยันว่าผลเก่าไม่ทับผลใหม่ ผ่านทั้งหมดโดยไม่มี JavaScript errors
- Automated Odoo tests ครอบคลุมต้นทุนแยกประเภท งบศูนย์ ยอดติดลบ เกณฑ์ 90%/100% หลายสกุลเงิน บริษัท สิทธิ์ record rules และการแบ่งหน้า

ไม่ deploy ไป DEV/PROD และไม่รันทดสอบบนฐานใช้งานจริง
