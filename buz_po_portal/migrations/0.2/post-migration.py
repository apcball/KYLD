from odoo import api, SUPERUSER_ID
from odoo.tools.image import image_process
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Fields to check and resize
    fields_to_fix = ['prepared_signature', 'reviewed_signature', 'approval_signature']
    
    # Fetch all POs that have at least one signature
    # Use generic search to accept all, then filter in loop to avoid complex domain issues if fields are missing
    try:
        domain = ['|', '|', 
                  ('prepared_signature', '!=', False), 
                  ('reviewed_signature', '!=', False),
                  ('approval_signature', '!=', False)]
        orders = env['purchase.order'].search(domain)
    except Exception as e:
        _logger.error(f"Migration 0.2: Failed to search orders: {str(e)}")
        return

    _logger.info(f"Migration 0.2: Found {len(orders)} Purchase Orders to check for image resizing.")
    
    count = 0
    for order in orders:
        vals = {}
        processed = False
        
        for field in fields_to_fix:
            try:
                # Read field value safely
                img_data = order[field]
                if not img_data:
                    continue

                # Resize to max 1024x1024 to save memory/space
                new_image = image_process(img_data, size=(1024, 1024))
                
                # Verify we actually got something back
                if new_image and new_image != img_data:
                     vals[field] = new_image
                     processed = True
                     
            except Exception as e:
                # Log but continue - don't crash the migration for one bad image
                _logger.warning(f"Migration 0.2: Failed to process {field} for PO {order.name}. Error: {str(e)}")
                continue

        if processed:
            try:
                order.write(vals)
                count += 1
                if count % 10 == 0:
                     _logger.info(f"Migration 0.2: Processed {count} orders...")
                     env.cr.commit() 
            except Exception as e:
                _logger.error(f"Migration 0.2: Failed to write to PO {order.name}. Error: {str(e)}")

    _logger.info(f"Migration 0.2: Completed. Resized images for {count} Purchase Orders.")
