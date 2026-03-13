# script to check analytic distribution
picking = env['stock.picking'].search([('name', '=', 'FR01/IN/00004')], limit=1)
if not picking:
    print("Picking not found")
else:
    for move in picking.move_ids:
        print(f"--- Move: {move.id} ---")
        print("Move Product:", move.product_id.name)
        
        # Check if analytic_distribution is directly on move
        analytic_dist = getattr(move, 'analytic_distribution', 'Not Found')
        print("Analytic Dist on Move:", analytic_dist)
        
        # Check source documents
        po_line = getattr(move, 'purchase_line_id', None)
        if po_line:
            print("PO Line Analytic:", getattr(po_line, 'analytic_distribution', 'Not Found'))
        else:
            print("No PO Line")
            
        so_line = getattr(move, 'sale_line_id', None)
        if so_line:
            print("SO Line Analytic:", getattr(so_line, 'analytic_distribution', 'Not Found'))
            
        # Get analytic names from move if it has distribution
        if hasattr(move, 'analytic_distribution') and move.analytic_distribution:
            account_ids = [int(k) for k in move.analytic_distribution.keys() if k.isdigit()]
            print("Analytic Keys:", account_ids)
            accounts = env['account.analytic.account'].browse(account_ids)
            print("Analytic Names:", [a.name for a in accounts])
