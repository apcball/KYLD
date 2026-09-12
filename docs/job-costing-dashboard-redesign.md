# Job Costing dashboard — September 12, 2026

ปรับ dashboard ตาม mockup ล่าสุด: KPI 6 ช่อง, กราฟ BOQ / Active / Actual,
สัดส่วนต้นทุน, Cost Variance, สรุปโครงการ, Top 5 รายการ BOQ และงานที่ต้องติดตาม
พร้อมแบนเนอร์บ้านและ layout ที่ปรับตามขนาดหน้าจอ

## ข้อมูลที่ใช้จริง

| ส่วนแสดงผล | แหล่งข้อมูล / การคำนวณ |
| --- | --- |
| BOQ Budget | ผลรวม `job.cost.sheet.boq_total_cost` เฉพาะเอกสารที่มีงบมากกว่าศูนย์ |
| Active Planned | `job.cost.sheet.active_total_cost` ซึ่งตัดแผนจากรายการยกเลิก/ปฏิเสธตามสูตรเดิม |
| Actual | `job.cost.sheet.actual_total_cost` รวมงานไม่มีงบ |
| Remaining / Used | งบลบ Actual / Actual หารงบ เฉพาะเอกสารที่มีงบ เพื่อคงนิยามเดิม |
| ประเภทต้นทุน | Material, Labour, Overhead จาก Cost Sheet; Active แยกประเภทจาก `job.cost.line.active_total_cost` |
| Cost Variance | Actual − BOQ; รวม Actual ของงานไม่มีงบ |
| Top 5 BOQ items | `job.cost.line` ที่มี BOQ มากกว่าศูนย์ เรียงตามขนาดส่วนต่าง `actual_cost - boq_total_cost` จากมากไปน้อย |
| Trend | ยอดปัจจุบันสะสมตามเดือนของ `date_start`; ไม่ใช่ประวัติการบันทึกต้นทุนรายเดือน |
| งานติดตาม | เกินงบ, ใช้งบตั้งแต่ 90%, หรือไม่มีงบ ตามเกณฑ์และ pagination เดิม |

ต้นทุนที่รวมจาก analytic account ระดับ Cost Sheet อาจไม่มีรายการ BOQ รองรับ
จึงไม่กระจายยอดนั้นลง Top 5 โดยสมมติสัดส่วน รายการที่ Actual ยังเป็นศูนย์อาจเป็นงานที่ยังไม่เกิดต้นทุน
ส่วนต่างติดลบจึงไม่ใช่การยืนยันว่าประหยัดงบเมื่อจบงาน

ทุกส่วนใช้ตัวกรองบริษัท โครงการ สถานะ Cost Sheet และวันเริ่มเอกสาร
แยกยอดตามสกุลเงิน ใช้สิทธิ์ผู้เรียกและ record rules ไม่มี `sudo()`
การกดการ์ด ชื่อโครงการ ชื่อรายการ และปุ่มดูทั้งหมดเปิดข้อมูลต้นทาง
ไม่มีตัวเลขตัวอย่างหรือเปอร์เซ็นต์เปรียบเทียบช่วงก่อนหน้าฝังใน dashboard จริง

## การตรวจสอบ

- Python AST, JavaScript syntax, XML parsing และ SCSS compilation ผ่าน
- Odoo 17 / PostgreSQL 16 บนฐานข้อมูลแยก `MOG_TEST`:
  **67 tests, 0 failed, 0 errors** รวม dashboard 12 tests
- ทดสอบ OWL template จริงกับข้อมูล fixture สำหรับ UI:
  KPI 6 ช่อง, SVG 3 กราฟ, แท่งเปรียบเทียบ 9 แท่ง, เปิด Cost Sheet/Cost Item,
  ตัวกรอง, retry, empty state, ต้นทุนติดลบ และไม่มีวันที่สำหรับ trend
- ตรวจความกว้าง 1400, 1024, 768 และ 390 pixels: ไม่มีหน้า dashboard ล้นแนวนอน
  ตารางกว้างเลื่อนได้ภายใน panel
- `git diff --check` ผ่าน

ภาพตรวจ UI ใช้ข้อมูล fixture ไม่ใช่ข้อมูลบริษัท:
`/private/tmp/kyld-dashboard-qa.W3m0zx/desktop.png` และ
`/private/tmp/kyld-dashboard-qa.W3m0zx/mobile.png`
สคริปต์ตรวจ: `/private/tmp/kyld-dashboard-qa.W3m0zx/verify.cjs`

ยังไม่ได้ deploy ไป DEV หรือ PROD การใช้งานบนเซิร์ฟเวอร์ต้องส่งทั้ง Python และ frontend assets
แล้ว restart/update โมดูลตามขั้นตอนของโครงการ

## ภาพแบนเนอร์

สร้างด้วย built-in image generation tool ตาม skill `imagegen` และบันทึกไว้ใน repository:
`job_costing_management/static/src/dashboard/construction-hero.png`
ไม่มีการโหลดรูปจากบริการภายนอกขณะเปิด dashboard

Prompt:

> Use case: photorealistic-natural. Create a wide panoramic background image for a construction cost executive dashboard, 1536x512 landscape. Modern two-storey tropical concrete and glass luxury house under construction, right half transitioning into delicate blue architectural wireframe and scaffolding. Soft pale blue sky, trees, warm muted stone and concrete, elegant realistic architectural photography. House located in right 65% of canvas, left 35% almost empty pale mist for overlaid navy UI title. Composition suitable for cropping to a very short banner. No text, no logo, no UI, no watermark.

ใช้ skill `context-mode` สรุปผลตรวจและ log ของฐานข้อมูลทดสอบ
