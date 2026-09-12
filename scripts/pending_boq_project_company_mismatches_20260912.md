# Pending: BOQ project/company mismatches blocking cost-line sync (2026-09-12)

Found while running `sync_all_unsynced_boqs.py` on KYLD_LIVE (PROD). 9 job cost
sheets failed `boq.boq._sync_job_cost_lines()` because `_check_work_context()`
rejected them. Root cause: BOQ was linked to the wrong (similarly-named)
project or company at creation time — same shape of mistake as the earlier
BOQ-line product+name mismatch bug, just one level up (project/company instead
of BOQ line).

**Not yet fixed** — needs a human to confirm the correct project/company
before writing anything, since either side (BOQ or cost sheet) could be the
one that's wrong. Once confirmed, re-run `sync_all_unsynced_boqs.py` (dry run
then apply) for these 9 sheets.

## Group A — Project mismatch (BOQ.project_id != cost_sheet.project_id)

| Sheet | BOQ | boq.project_id (current) | cost_sheet.project_id |
|---|---|---|---|
| 58 JCS/0058/2026 | BOQ00100 (id 100) | 290 Forest 2 / B6 | 319 Forest 1 /B6 |
| 54 JCS/0054/2026 | BOQ00095 (id 95), BOQ00094 (id 94) | 89 Forest 4 /KS2 | 314 Forest 3 / KS2 |
| 33 JCS/0033/2026 | BOQ00069 (id 69) | 215 Forest 1 /T4 | 216 Forest 1 /T5 |
| 32 JCS/0032/2026 | BOQ00067 (id 67) | 233 Forest 4 / สาธารณูปโภค | 236 Forest 3 / สาธารณูปโภค |
| 25 JCS/0025/2026 | BOQ00051 (id 51) | 163 Forest 4 /TS71 | 216 Forest 1 /T5 |
| 25 JCS/0025/2026 | BOQ00050 (id 50), BOQ00049 (id 49) | 235 "Forest 1/T5" (no space, duplicate project record) | 216 "Forest 1 /T5" |

Note: project id 235 and 216 both read as "Forest 1/T5" - likely a duplicate
project record that should be merged/deduped, not just relinked.

## Group B — Company mismatch (boq.company_id != project/cost_sheet company_id)

| Sheet | BOQ | boq.company_id (current) | should be |
|---|---|---|---|
| 26 JCS/0026/2026 | BOQ00053 (id 53), BOQ00052 (id 52) | 4 สมาร์ท เควาย แมนเนจเม้นท์ | 2 เขาใหญ่ ไลฟ์ ดีเวลลอปเม้นท์ |
| 24 JCS/0024/2026 | BOQ00048 (id 48), BOQ00047 (id 47), BOQ00046 (id 46) | 1 ไอดอล ซิสเท่ม | 4 สมาร์ท เควาย แมนเนจเม้นท์ |
| 23 JCS/0023/2026 | BOQ00045 (id 45), BOQ00044 (id 44), BOQ00043 (id 43) | 1 ไอดอล ซิสเท่ม | 4 สมาร์ท เควาย แมนเนจเม้นท์ |

Sheet 25 BOQ00051 also has a company mismatch on top of its project mismatch
(see Group A row for sheet 25 / BOQ00051).

## Not actually broken (same sheet, different BOQ)

BOQ 96 (sheet 54) and BOQ 61, 60 (sheet 26) matched fine and had already
`created`/committed some cost lines before the sibling BOQ in the same sheet
failed and rolled the whole sheet back (script commits per-sheet, not
per-BOQ). Once the mismatched BOQs above are fixed, re-running the sync
script will pick these up again too - no separate action needed for them.

## Next step

1. Confirm with whoever owns each project/BOQ which side is correct
   (BOQ's project/company link, or the cost sheet's).
2. Fix the wrong link (either `boq.boq.write({'project_id': ...})` /
   `company_id`, or fix the cost sheet - decide per row).
3. Re-run `scripts/sync_all_unsynced_boqs.py` (DRY_RUN=True first) to confirm
   these 9 sheets now sync clean, then apply.
