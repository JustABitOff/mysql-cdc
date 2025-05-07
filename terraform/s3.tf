# S3 resources for MySQL CDC to Apache Iceberg

# S3 bucket for Iceberg tables
resource "aws_s3_bucket" "iceberg_bucket" {
  bucket = var.s3_bucket_name != "" ? var.s3_bucket_name : "${var.name_prefix}-${random_id.suffix.hex}"
  force_destroy = var.force_destroy_bucket

  tags = merge(local.common_tags, {
    Name = "Iceberg Tables Bucket"
  })
}

# Enable versioning for the S3 bucket
resource "aws_s3_bucket_versioning" "iceberg_bucket_versioning" {
  bucket = aws_s3_bucket.iceberg_bucket.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption for the S3 bucket
resource "aws_s3_bucket_server_side_encryption_configuration" "iceberg_bucket_encryption" {
  bucket = aws_s3_bucket.iceberg_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block public access to the S3 bucket
resource "aws_s3_bucket_public_access_block" "iceberg_bucket_public_access_block" {
  bucket = aws_s3_bucket.iceberg_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Create S3 prefixes for each table
resource "aws_s3_object" "table_prefixes" {
  for_each = toset(var.mysql_tables)

  bucket  = aws_s3_bucket.iceberg_bucket.id
  key     = "${var.connection_name}/${var.mysql_schema}/${each.value}/"
  content_type = "application/x-directory"
  content = ""
}

# Create S3 prefix for watermarks
resource "aws_s3_object" "watermarks_prefix" {
  bucket  = aws_s3_bucket.iceberg_bucket.id
  key     = "${var.connection_name}/watermarks/"
  content_type = "application/x-directory"
  content = ""
}
