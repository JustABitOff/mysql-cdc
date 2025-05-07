# Outputs for MySQL CDC to Apache Iceberg Terraform configuration

output "s3_bucket_name" {
  description = "Name of the S3 bucket for Iceberg tables"
  value       = aws_s3_bucket.iceberg_bucket.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for Iceberg tables"
  value       = aws_s3_bucket.iceberg_bucket.arn
}

output "glue_data_database_name" {
  description = "Name of the AWS Glue database for data tables (same as MySQL schema)"
  value       = aws_glue_catalog_database.data_database.name
}

output "glue_metadata_database_name" {
  description = "Name of the AWS Glue database for metadata tables"
  value       = aws_glue_catalog_database.metadata_database.name
}

output "glue_role_arn" {
  description = "ARN of the IAM role for Glue"
  value       = aws_iam_role.glue_role.arn
}

output "cdc_app_role_arn" {
  description = "ARN of the IAM role for the CDC application"
  value       = aws_iam_role.cdc_app_role.arn
}

output "table_locations" {
  description = "S3 locations for each Iceberg table"
  value = {
    for table in var.mysql_tables :
    table => "s3://${aws_s3_bucket.iceberg_bucket.bucket}/${var.connection_name}/${var.mysql_schema}/${table}/"
  }
}

output "watermarks_location" {
  description = "S3 location for the watermarks table"
  value       = "s3://${aws_s3_bucket.iceberg_bucket.bucket}/${var.connection_name}/watermarks/"
}

output "expected_table_names" {
  description = "Expected names of the Glue tables (to be created by the application)"
  value = {
    for table in var.mysql_tables :
    table => "${var.mysql_schema}.${table}"
  }
}

output "expected_watermarks_table_name" {
  description = "Expected name of the watermarks Glue table (to be created by the application)"
  value       = "cdc_metadata.watermarks"
}

output "aws_region" {
  description = "AWS region where resources are deployed"
  value       = var.aws_region
}

output "connection_name" {
  description = "Connection name used in S3 paths and Iceberg catalog"
  value       = var.connection_name
}

output "athena_workgroup_name" {
  description = "Name of the Athena workgroup for querying Iceberg tables"
  value       = aws_athena_workgroup.iceberg_workgroup.name
}

output "athena_output_location" {
  description = "S3 location for Athena query results"
  value       = "s3://${aws_s3_bucket.iceberg_bucket.bucket}/${var.connection_name}/athena-results/"
}

output "athena_data_catalog" {
  description = "Athena data catalog for Iceberg tables"
  value       = aws_athena_data_catalog.iceberg_catalog.name
}
