import logging

_logger = logging.getLogger(__name__)

def pre_init_hook(env):
    """
    Since trade_channel (Selection) is being replaced by trade_channel_id (Many2one),
    we need to ensure existing string values are temporarily renamed in the database
    so we can migrate them after the module finishes its upgrade.
    Otherwise, Odoo drops the column because it changed from string to int reference.
    """
    cr = env.cr
    tables_to_preserve = [
        'account_move',
        'sale_order',
        'marketplace_settlement',
        'marketplace_settlement_profile',
        'marketplace_vendor_bill',
    ]

    for table in tables_to_preserve:
        _logger.info("Preserving trade_channel column in table %s", table)
        cr.execute(f"""
            DO $$
            BEGIN
                IF EXISTS(SELECT *
                    FROM information_schema.columns
                    WHERE table_name='{table}' and column_name='trade_channel')
                THEN
                    ALTER TABLE {table} RENAME COLUMN trade_channel TO trade_channel_old;
                END IF;
            END $$;
        """)
