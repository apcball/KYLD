# Read-only audit of JCS/0028/2026: explain where Total Labour Cost
# (562,322.92) and Actual Labour Cost (1,347,140.14) come from, since
# Actual > Total (Planned) by a wide margin is worth checking - is it a
# genuine cost overrun, or a data/matching problem (analytic account
# mismatch, mis-synced BOQ, wrong cost_type, etc)?
#
# Total Labour Cost = sum(labour_cost_ids.total_cost) = planned_qty * unit_cost
#   per job.cost.line (job_cost_sheet.py _compute_totals).
# Actual Labour Cost = _get_analytic_actual_cost_totals() - a raw SQL query
#   summing PO lines (net of billed), posted bills, and timesheets whose
#   analytic_distribution (or job_cost_line fallback) matches this sheet's
#   analytic_account_id (job_cost_sheet.py, around line 223-353).
#
# Usage (no writes):
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/audit_jcs0028_labour_cost.py

JobCostSheet = env['job.cost.sheet'].sudo()

sheet = JobCostSheet.search([('name', '=', 'JCS/0028/2026')], limit=1)
account_id = sheet.analytic_account_id.id
print(f"Sheet {sheet.id} '{sheet.name}', project={sheet.project_id.display_name} (id {sheet.project_id.id}), "
      f"analytic_account_id={account_id} ({sheet.analytic_account_id.display_name if sheet.analytic_account_id else None})")
print(f"project.analytic_account_id = {sheet.project_id.analytic_account_id.id if sheet.project_id.analytic_account_id else None}")

print(f"\nStored: total_labour_cost={sheet.total_labour_cost}, actual_labour_cost={sheet.actual_labour_cost}, "
      f"active_total_cost includes labour too (planned, MR-adjusted)")
print(f"labour_cost_ids count = {len(sheet.labour_cost_ids)}")

print("\n=== 1. Is analytic_account_id shared with another sheet? (would explain inflated actuals) ===")
other_sheets = JobCostSheet.search([('analytic_account_id', '=', account_id)])
print(f"  sheets using this account: {[(s.id, s.name) for s in other_sheets]}")

print("\n=== 2. Manual recompute vs stored ===")
totals = sheet._get_analytic_actual_cost_totals([account_id])
print(f"  fresh _get_analytic_actual_cost_totals = {totals.get(account_id)}")

print("\n=== 3. sum(labour_cost_ids.total_cost) vs sum(labour_cost_ids.actual_cost) (line-level, different metric) ===")
print(f"  sum(labour_cost_ids.total_cost) = {sum(sheet.labour_cost_ids.mapped('total_cost'))}")
print(f"  sum(labour_cost_ids.actual_cost) = {sum(sheet.labour_cost_ids.mapped('actual_cost'))}")

print("\n=== 4. PO lines directly distributed to this account, classified as labour (service product) ===")
env.cr.execute("""
    SELECT pol.id, po.name, po.state, pt.default_code, pt.detailed_type, pol.price_subtotal,
           pol.qty_received, pol.product_qty, res_partner.name AS vendor
    FROM purchase_order_line pol
    JOIN purchase_order po ON po.id = pol.order_id
    LEFT JOIN res_partner ON res_partner.id = po.partner_id
    LEFT JOIN product_product pp ON pp.id = pol.product_id
    LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN jsonb_each_text(COALESCE(pol.analytic_distribution, '{}'::jsonb)) AS kv(key, value) ON TRUE
    WHERE kv.key ~ ('(^|,)' || %(aid)s || '(,|$)')
      AND po.state IN ('purchase', 'done')
      AND pol.display_type IS NULL
      AND pt.detailed_type = 'service'
""", {'aid': account_id})
rows = env.cr.fetchall()
po_sum = sum(r[5] for r in rows)
print(f"  {len(rows)} PO line(s), sum price_subtotal = {po_sum}")
for r in sorted(rows, key=lambda r: -r[5])[:15]:
    print(f"  POL {r[0]} PO={r[1]} state={r[2]} code={r[3]} price_subtotal={r[5]} vendor={r[8]}")

print("\n=== 5. Posted bill lines distributed to this account, classified as labour ===")
env.cr.execute("""
    SELECT aml.id, am.name, am.move_type, aml.balance, pt.default_code, res_partner.name
    FROM account_move_line aml
    JOIN account_move am ON am.id = aml.move_id
    LEFT JOIN res_partner ON res_partner.id = am.partner_id
    LEFT JOIN product_product pp ON pp.id = aml.product_id
    LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
    JOIN jsonb_each_text(COALESCE(aml.analytic_distribution, '{}'::jsonb)) AS kv(key, value) ON TRUE
    WHERE kv.key ~ ('(^|,)' || %(aid)s || '(,|$)')
      AND am.state = 'posted' AND am.move_type IN ('in_invoice', 'in_refund')
      AND aml.display_type = 'product'
      AND pt.detailed_type = 'service'
""", {'aid': account_id})
rows2 = env.cr.fetchall()
bill_sum = sum(r[3] for r in rows2)
print(f"  {len(rows2)} bill line(s), sum balance = {bill_sum}")
for r in sorted(rows2, key=lambda r: -r[3])[:15]:
    print(f"  AML {r[0]} bill={r[1]} type={r[2]} balance={r[3]} code={r[4]} vendor={r[5]}")

print("\n=== 6. Timesheets (account.analytic.line, employee_id set) on this account ===")
env.cr.execute("""
    SELECT COUNT(*), SUM(ABS(amount))
    FROM account_analytic_line
    WHERE account_id = %(aid)s AND employee_id IS NOT NULL
""", {'aid': account_id})
ts_count, ts_sum = env.cr.fetchone()
print(f"  {ts_count} timesheet line(s), sum amount = {ts_sum}")

print(f"\n=== 7. Sanity total: PO({po_sum}) + Bill({bill_sum}) + Timesheet({ts_sum or 0}) = {po_sum + bill_sum + (ts_sum or 0)} ===")
print(f"    vs stored actual_labour_cost = {sheet.actual_labour_cost}")
print("    (won't match exactly - this only covers the direct-distribution branch, not the job_cost_line fallback branch)")
