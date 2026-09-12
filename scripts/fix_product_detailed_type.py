# Fix product master data: 6 products whose default_code prefix (L=labour,
# M=material) disagrees with their detailed_type, which is what made
# boq.boq._sync_job_cost_lines() file them under the wrong cost_type bucket
# (see scripts/cost_type_mismatch_findings_20260912.md).
#
#   L0000130, L0000135, L0000131, L0000141, L0000143: currently detailed_type
#     'product' (storable) -> should be 'service' (labour convention).
#   M0001542: currently detailed_type 'service' -> should be 'product'
#     (storable material convention).
#
# This only fixes future syncs; it does NOT retroactively fix the 632
# existing job.cost.line rows with the wrong cost_type (separate script).
#
# Usage:
#   docker exec -i odoo odoo shell -d KYLD_LIVE --no-http < scripts/fix_product_detailed_type.py
#
# DRY_RUN = True: reports current state and any blockers (stock on hand,
# existing stock moves) without writing. No writes, no commit.

DRY_RUN = True

# Only M0001542 has zero stock quantity and zero stock move history, so only
# it is safe to flip right now. The 5 'L'-coded products (L0000130, 135, 131,
# 141, 143) have real stock qty/moves - flipping their detailed_type touches
# inventory valuation, not just job costing, and needs the inventory/
# accounting team's sign-off first (see dry-run output from 2026-09-12).
FIXES = {
    'M0001542': 'product',
}

ProductTemplate = env['product.template'].sudo()
StockMove = env['stock.move'].sudo()

for code, target_type in FIXES.items():
    templates = ProductTemplate.search([('default_code', '=', code)])
    if not templates:
        print(f"{code}: NOT FOUND")
        continue
    for tmpl in templates:
        print(f"\n{code} (template {tmpl.id}, {tmpl.name}): detailed_type={tmpl.detailed_type} -> target={target_type}")
        if tmpl.detailed_type == target_type:
            print("  already correct, skipping")
            continue
        qty = sum(tmpl.product_variant_ids.mapped('qty_available'))
        move_count = StockMove.search_count([('product_id', 'in', tmpl.product_variant_ids.ids)])
        print(f"  qty_available={qty}, stock_move_count={move_count}")
        if qty or move_count:
            print("  WARNING: has stock quantity or stock move history - changing "
                  "detailed_type away from storable may be blocked by Odoo or lose stock valuation context")
        if not DRY_RUN:
            try:
                tmpl.write({'detailed_type': target_type})
                print(f"  -> WRITTEN: detailed_type = {target_type}")
            except Exception as e:
                print(f"  !! FAILED: {e}")

if not DRY_RUN:
    env.cr.commit()
    print("\nCommitted.")
else:
    print("\nDry run only - set DRY_RUN = False and re-run to apply.")
