# AWS Glue resources for MySQL CDC to Apache Iceberg

# Data source to get the current AWS account ID
data "aws_caller_identity" "current" {}

# Glue Database for data tables (directly using MySQL schema name)
resource "aws_glue_catalog_database" "data_database" {
  name        = var.mysql_schema
  description = "Database for Iceberg tables from MySQL CDC for schema ${var.mysql_schema}"

  catalog_id = data.aws_caller_identity.current.account_id
}

# Glue Database for metadata (watermarks)
resource "aws_glue_catalog_database" "metadata_database" {
  name        = "cdc_metadata"
  description = "Database for Iceberg metadata tables from MySQL CDC"

  catalog_id = data.aws_caller_identity.current.account_id
}


# Note: We're not pre-creating the Glue tables with Terraform anymore.
# Instead, we'll let the PyIceberg application create the tables.
# This ensures that the Iceberg metadata files are properly created in S3.
# 
# The tables will be created with the following structure:
# - Data tables: {mysql_schema}.{table_name}
# - Watermarks table: cdc_metadata.watermarks
#
# The S3 paths will be:
# - Data tables: s3://{bucket}/{connection_name}/{schema}/{table}/
# - Watermarks: s3://{bucket}/{connection_name}/watermarks/
