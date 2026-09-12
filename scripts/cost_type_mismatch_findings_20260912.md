# Company-wide cost_type vs product-code mismatch (2026-09-12)

Found while investigating a user report that labour products were showing
under "Material Cost" on JCS/0034/2026. Checked the whole DB with
`scripts/check_all_cost_type_mismatch.py` (read-only) - it's not a one-sheet
issue.

## Scale

- 621 `job.cost.line` rows: `cost_type='material'` but product code starts
  with `L` (the labour-product convention).
- 11 rows: `cost_type='labour'` but product code starts with `M` (the
  material-product convention).
- 632 total, spread across 55+ job cost sheets (JCS/0001/2025 through
  JCS/0064/2026 - essentially the whole active portfolio).
- Oldest offending row: create_date 2025-12-04. Not something introduced by
  today's deploy or BOQ-sync work - long-standing.
- 82 of the 632 have create_date 2026-09-12 (today) - likely came from
  today's `sync_all_unsynced_boqs.py` run picking up already-mislabeled BOQ
  lines rather than a bug in that script; needs a quick look to confirm.
- 106 rows have non-zero `actual_cost` - these actually skew reported
  Material vs Labour totals on the job cost sheet dashboard right now (both
  the "BOQ Costs" baseline and "Actual Costs" summary split by `cost_type`).

## Recurring products (same wrong product reused across many sheets)

`L0000130` (ค่าแรง ปลูกหญ้า), `L0000135` (ค่าแรง ติดตั้งโครงเหล็กพร้อมทาสี),
`L0000126` (ค่าแรง มุงกระเบื้องหลังคา), `L0000006` (ค่าแรงติดตั้งงานผนัง),
`L0000026` (ค่าแรง ประตู-หน้าต่าง กระจก/อลูมิเนียม), `L0000141`
(ค่าแรงติดตั้งประตูรั้วเหล็กหน้าบ้าน), `L0000025`, `L0000014`, `L0000002`-`006`
each show up wrong on 5-10+ different sheets - suggests these were
mis-classified once (in a BOQ template or product master data setup) and the
mistake got copied every time that BOQ template/line was reused, rather than
632 independent one-off entry errors.

## Root cause hypothesis (not yet confirmed)

`boq.boq._sync_job_cost_lines()` sets `cost_type = 'labour' if
line.product_id.detailed_type == 'service' else 'material'` - so a line only
lands in the wrong bucket if either:
  (a) the product's own `detailed_type` is wrong (found 3 cases where an
      'L'-coded product has `detailed_type='product'` instead of `'service'`
      - product master data error), or
  (b) the cost line was created some other way (manual entry, import, an
      older code path) that didn't go through `_sync_job_cost_lines`.

Given 632 rows and the same handful of products recurring, (b) - or a
product master data issue predating the current classification logic - looks
more likely than 632 independent typos. Not confirmed; needs someone who
knows the product catalog history to weigh in.

## Not yet fixed

This is a data correction across the whole cost DB - reclassifying
`cost_type` on 632 rows changes what bucket (and dashboard subtotal) each
cost falls into for reporting. Mechanically it's a simple field flip
(`cost_type: 'material' -> 'labour'` or vice versa) with no cascading writes,
but the blast radius (55+ sheets, 106 with real actual_cost) means it should
go through the same dry-run-then-confirm flow as the earlier BOQ/PO fixes,
not get applied silently.

## Next step

1. Confirm whether (a) or (b) above is the real cause, and whether the fix
   should be "flip cost_type on the 632 existing lines" only, or also
   "fix the product master data (`detailed_type`) so future BOQ syncs don't
   recreate the same mistake."
2. Write a dry-run script (`cost_type` flip only, no other field touched)
   listing all 632 rows for review, get explicit apply confirmation, then
   run per-sheet (like `sync_all_unsynced_boqs.py`) so a failure doesn't
   roll back unrelated sheets.
3. Re-check the 82 lines created today (2026-09-12) specifically to confirm
   they came from pre-existing BOQ line data rather than a bug in
   `sync_all_unsynced_boqs.py` / `sync_missing_boq_cost_lines.py`.
