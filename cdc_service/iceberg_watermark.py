# Manages Iceberg-based log position watermarking for CDC service

import logging
import os
from datetime import datetime
from typing import Dict, Optional, Any

import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    NestedField,
    StringType,
    TimestampType,
    LongType,
    BooleanType,
)
from pyiceberg.expressions import (
    And,
    EqualTo,
)

logger = logging.getLogger("watermark")

class IcebergWatermarkManager:
    """
    Manages watermarks using an Iceberg table in S3.
    
    This replaces the Redis-based watermark manager with a more durable
    and integrated solution using the same Iceberg technology as the data pipeline.
    """
    
    def __init__(self, connection_name: str, server_id: int = 1, region: Optional[str] = None):
        """
        Initialize an Iceberg watermark manager.
        
        Args:
            connection_name: Identifier for the connection (used in table path)
            server_id: MySQL replication server ID
            region: AWS region (defaults to AWS_REGION env var)
        """
        self.connection_name = connection_name
        self.server_id = server_id
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        
        # Initialize Iceberg catalog using the default catalog from .pyiceberg.yaml
        try:
            self.catalog = load_catalog("default")
            logger.info(f"Successfully loaded Iceberg catalog with region: {self.region}")
            
            # Table identifier in the catalog - use two-level namespace (database.table)
            # Use a dedicated "cdc_metadata" database for watermarks
            self.database_name = "cdc_metadata"
            self.table_id = f"{self.database_name}.watermarks"
            
            # Load or create table
            try:
                self.iceberg_table = self.catalog.load_table(self.table_id)
                logger.info(f"Loaded existing watermark table: {self.table_id}")
            except Exception as e:
                logger.info(f"Watermark table {self.table_id} not found, creating: {str(e)}")
                self._create_table()
        except Exception as e:
            logger.error(f"Failed to initialize Iceberg catalog for watermarks: {str(e)}")
            logger.error(f"AWS Region: {self.region}")
            logger.error(f"AWS credentials may be invalid or missing")
            raise
    
    def _create_table(self):
        """Create a new Iceberg table for watermarks."""
        # Define schema with identifier fields for upsert operations
        schema = Schema(
            NestedField(1, "connection_name", StringType(), required=True),
            NestedField(2, "server_id", LongType(), required=True),
            NestedField(3, "schema", StringType(), required=True),
            NestedField(4, "table", StringType(), required=True),
            NestedField(5, "log_file", StringType()),
            NestedField(6, "log_position", LongType()),
            NestedField(7, "backfill_complete", BooleanType()),
            NestedField(8, "updated_at", TimestampType()),
            # Define identifier fields (composite key) for upsert operations
            identifier_field_ids=[1, 2, 3, 4]
        )
        
        # S3 location
        s3_bucket = os.environ.get("S3_BUCKET", "my-cdc-bucket")
        s3_path = f"s3://{s3_bucket}/{self.connection_name}/watermarks/"
        
        # Create table
        self.iceberg_table = self.catalog.create_table(
            identifier=self.table_id,
            schema=schema,
            location=s3_path
        )
        logger.info(f"Created new watermark table: {self.table_id} at {s3_path}")
    
    def _get_watermark_record(self, schema: str, table: str) -> Optional[Dict[str, Any]]:
        """
        Get the current watermark record for a table.
        
        Args:
            schema: MySQL schema name
            table: MySQL table name
            
        Returns:
            Dict with watermark data or None if not found
        """
        # Build filter expression
        expr = And(
            EqualTo("connection_name", self.connection_name),
            And(
                EqualTo("server_id", self.server_id),
                And(
                    EqualTo("schema", schema),
                    EqualTo("table", table)
                )
            )
        )
        
        # Query the table
        scan = self.iceberg_table.scan(row_filter=expr)
        records = list(scan.to_arrow().to_pylist())
            
        if not records:
            return None
            
        # Return the first (and should be only) record
        return records[0]
    
    def get_watermark(self, schema: str, table: str) -> Dict[str, Any]:
        """
        Get the current watermark for a table.
        
        Args:
            schema: MySQL schema name
            table: MySQL table name
            
        Returns:
            dict with log_file, log_pos, and backfill_complete
        """
        record = self._get_watermark_record(schema, table)
        
        if not record:
            return {
                "log_file": None,
                "log_pos": None,
                "backfill_complete": False
            }
        
        return {
            "log_file": record.get("log_file"),
            "log_pos": record.get("log_position"),
            "backfill_complete": record.get("backfill_complete", False)
        }
    
    def set_watermark(self, schema: str, table: str, log_file: str, log_pos: int) -> bool:
        """
        Update the watermark for a table, only if the new position is greater.
        This should only be called after successful batch processing.
        
        Args:
            schema: MySQL schema name
            table: MySQL table name
            log_file: MySQL binlog file
            log_pos: MySQL binlog position
            
        Returns:
            bool: True if watermark was updated, False otherwise
        """
        if not log_file:
            logger.warning(f"Attempted to set watermark with empty log_file for {schema}.{table}")
            return False
        
        # Get current watermark
        current = self.get_watermark(schema, table)
        
        # Only update if position increases
        if current["log_pos"] is not None:
            if log_file < current["log_file"]:
                return False
            if log_file == current["log_file"] and log_pos <= current["log_pos"]:
                return False
        
        # Prepare record
        record = {
            "connection_name": self.connection_name,
            "server_id": self.server_id,
            "schema": schema,
            "table": table,
            "log_file": log_file,
            "log_position": log_pos,
            "backfill_complete": current.get("backfill_complete", False),
            "updated_at": datetime.now()
        }
        
        # Create PyArrow schema matching our record structure
        arrow_schema = pa.schema([
            pa.field("connection_name", pa.string(), nullable=False),
            pa.field("server_id", pa.int64(), nullable=False),
            pa.field("schema", pa.string(), nullable=False),
            pa.field("table", pa.string(), nullable=False),
            pa.field("log_file", pa.string(), nullable=True),
            pa.field("log_position", pa.int64(), nullable=True),
            pa.field("backfill_complete", pa.bool_(), nullable=True),
            pa.field("updated_at", pa.timestamp('us'), nullable=True)
        ])
        
        # Create PyArrow table with our record
        arrow_table = pa.Table.from_pylist([record], schema=arrow_schema)
        
        # Perform upsert operation
        result = self.iceberg_table.upsert(arrow_table)
        
        logger.info(f"Updated watermark for {schema}.{table} to {log_file}:{log_pos}")
        logger.debug(f"Upsert result: {result.rows_updated} rows updated, {result.rows_inserted} rows inserted")
        return True
    
    def mark_backfill_complete(self, schema: str, table: str):
        """
        Mark a table's backfill as complete.
        
        Args:
            schema: MySQL schema name
            table: MySQL table name
        """
        # Get current watermark
        current = self.get_watermark(schema, table)
        
        # Prepare record
        record = {
            "connection_name": self.connection_name,
            "server_id": self.server_id,
            "schema": schema,
            "table": table,
            "log_file": current.get("log_file"),
            "log_position": current.get("log_pos", 0),
            "backfill_complete": True,
            "updated_at": datetime.now()
        }
        
        # Use PyArrow to create a table for upsert
        import pyarrow as pa
        
        # Create PyArrow schema matching our record structure
        arrow_schema = pa.schema([
            pa.field("connection_name", pa.string(), nullable=False),
            pa.field("server_id", pa.int64(), nullable=False),
            pa.field("schema", pa.string(), nullable=False),
            pa.field("table", pa.string(), nullable=False),
            pa.field("log_file", pa.string(), nullable=True),
            pa.field("log_position", pa.int64(), nullable=True),
            pa.field("backfill_complete", pa.bool_(), nullable=True),
            pa.field("updated_at", pa.timestamp('us'), nullable=True)
        ])
        
        # Create PyArrow table with our record
        arrow_table = pa.Table.from_pylist([record], schema=arrow_schema)
        
        # Perform upsert operation
        result = self.iceberg_table.upsert(arrow_table)
        
        logger.info(f"Marked backfill complete for {schema}.{table}")
        logger.debug(f"Upsert result: {result.rows_updated} rows updated, {result.rows_inserted} rows inserted")
    
    def is_backfill_complete(self, schema: str, table: str) -> bool:
        """
        Check if a table's backfill is complete.
        
        Args:
            schema: MySQL schema name
            table: MySQL table name
            
        Returns:
            bool: True if backfill is complete, False otherwise
        """
        record = self._get_watermark_record(schema, table)
        return record is not None and record.get("backfill_complete", False)
