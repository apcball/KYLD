from odoo import api, SUPERUSER_ID
from odoo.tools.image import image_process
import logging
import base64
import re

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Fields to check and resize
    fields_to_fix = ['prepared_signature', 'reviewed_signature', 'approval_signature']
    
    # Fetch all POs that have at least one signature
    # Use generic search 
    try:
        domain = ['|', '|', 
                  ('prepared_signature', '!=', False), 
                  ('reviewed_signature', '!=', False),
                  ('approval_signature', '!=', False)]
        orders = env['purchase.order'].search(domain)
    except Exception as e:
        _logger.error(f"Migration 0.3: Failed to search orders: {str(e)}")
        return

    _logger.info(f"Migration 0.3: Found {len(orders)} Purchase Orders to check for image resizing.")
    
    count = 0
    cleared_count = 0
    recovered_count = 0
    
    for order in orders:
        vals = {}
        processed = False
        
        for field in fields_to_fix:
            try:
                # Read field value safely
                img_data = order[field]
                if not img_data:
                    continue

                # Attempt 1: Standard Resize
                try:
                    new_image = image_process(img_data, size=(1024, 1024))
                except Exception:
                    # Attempt 2: Handle data URI scheme (b'data:image/png;base64,...')
                    # This often happens if the widget saved raw data URI
                    try:
                        # Check if bytes start with data:image
                        if img_data[:10].startswith(b'data:image'):
                            # Find comma
                            if b',' in img_data:
                                header, body = img_data.split(b',', 1)
                                # Decode the body (which is base64) to get raw image bytes
                                # But wait, image_process EXPECTS base64 string/bytes usually?
                                # No, image_process(base64_source) -> returns base64
                                # BUT if it finds a header, it crashes.
                                # So we pass the body (which is base64 encoded image) to image_process
                                new_image = image_process(body, size=(1024, 1024))
                                recovered_count += 1
                            else:
                                raise ValueError("Invalid data URI")
                        else:
                             raise Exception("Not a data URI")
                    
                    except Exception as e2:
                        # Attempt 3: If still failing, it's corrupt. CLEAR IT.
                        _logger.warning(f"Migration 0.3: PO {order.name} field {field} is corrupt/unreadable. Clearing it to fix crash. Error: {e2}")
                        vals[field] = False
                        cleared_count += 1
                        processed = True
                        continue

                # If successful (Attempt 1 or 2)
                # Verify we actually got something back
                if new_image and new_image != img_data:
                     vals[field] = new_image
                     processed = True
                     
            except Exception as e:
                _logger.warning(f"Migration 0.3: Unexpected error processing {field} for PO {order.name}. Error: {str(e)}")
                continue

        if processed:
            try:
                order.write(vals)
                count += 1
                if count % 10 == 0:
                     _logger.info(f"Migration 0.3: Processed {count} orders...")
                     env.cr.commit() 
            except Exception as e:
                _logger.error(f"Migration 0.3: Failed to write to PO {order.name}. Error: {str(e)}")

    _logger.info(f"Migration 0.3: Completed. Optimized {count} orders. Recovered {recovered_count} signatures. Cleared {cleared_count} corrupt signatures.")
