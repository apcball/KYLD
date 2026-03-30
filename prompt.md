# 📦 prompt.md – Remove VAT and Include in Price (Multi-Company Ready)

## 🎯 Objective

สร้าง Odoo module ที่สามารถ:

* ลบ VAT ออกจาก Bill Line
* นำ VAT ไปรวมในราคาสินค้า (price_unit)
* ทำงานผ่านปุ่มใน Vendor Bill (account.move)
* รองรับ Multi-Company อย่างถูกต้องตามมาตรฐาน Odoo

---

## 🧠 Functional Requirements

### 1. Button Action

เพิ่มปุ่มใน Vendor Bill:

* Label: `Include VAT in Price`
* เรียก method: `action_include_vat_into_price`

---

### 2. Core Behavior

เมื่อกดปุ่ม:

* Loop ทุก `invoice_line_ids`
* ถ้ามี tax_ids:

  * คำนวณ VAT จาก tax
  * เพิ่ม VAT เข้า price_unit
  * ลบ tax_ids ออก
* Recompute totals

---

### 3. Multi-Company Support (IMPORTANT)

#### 3.1 Company Isolation

* ทุก record ต้อง respect `company_id`
* ห้ามใช้ tax ข้าม company
* Validate:

```python
if line.tax_ids.filtered(lambda t: t.company_id != move.company_id):
    raise UserError("Tax company mismatch")
```

---

#### 3.2 Currency Handling

* ใช้ currency ของ document (`move.currency_id`)
* รองรับ multi-currency:

```python
currency = move.currency_id
company_currency = move.company_id.currency_id
```

* ถ้ามี conversion:

```python
amount = currency._convert(
    amount,
    company_currency,
    move.company_id,
    move.date or fields.Date.today()
)
```

---

#### 3.3 Tax Computation (ใช้ Odoo Engine เท่านั้น ❗)

ห้ามคำนวณเองตรงๆ ให้ใช้:

```python
taxes_res = line.tax_ids.compute_all(
    line.price_unit,
    currency=move.currency_id,
    quantity=1.0,
    product=line.product_id,
    partner=move.partner_id,
)
```

แล้วเอา:

```python
tax_amount = sum(t['amount'] for t in taxes_res.get('taxes', []))
```

---

### 4. Update Logic

```python
new_price = line.price_unit + tax_amount
```

update:

```python
line.write({
    'price_unit': new_price,
    'tax_ids': [(5, 0, 0)]
})
```

---

### 5. Recompute

หลังจาก update ทุก line:

```python
move._recompute_dynamic_lines(recompute_all_taxes=True)
```

---

### 6. Safety Control

#### 6.1 Prevent Double Apply

เพิ่ม field:

```python
is_vat_included = fields.Boolean(default=False)
```

logic:

```python
if move.is_vat_included:
    raise UserError("VAT already included")
```

---

#### 6.2 Only Vendor Bills

```python
if move.move_type not in ['in_invoice', 'in_refund']:
    raise UserError("Only vendor bills allowed")
```

---

#### 6.3 Draft Only

```python
if move.state != 'draft':
    raise UserError("Only draft bills allowed")
```

---

### 7. Tax Edge Cases

ต้อง handle:

* multiple taxes
* price_include = True → skip
* zero tax
* negative line (refund)

```python
valid_taxes = line.tax_ids.filtered(lambda t: not t.price_include and t.amount > 0)
```

---

### 8. Audit Log (Recommended)

เพิ่ม chatter:

```python
move.message_post(body="VAT has been included into price and removed from lines")
```

---

## 🎨 UI Requirements

เพิ่มปุ่มใน form view:

```xml
<button name="action_include_vat_into_price"
        type="object"
        string="Include VAT in Price"
        class="btn-primary"
        attrs="{'invisible': [('state', '!=', 'draft')]}"/>
```

---

## 🏗️ Technical Constraints

* ใช้ `_inherit = account.move`
* ห้าม override core tax logic
* ใช้ ORM เท่านั้น
* ห้าม SQL ตรง

---

## 🧪 Test Cases

### Case 1: Single Tax

* ราคา 100
* VAT 7%
* Expected:

  * price_unit = 107
  * tax_ids = empty

---

### Case 2: Multi Tax

* VAT 7% + WHT 3%
* Expected:

  * รวมเฉพาะ VAT (configurable optional)

---

### Case 3: Multi Company

* Company A ใช้ VAT 7%
* Company B ใช้ VAT 10%
* ต้องไม่ปะปนกัน

---

### Case 4: Currency

* USD bill
* Company currency = THB
* ต้องไม่ error

---

## 🔮 Optional Enhancements

* Checkbox: Auto include VAT
* Apply on Confirm
* Apply เฉพาะ product type
* Config setting per company

---

## 🚫 Anti-Patterns (ห้ามทำ)

* ❌ hardcode VAT 7%
* ❌ ใช้ tax.amount ตรงๆ
* ❌ ignore currency
* ❌ ignore company_id

---

## ✅ Definition of Done

* ปุ่มใช้งานได้จริง
* รองรับ multi-company
* ไม่มี error ใน multi-currency
* Recompute ถูกต้อง
* ไม่สามารถกดซ้ำได้
* ผ่าน test cases ทั้งหมด

---
