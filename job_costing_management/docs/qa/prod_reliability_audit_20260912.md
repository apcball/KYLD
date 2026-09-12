# PROD data-reliability audit — job cost sheet + executive dashboard

Date: 2026-09-12 · DB: `KYLD_LIVE` · Script: `scripts/audit_prod_data_reliability_20260912.py` (read-only, no PROD writes; full transaction rolled back)

## Update 2026-09-12 (same day) — items 1 & 7 actioned

- **Check 1 (stale totals)**: ran `scripts/recompute_stale_actual_costs_20260912.py` with `DRY_RUN=False` against `KYLD_LIVE`. Committed — the 8 sheets listed below (4, 5, 6, 7, 25, 43, 50, 57) had `actual_total_cost`/`total_variance` refreshed to match live PO/bill/timesheet data. A re-run of the full audit afterward showed 5 sheets stale again — that's new drift accumulated between the fix and the verification run (the actual-cost query reads live transactional data), not a sign the fix failed.
- **Check 7 (unscoped PO fallback)**: code fix applied in `job_costing_management/models/purchase_order.py` (~L338-349) — the sheet-level auto-link fallback now requires a candidate cost line's `boq_line_id` to be blank or match the incoming PO line's own BOQ line, mirroring the `ae5e783` fix. Deployed to DEV then PROD (module update + container restart on both, per this repo's Python-reload requirement). This only prevents *new* bad links; the 154 already-ambiguous product+name groups found in Check 7 are unchanged by this fix and still need a separate data-repair pass.
- Items 3, 4, 5, 6 (PO/BOQ relink script, shared-analytic-account groups, duplicate sheets, BOQ project mismatch) were **not** actioned — still open, pending separate approval/human decision as noted below.

### Item 3 investigated (2026-09-12) — held for human review, not fixed

Dry-ran `fix_po_boq_line_mismatch.py` on PROD: 0 auto-fixable, all 4 skipped ("no job.cost.line exists yet for the expected BOQ line" — because that search is scoped to the PO line's *current* cost sheet). Inspected each case directly and found this is **worse than a same-sheet BOQ-line collision** — all 4 are cross-sheet: the PO's actual cost is currently recorded on a different job cost sheet than the one its own material-requisition/BOQ line belongs to.

| PO line | Product on the PO | Currently booked on (wrong) | Cost line already exists on (correct sheet) |
|---|---|---|---|
| 16567 (APO2602543) | M0000190 กระเบื้อง 12x24 | JCS/0034/2026, cost_line 1581 | JCS/0038/2026, cost_line 6536 (boq_line 7928) |
| 16530 (APO2602540) | M0000538 ตะแกรงดักกลิ่น | JCS/0034/2026, cost_line 1644 | JCS/0038/2026, cost_line 6600 (boq_line 7991) |
| 13625 (APO2602120) | X0000007 ค่าขนส่งรถเฮี๊ยบ | JCS/0034/2026, cost_line 1569 | JCS/0020/2026, cost_line 6898 (boq_line 10387) |
| 11432 (APO2601759) | M0001792 ลูกกลิ้งทาสี | JCS/0013/2025, cost_line 996 — **that cost_line's own product is M0000681 (วัสดุสิ้นเปลืองงานโครงสร้าง), a completely different product from the PO**, and 10 other PO lines also point to it | JCS/0048/2026, cost_line 7367 (boq_line 9994) |

Case 11432 looks like cost_line 996 is being used as a catch-all "misc materials" bucket across 11 unrelated PO lines and possibly multiple projects, not a simple mismatch — needs accounting/PM judgment on intent before any relink, since moving it would shift real Actual Cost between two different projects' job cost sheets. **Decision (2026-09-12): hold all 4, no write made, pending human review of financial impact before any fix.**

## Bottom line

**63 job cost sheets on PROD. Only 9 have zero known open issues. 54 carry at least one.**
The executive dashboard does not compute independently — it `search_read`s the same stored fields as the sheet (`executive_dashboard.py`), so every sheet-level issue below shows up on the dashboard too. Numbers can be trusted case-by-case, not as a blanket yes.

| Check | Result | Status |
|---|---|---|
| 1. Stale stored totals (post cancel-BOQ fix `940e2ff`/`fb2ff64`) | 8 of 63 sheets stale | ⚠️ recompute script never fully applied |
| 2. cost_type vs product-code mismatch (`d09206c`) | 0 mismatches | ✅ fix holds, no regressions |
| 3. PO line linked to wrong BOQ line's cost line (`ae5e783`/`f1cdc0a`) | 4 PO lines still mismatched | ⚠️ relink script never run |
| 4. Sheets sharing one analytic account (actual cost combined) | 9 accounts / 20 sheets affected | ⚠️ known limitation, mitigated by UI banner only |
| 5. Duplicate job cost sheet per project | 8 projects, 16 sheets | ⚠️ 1 pair empty (safe cleanup drafted), 7 pairs need human call |
| 6. BOQ/cost-sheet project or company mismatch | 9 sheets | ⚠️ unchanged from prior finding, still open |
| 7. Sheet-level PO fallback collision risk (product+name, no `boq_line_id` scope) | 154 real dual-BOQ collisions (of 1424 groups; rest are single real link + one blank) | ⚠️ new finding, not yet fixed in code |
| 8. Dashboard vs sheet stored-field consistency | 0 mismatches | ✅ dashboard is a faithful mirror of sheet fields |

## Detail

### 1. Stale stored totals — 8 sheets
`_compute_boq_totals`/`_compute_active_totals`/`_compute_totals`/`_compute_actual_costs`/`_compute_variance` produced different values when force-recomputed vs. what's currently stored. `recompute_boq_totals_after_cancel_fix.py` (commit `fb2ff64`) was written for exactly this but its run against PROD was never confirmed — this audit confirms it was **not fully run**, or new drift has appeared since.

| Sheet | Stored `actual_total_cost` | Fresh `actual_total_cost` | Delta |
|---|---:|---:|---:|
| JCS/0004/2025 (id 4) | 6,267,453.34 | 6,503,053.34 | +235,600.00 |
| JCS/0005/2025 (id 5) | 6,313,953.34 | 6,503,053.34 | +189,100.00 |
| JCS/0006/2025 (id 6) | 6,362,653.34 | 6,503,053.34 | +140,400.00 |
| JCS/0007/2025 (id 7) | 6,442,353.34 | 6,503,053.34 | +60,700.00 |
| JCS/0025/2026 (id 25) | 4,078,110.59 | 4,100,742.59 | +22,632.00 |
| JCS/0050/2026 (id 50) | 1,087,414.73 | 979,280.33 | −108,134.40 |
| JCS/0057/2026 (id 57) | 0.00 | 1,002.40 | +1,002.40 |
| JCS/0043/2026 (id 43) | 0.00 | 17,899.67 | +17,899.67 |

**Action**: rerun `scripts/recompute_boq_totals_after_cancel_fix.py` with `DRY_RUN = False` against PROD (after reviewing the deltas above) to bring stored fields current — pending user approval, not done in this audit.

### 2. cost_type mismatch — clean
0 lines found with `cost_type` disagreeing with the M/L product-code convention. The 632-row fix (`d09206c`) holds; no regressions from `sync_all_unsynced_boqs.py` or other paths since.

### 3. PO → wrong BOQ line's cost line — 4 still wrong
`fix_po_boq_line_mismatch.py` (companion to `ae5e783`) was never confirmed run. This audit found 4 live mismatches:

| PO line | PO | Currently on cost_line (boq_line) | Should be boq_line |
|---|---|---|---|
| 11432 | APO2601759 | cost_line 996 (boq_line 6561) | 9994 |
| 16567 | APO2602543 | cost_line 1581 (boq_line 6988) | 7928 |
| 16530 | APO2602540 | cost_line 1644 (boq_line 7051) | 7991 |
| 13625 | APO2602120 | cost_line 1569 (boq_line 6976) | 10387 |

**Action**: rerun `scripts/fix_po_boq_line_mismatch.py` (still `DRY_RUN = True`) to confirm these 4 and apply the relink — pending user approval.

### 4. Sheets sharing an analytic account — 9 accounts, 20 sheets
Every pair/group below shows identical or combined Actual Cost across all listed sheets (`_get_analytic_actual_cost_totals` groups by account, not by sheet):

- account 97: JCS/0062/2026, JCS/0017/2026
- account 494: JCS/0060/2026, JCS/0057/2026
- account 477: JCS/0059/2026, JCS/0050/2026
- account 446: JCS/0052/2026, JCS/0047/2026
- account 186: JCS/0044/2026, JCS/0043/2026
- account 249: JCS/0033/2026, JCS/0025/2026
- account 184: JCS/0029/2026, JCS/0023/2026
- account 185: JCS/0028/2026, JCS/0024/2026 *(the JCS/0024 vs JCS/0028 pair from `afe59b5`/`compare_jcs0024_jcs0028_duplicate.py`)*
- account 255: JCS/0008/2025, JCS/0007/2025, JCS/0006/2025, JCS/0005/2025, JCS/0004/2025 *(5-way — largest cluster, also all 4 of the 2025 sheets flagged stale in Check 1)*

This is the same limitation `afe59b5` added a warning banner for. The banner is UI-only; the underlying Actual Cost numbers for every sheet in each group above are not individually trustworthy.

### 5. Duplicate job cost sheets — 8 projects
| Project | Sheets | Verdict |
|---|---|---|
| 96 Forest 4/M1 | JCS/0062 (4 lines) vs JCS/0017 (648 lines) | needs human call |
| 290 Forest 2/B6 | JCS/0060 (2 lines) vs **JCS/0057 (0 lines, EMPTY)** | JCS/0057 safe to remove |
| 273 Forest 2/D3 | JCS/0059 (209 lines) vs JCS/0050 (10 lines) | needs human call |
| 245 Forest 3/VP32 | JCS/0052 (392 lines) vs JCS/0047 (3 lines) | needs human call |
| 172 Forest 2/B9 | JCS/0044 (8 lines) vs **JCS/0043 (0 lines, EMPTY)** | JCS/0043 safe to remove |
| 216 Forest 1/T5 | JCS/0033 (13 lines) vs JCS/0025 (183 lines) | needs human call |
| 170 Forest 2/B7 | JCS/0029 (45 lines) vs JCS/0023 (24 lines) | needs human call |
| 171 Forest 2/B10 | JCS/0028 (43 lines) vs JCS/0024 (25 lines) | needs human call |

Only 2 of 8 pairs (project 290, 172) are cleanly empty-vs-real; `cleanup_duplicate_empty_job_cost_sheets.py` already targets exactly these two (ids 43, 57) and is still `DRY_RUN = True`. The other 6 pairs both carry real data and additionally overlap with Check 4's shared-analytic-account list — meaning their Actual Cost figures are already combined/ambiguous, compounding the duplicate-sheet problem.

### 6. BOQ/cost-sheet project or company mismatch — 9 sheets, unchanged
Same count as `pending_boq_project_company_mismatches_20260912.md` — still open, blocks `boq.boq._sync_job_cost_lines()` for these sheets. No regression, no fix yet either.

### 7. New finding — sheet-level PO fallback has no `boq_line_id` scoping
`purchase_order.py` (~L343-345) has a second auto-link fallback (separate from the one fixed in `ae5e783`) that matches an incoming PO line to an existing `job.cost.line` by `product_id + name` only, with **no `boq_line_id` filter at all** — same defect class as the bug that caused the confirmed sheet-10 incident, at a different code path that was never audited or fixed.

154 product+name groups across the DB currently have 2+ **distinct, non-blank** `boq_line_id` values sharing the same product+description text within one sheet — meaning a future PO line matching that product+name has no way to land on the correct one; it will pick whichever `job.cost.line` the `.filtered()` call happens to return first. This is a live, unfixed data-integrity risk, not just historical.

**Action**: this needs a code fix mirroring `ae5e783`'s scoping (out of scope for this read-only audit) plus a follow-up detection pass once fixed, to see if any of these 154 groups already show incorrect actual-cost attribution.

### 8. Dashboard consistency — clean
0 discrepancies between `executive_dashboard.py`'s `search_read` values and a fresh `browse()` of the same sheets. Confirms the dashboard has no separate bug of its own — every number it shows is exactly what's stored on the sheet, good or bad.

## What this means for "can we trust the data?"

- **Trust as-is**: 9 of 63 sheets (no open issue in any of the 8 checks).
- **Trust with a known, bounded discount**: sheets only affected by Check 6 (BOQ/project mismatch, doesn't touch cost numbers directly) or minor stale-total drift.
- **Do not trust Actual Cost in isolation**: the 20 sheets in the 9 shared-analytic-account groups (Check 4) — their Actual Cost is combined with a sibling sheet's.
- **Needs a data decision before trusting either sheet**: the 6 non-empty duplicate-sheet pairs (Check 5).
- **Needs a code fix, not just data cleanup**: Check 7 (unscoped fallback) is an open wound that will keep generating new bad links until patched.

No PROD data was changed by this audit. Recommended next steps (each needs separate approval before running):
1. Rerun `recompute_boq_totals_after_cancel_fix.py` with `DRY_RUN = False`.
2. Rerun `fix_po_boq_line_mismatch.py` with `DRY_RUN = False` for the 4 confirmed mismatches.
3. Rerun `cleanup_duplicate_empty_job_cost_sheets.py` with `DRY_RUN = False` for sheets 43 and 57.
4. Human decision needed on the 6 non-empty duplicate pairs and the 9 shared-analytic-account groups — these are data-modeling decisions, not scripts.
5. Code fix for the sheet-level PO fallback (Check 7), plus a data-repair pass afterward.
