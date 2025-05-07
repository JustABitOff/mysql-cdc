# Athena resources for MySQL CDC to Apache Iceberg

# Create S3 prefix for Athena query results
resource "aws_s3_object" "athena_results_prefix" {
  bucket       = aws_s3_bucket.iceberg_bucket.id
  key          = "${var.connection_name}/athena-results/"
  content_type = "application/x-directory"
  content      = ""
}

# Athena workgroup for querying Iceberg tables
resource "aws_athena_workgroup" "iceberg_workgroup" {
  name        = "${var.name_prefix}-iceberg-workgroup"
  description = "Workgroup for querying Iceberg tables from MySQL CDC"
  
  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    
    result_configuration {
      output_location = "s3://${aws_s3_bucket.iceberg_bucket.bucket}/${var.connection_name}/athena-results/"
      
      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
    
    engine_version {
      selected_engine_version = "Athena engine version 3"
    }
  }
  
  tags = merge(local.common_tags, {
    Name = "Iceberg Athena Workgroup"
  })
}

# Athena named query for listing tables (example)
resource "aws_athena_named_query" "list_tables" {
  name        = "list_tables"
  description = "List all tables in the Iceberg catalog"
  workgroup   = aws_athena_workgroup.iceberg_workgroup.id
  database    = var.mysql_schema
  query       = "SHOW TABLES IN ${var.mysql_schema}"
}

# Athena data catalog for Iceberg tables
resource "aws_athena_data_catalog" "iceberg_catalog" {
  name        = "iceberg_catalog"
  description = "Iceberg catalog for MySQL CDC data"
  type        = "GLUE"
  
  parameters = {
    "catalog-id" = data.aws_caller_identity.current.account_id
  }
}
