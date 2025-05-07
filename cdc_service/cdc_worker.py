# CDC logic for binlog streaming and event extraction per table

import pymysql
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import (
    DeleteRowsEvent,
    UpdateRowsEvent,
    WriteRowsEvent,
)
import logging
import time
import os

logger = logging.getLogger("cdc_worker")

def get_current_binlog_position(mysql_conn):
    """
    Get current binlog file and position from MySQL.
    
    Returns:
        tuple of (log_file, log_pos)
    """
    with mysql_conn.cursor() as cursor:
        cursor.execute("SHOW MASTER STATUS")
        result = cursor.fetchone()
        if not result:
            raise RuntimeError("Failed to get master status from MySQL")
        return result["File"], int(result["Position"])

def get_binlog_files(mysql_conn):
    """
    Get list of available binlog files from MySQL.
    
    Returns:
        list of binlog files sorted by name
    """
    with mysql_conn.cursor() as cursor:
        cursor.execute("SHOW BINARY LOGS")
        return [row["Log_name"] for row in cursor.fetchall()]

def process_binlog_file(mysql_settings, schema, table, iceberg_writer, watermark_manager, 
                        log_file, start_pos, end_file=None, end_pos=None, server_id=1, batch_size=100):
    """
    Process a single binlog file from start_pos up to end_pos.
    
    Args:
        mysql_settings: MySQL connection settings
        schema: MySQL schema name
        table: MySQL table name
        iceberg_writer: IcebergWriter instance
        watermark_manager: WatermarkManager instance
        log_file: Binlog file to process
        start_pos: Starting position in the binlog file
        end_file: Ending binlog file (if different from log_file)
        end_pos: Ending position (if processing up to a specific position)
        server_id: MySQL replication server ID
        batch_size: Number of events to batch before writing
        
    Returns:
        bool: True if processing is complete, False if more files need processing
    """
    logger.info(f"Processing binlog file {log_file} from position {start_pos}")
    
    # Create binlog stream reader
    stream = BinLogStreamReader(
        connection_settings=mysql_settings,
        server_id=server_id,
        blocking=False,
        resume_stream=True,
        only_events=[DeleteRowsEvent, WriteRowsEvent, UpdateRowsEvent],
        only_tables=[table],
        only_schemas=[schema],
        log_file=log_file,
        log_pos=start_pos,
    )
    
    batch = []
    last_log_file = None
    last_log_pos = None
    
    try:
        # Process events until we reach the end position or run out of events
        for binlogevent in stream:
            # Check if we've reached the end file and position
            current_file = stream.log_file
            current_pos = binlogevent.packet.log_pos
            
            if end_file and end_pos:
                if (current_file > end_file) or (current_file == end_file and current_pos >= end_pos):
                    logger.info(f"Reached end position {end_file}:{end_pos}, stopping")
                    break
            
            # Process the event
            for row in binlogevent.rows:
                if isinstance(binlogevent, WriteRowsEvent):
                    event_type = "insert"
                    row_data = row.get("values", None)
                elif isinstance(binlogevent, UpdateRowsEvent):
                    event_type = "update"
                    row_data = row.get("after_values", None)
                elif isinstance(binlogevent, DeleteRowsEvent):
                    event_type = "delete"
                    row_data = row.get("values", None)
                else:
                    continue

                event = {
                    "event_type": event_type,
                    "timestamp": binlogevent.timestamp,
                    "schema": binlogevent.schema,
                    "table": binlogevent.table,
                    "log_file": current_file,
                    "log_position": current_pos,
                    "row": row_data,
                }
                batch.append(event)
                
                # Track the last position we've seen
                last_log_file = current_file
                last_log_pos = current_pos

                # Send batch if it's full
                if len(batch) >= batch_size:
                    iceberg_writer.send_batch(batch)
                    # Only update watermark after successful batch processing
                    watermark_manager.set_watermark(schema, table, last_log_file, last_log_pos)
                    batch = []
        
        # Send any remaining events
        if batch:
            iceberg_writer.send_batch(batch)
            if last_log_file and last_log_pos:
                watermark_manager.set_watermark(schema, table, last_log_file, last_log_pos)
        
        # Check if we've reached the end file
        if end_file and stream.log_file >= end_file:
            return True
        
        return False
        
    finally:
        stream.close()

def run_cdc_worker(mysql_settings, schema, table, iceberg_writer, watermark_manager, server_id=1, batch_size=100):
    """
    Stream binlog events for a specific table from start to stop position.
    
    This function will:
    1. Get the start position from the watermark
    2. Get the current binlog position from MySQL as the stop position
    3. Process binlogs from start to stop
    4. Exit when processing is complete
    """
    # Get start position from watermark
    watermark = watermark_manager.get_watermark(schema, table)
    start_file = watermark["log_file"]
    start_pos = watermark["log_pos"]
    
    # Connect to MySQL
    conn = pymysql.connect(
        host=mysql_settings["host"],
        port=mysql_settings.get("port", 3306),
        user=mysql_settings["user"],
        password=mysql_settings["passwd"],
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        # Get stop position from MySQL
        stop_file, stop_pos = get_current_binlog_position(conn)
        
        # If no start position, use the current position
        if not start_file:
            logger.info(f"No watermark found, starting from current position {stop_file}:{stop_pos}")
            watermark_manager.set_watermark(schema, table, stop_file, stop_pos)
            return
        
        logger.info(f"Processing binlogs from {start_file}:{start_pos} to {stop_file}:{stop_pos}")
        
        # Get list of binlog files
        binlog_files = get_binlog_files(conn)
        
        # Find the start and stop files in the list
        try:
            start_idx = binlog_files.index(start_file)
            stop_idx = binlog_files.index(stop_file)
        except ValueError:
            logger.error(f"Start or stop file not found in binlog files: {binlog_files}")
            raise RuntimeError("Start or stop binlog file not found")
        
        # Process each binlog file from start to stop
        for i in range(start_idx, stop_idx + 1):
            current_file = binlog_files[i]
            
            # Determine the starting position for this file
            if i == start_idx:
                # For the first file, use the watermark position
                current_start_pos = start_pos
            else:
                # For subsequent files, check if we have a watermark for this file
                file_watermark = watermark_manager.get_watermark(schema, table)
                if file_watermark["log_file"] == current_file:
                    # If we have a watermark for this file, use that position
                    current_start_pos = file_watermark["log_pos"]
                    logger.info(f"Resuming from watermark position in {current_file}:{current_start_pos}")
                else:
                    # Otherwise, start from the beginning of the file
                    current_start_pos = 4  # 4 is the position after binlog header
                    logger.info(f"Starting new file {current_file} from position {current_start_pos}")
            
            # If this is the stop file, pass the stop position
            if i == stop_idx:
                is_complete = process_binlog_file(
                    mysql_settings, schema, table, iceberg_writer, watermark_manager,
                    log_file=current_file, 
                    start_pos=current_start_pos,
                    end_file=stop_file,
                    end_pos=stop_pos,
                    server_id=server_id,
                    batch_size=batch_size
                )
            else:
                # Process the entire file
                is_complete = process_binlog_file(
                    mysql_settings, schema, table, iceberg_writer, watermark_manager,
                    log_file=current_file, 
                    start_pos=current_start_pos,
                    server_id=server_id,
                    batch_size=batch_size
                )
            
            if is_complete:
                break
        
        logger.info(f"Completed processing binlogs from {start_file}:{start_pos} to {stop_file}:{stop_pos}")
        
    finally:
        conn.close()
