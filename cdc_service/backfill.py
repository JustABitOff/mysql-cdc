# Handles initial full-table dump for new tables (backfill logic)

import pymysql
import logging
import time
from datetime import datetime

logger = logging.getLogger("backfill")

def backfill_table(mysql_settings, schema, table, iceberg_writer, watermark_manager, batch_size=1000):
    """
    Dump all rows from the specified table and send to Iceberg in batches.
    """
    conn = pymysql.connect(
        host=mysql_settings["host"],
        port=mysql_settings.get("port", 3306),
        user=mysql_settings["user"],
        password=mysql_settings["passwd"],
        db=schema,
        cursorclass=pymysql.cursors.DictCursor
    )
    
    # Get current timestamp for all backfill events
    current_timestamp = datetime.now()
    
    try:
        # Get current binlog position to use for all backfill events
        with conn.cursor() as cursor:
            cursor.execute("SHOW MASTER STATUS")
            binlog_status = cursor.fetchone()
            if not binlog_status:
                raise RuntimeError("Failed to get master status from MySQL")
            log_file = binlog_status["File"]
            log_pos = int(binlog_status["Position"])
        
        logger.info(f"Starting backfill for {schema}.{table} at {log_file}:{log_pos}")
        
        # Dump all rows
        with conn.cursor() as cursor:
            cursor.execute(f"SELECT * FROM `{table}`")
            batch = []
            row_count = 0
            
            for row in cursor:
                # Create an event similar to CDC events
                event = {
                    "event_type": "backfill",
                    "timestamp": current_timestamp,
                    "schema": schema,
                    "table": table,
                    "log_file": log_file,
                    "log_position": log_pos,
                    "row": row
                }
                batch.append(event)
                row_count += 1
                
                if len(batch) >= batch_size:
                    iceberg_writer.send_batch(batch)
                    logger.info(f"Backfilled {row_count} rows so far for {schema}.{table}")
                    batch = []
            
            # Send any remaining rows
            if batch:
                iceberg_writer.send_batch(batch)
        
        # Mark backfill as complete and update watermark
        watermark_manager.set_watermark(schema, table, log_file, log_pos)
        watermark_manager.mark_backfill_complete(schema, table)
        logger.info(f"Backfill complete for {schema}.{table}, processed {row_count} rows")
        
    except Exception as e:
        logger.error(f"Error during backfill of {schema}.{table}: {str(e)}")
        raise
    finally:
        conn.close()
