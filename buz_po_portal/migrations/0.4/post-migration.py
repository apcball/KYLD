from odoo import api, SUPERUSER_ID
from odoo.tools.image import image_process
import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    """Resize all existing signature images to prevent wkhtmltopdf memory issues.
    
    This migration fixes the std::bad_alloc error that occurs when printing POs
    with large signature images by resizing them to 1024x1024.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Fields to check and resize
    fields_to_fix = ['prepared_signature', 'reviewed_signature', 'approval_signature']
    
    # Fetch all POs that have at least one signature
    try:
        domain = ['|', '|', 
                  ('prepared_signature', '!=', False), 
                  ('reviewed_signature', '!=', False),
                  ('approval_signature', '!=', False)]
        orders = env['purchase.order'].search(domain)
    except Exception as e:
        _logger.error(f"Migration 0.4: Failed to search orders: {str(e)}")
        return

    _logger.info(f"Migration 0.4: Found {len(orders)} Purchase Orders to check for image resizing.")
    
    count = 0
    
    for order in orders:
        vals = {}
        processed = False
        
        for field in fields_to_fix:
            try:
                img_data = order[field]
                if not img_data:
                    continue

                # Try to resize the image
                try:
                    new_image = image_process(img_data, size=(1024, 1024))
                    
                    # Only update if image was actually changed (means it was resized)
                    if new_image and new_image != img_data:
                        vals[field] = new_image
                        processed = True
                        _logger.info(f"Migration 0.4: Resized {field} for PO {order.name}")
                        
                except Exception as e:
                    # Check if it's a data URI that wasn't properly stripped
                    if isinstance(img_data, bytes) and img_data[:15].startswith(b'data:image'):
                        try:
                            # Extract base64 part
                            if b',' in img_data:
                                _, body = img_data.split(b',', 1)
                                new_image = image_process(body, size=(1024, 1024))
                                if new_image:
                                    vals[field] = new_image
                                    processed = True
                                    _logger.info(f"Migration 0.4: Fixed and resized data URI {field} for PO {order.name}")
                        except Exception as e2:
                            _logger.warning(f"Migration 0.4: Failed to process {field} for PO {order.name}: {e2}")
                    else:
                        _logger.warning(f"Migration 0.4: Failed to resize {field} for PO {order.name}: {e}")
                        
            except Exception as e:
                _logger.warning(f"Migration 0.4: Unexpected error processing {field} for PO {order.name}: {e}")
                continue

        if processed:
            try:
                order.write(vals)
                count += 1
                if count % 10 == 0:
                    _logger.info(f"Migration 0.4: Processed {count} orders...")
                    env.cr.commit()
            except Exception as e:
                _logger.error(f"Migration 0.4: Failed to write to PO {order.name}: {e}")

    _logger.info(f"Migration 0.4: Completed. Resized signatures in {count} orders.")
