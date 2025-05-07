# Handles writing events to Apache Iceberg tables in S3

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pyarrow as pa
from pydantic import BaseModel, Field
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import (
    NestedField,
    StringType,
    TimestampType,
    LongType,
)
from pyiceberg.transforms import DayTransform
from pyiceberg.partitioning import PartitionSpec, PartitionField

logger = logging.getLogger("iceberg_writer")

# Custom JSON encoder for handling datetime and other complex types
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Pydantic model for CDC events
class CdcEvent(BaseModel):
    event_type: str
    timestamp: datetime
    log_file: str = ""
    log_position: int = 0
    row: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }

class IcebergWriter:
    def __init__(self, connection_name, schema, table, region=None):
        """
        Initialize an Iceberg writer for a specific table.
        
        Args:
            connection_name: Arbitrary connection identifier for path/catalog
            schema: MySQL schema name
            table: MySQL table name
            region: AWS region (defaults to AWS_REGION env var)
        """
        self.connection_name = connection_name
        self.schema_name = schema
        self.table_name = table
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")
        
        # Initialize Iceberg catalog using the default catalog from .pyiceberg.yaml
        try:
            self.catalog = load_catalog("default")
            logger.info(f"Successfully loaded Iceberg catalog with region: {self.region}")
            
            # Table identifier in the catalog - use two-level namespace (database.table)
            # Use MySQL schema directly as Glue database name
            self.database_name = schema
            self.table_id = f"{self.database_name}.{table}"
            
            # Load or create table
            try:
                self.iceberg_table = self.catalog.load_table(self.table_id)
                logger.info(f"Loaded existing Iceberg table: {self.table_id}")
            except Exception as e:
                logger.info(f"Table {self.table_id} not found, creating: {str(e)}")
                self._create_table()
        except Exception as e:
            logger.error(f"Failed to initialize Iceberg catalog: {str(e)}")
            logger.error(f"AWS Region: {self.region}")
            logger.error(f"AWS credentials may be invalid or missing")
            raise
    
    def _create_table(self):
        """Create a new Iceberg table with the appropriate schema and partitioning."""
        # Define schema with JSON payload
        schema = Schema(
            NestedField(1, "event_type", StringType()),         # insert/update/delete
            NestedField(2, "timestamp", TimestampType()),       # Event timestamp
            NestedField(3, "log_file", StringType()),           # Binlog file
            NestedField(4, "log_position", LongType()),         # Binlog position
            NestedField(5, "payload", StringType())             # JSON string of the row data
        )
        
        # Partition by date from timestamp
        partition_spec = PartitionSpec(
            PartitionField(source_id=2, transform=DayTransform(), name="date", field_id=1000)
        )
        
        # S3 location
        s3_bucket = os.environ.get("S3_BUCKET", "my-cdc-bucket")
        s3_path = f"s3://{s3_bucket}/{self.connection_name}/{self.schema_name}/{self.table_name}/"
        
        # Create table
        self.iceberg_table = self.catalog.create_table(
            identifier=self.table_id,
            schema=schema,
            location=s3_path,
            partition_spec=partition_spec
        )
        logger.info(f"Created new Iceberg table: {self.table_id} at {s3_path}")
    
    def send_batch(self, events):
        """
        Send a batch of events to the Iceberg table using PyArrow.
        
        Args:
            events: List of dicts with event data
            
        Returns:
            Dict with record count
        """
        if not events:
            logger.warning("Attempted to send empty batch, skipping")
            return {"RecordCount": 0}
        
        # Process events and prepare data for PyArrow
        processed_events = []
        for event in events:
            # Convert MySQL timestamp to Python datetime if needed
            timestamp = event.get("timestamp")
            if isinstance(timestamp, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp)
            
            # Create a Pydantic model for the event to handle serialization
            cdc_event = CdcEvent(
                event_type=event["event_type"],
                timestamp=timestamp,
                log_file=event.get("log_file", ""),
                log_position=event.get("log_position", 0),
                row=event.get("row", {})
            )
            
            # Convert to record format for Iceberg
            processed_events.append({
                "event_type": cdc_event.event_type,
                "timestamp": cdc_event.timestamp,
                "log_file": cdc_event.log_file,
                "log_position": cdc_event.log_position,
                "payload": json.dumps(cdc_event.row, cls=DateTimeEncoder)
            })
        
        try:
            # Define PyArrow schema matching our Iceberg table schema
            arrow_schema = pa.schema([
                pa.field("event_type", pa.string()),
                pa.field("timestamp", pa.timestamp('us')),
                pa.field("log_file", pa.string()),
                pa.field("log_position", pa.int64()),
                pa.field("payload", pa.string())
            ])
            
            # Create PyArrow table
            arrow_table = pa.Table.from_pylist(processed_events, schema=arrow_schema)
            
            # Append the entire batch at once using PyArrow
            self.iceberg_table.append(arrow_table)
            
            logger.info(f"Successfully wrote {len(processed_events)} records to {self.table_id} using PyArrow")
            return {"RecordCount": len(processed_events)}
        except Exception as e:
            logger.error(f"Error writing to Iceberg table {self.table_id}: {str(e)}")
            raise
