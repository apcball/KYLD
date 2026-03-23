import logging

_logger = logging.getLogger(__name__)

def post_init_hook(env):
    """
    Migrates the preserved 'trade_channel_old' string data into the new 'trade_channel_id'
    Many2one relational column.
    """
    cr = env.cr
    tables_to_preserve = [
        'account_move',
        'sale_order',
        'marketplace_settlement',
        'marketplace_settlement_profile',
        'marketplace_vendor_bill',
    ]

    # Insert default trade channels directly if they don't exist
    # (data/trade_channel_data.xml would have created them, but we ensure mapping works)
    
    for table in tables_to_preserve:
        _logger.info("Migrating trade_channel_old to trade_channel_id in table %s", table)
        cr.execute(f"""
            DO $$
            BEGIN
                IF EXISTS(SELECT *
                    FROM information_schema.columns
                    WHERE table_name='{table}' and column_name='trade_channel_old')
                THEN
                    -- Update the new Many2one id based on the string code
                    UPDATE {table} t
                    SET trade_channel_id = mtc.id
                    FROM marketplace_trade_channel mtc
                    WHERE t.trade_channel_old = mtc.code;
                    
                    -- Drop the old column to clean up
                    ALTER TABLE {table} DROP COLUMN trade_channel_old;
                END IF;
            END $$;
        """)
