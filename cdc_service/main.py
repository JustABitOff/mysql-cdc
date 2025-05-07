# Entrypoint for CDC service
# Uses environment variables for configuration and launches CDC logic for the assigned table
# Includes signal handling for graceful shutdown

import os
import logging
import signal
import sys

from cdc_service.iceberg_writer import IcebergWriter
from cdc_service.iceberg_watermark import IcebergWatermarkManager
from cdc_service.backfill import backfill_table
from cdc_service.cdc_worker import run_cdc_worker

def setup_logging():
    """Configure logging with a standard format."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )

def get_env_var(name, default=None, required=False):
    """
    Get an environment variable with validation.
    
    Args:
        name: Name of the environment variable
        default: Default value if not set
        required: Whether the variable is required
        
    Returns:
        The value of the environment variable, or the default
        
    Raises:
        RuntimeError: If the variable is required but not set
    """
    value = os.environ.get(name, default)
    if required and value is None:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value

def get_env_int(name, default=None, required=False):
    """Get an environment variable as an integer."""
    value = get_env_var(name, default, required)
    if value is not None:
        return int(value)
    return None

def main():
    """Main entrypoint for the CDC service."""
    setup_logging()
    logger = logging.getLogger("main")

    # Handle SIGTERM/SIGINT for graceful shutdown
    def handle_signal(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully.")
        sys.exit(0)
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Get environment variables
    schema = get_env_var("CDC_SCHEMA", required=True)
    table = get_env_var("CDC_TABLE", required=True)
    mode = get_env_var("CDC_MODE", "cdc")
    connection_name = get_env_var("CONNECTION_NAME", required=True)
    
    mysql_host = get_env_var("MYSQL_HOST", "localhost")
    mysql_port = get_env_int("MYSQL_PORT", 3306)
    mysql_user = get_env_var("MYSQL_USER", "root")
    mysql_passwd = get_env_var("MYSQL_PASSWD", "password")
    
    server_id = get_env_int("CDC_SERVER_ID", 1)
    region = get_env_var("AWS_REGION", "us-east-2")
    
    batch_size = get_env_int("BATCH_SIZE", 1000)
    
    logger.info(f"Starting CDC service for {schema}.{table} in {mode} mode")
    logger.info(f"Connection name: {connection_name}")
    logger.info(f"MySQL: {mysql_host}:{mysql_port}")
    logger.info(f"AWS Region: {region}")
    logger.info(f"Environment AWS_REGION: {os.environ.get('AWS_REGION', 'not set')}")

    # Initialize components
    iceberg_writer = IcebergWriter(
        connection_name=connection_name,
        schema=schema,
        table=table
    )
    
    watermark_manager = IcebergWatermarkManager(
        connection_name=connection_name,
        server_id=server_id
    )

    mysql_settings = {
        "host": mysql_host,
        "port": mysql_port,
        "user": mysql_user,
        "passwd": mysql_passwd
    }

    # Run in the appropriate mode
    if mode.lower() == "backfill":
        if watermark_manager.is_backfill_complete(schema, table):
            logger.info(f"Backfill already complete for {schema}.{table}")
        else:
            logger.info(f"Starting backfill for {schema}.{table}")
            backfill_table(
                mysql_settings,
                schema,
                table,
                iceberg_writer,
                watermark_manager,
                batch_size=batch_size
            )
    else:  # CDC mode
        logger.info(f"Starting CDC processing for {schema}.{table}")
        run_cdc_worker(
            mysql_settings,
            schema,
            table,
            iceberg_writer,
            watermark_manager,
            server_id=server_id,
            batch_size=batch_size
        )

if __name__ == "__main__":
    main()
