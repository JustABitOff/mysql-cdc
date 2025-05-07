# IAM resources for MySQL CDC to Apache Iceberg

# IAM role for Glue
resource "aws_iam_role" "glue_role" {
  name = "${var.name_prefix}-glue-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

# Attach AWS managed policy for Glue service
resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Custom policy for S3 access
resource "aws_iam_policy" "s3_access_policy" {
  name        = "${var.name_prefix}-s3-access-policy"
  description = "Policy for accessing S3 bucket for Iceberg tables"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:GetBucketLocation"
        ]
        Effect = "Allow"
        Resource = [
          aws_s3_bucket.iceberg_bucket.arn,
          "${aws_s3_bucket.iceberg_bucket.arn}/*"
        ]
      }
    ]
  })

  tags = local.common_tags
}

# Attach S3 access policy to Glue role
resource "aws_iam_role_policy_attachment" "s3_access" {
  role       = aws_iam_role.glue_role.name
  policy_arn = aws_iam_policy.s3_access_policy.arn
}

# Custom policy for Glue catalog access
resource "aws_iam_policy" "glue_catalog_policy" {
  name        = "${var.name_prefix}-glue-catalog-policy"
  description = "Policy for accessing Glue catalog for Iceberg tables"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "glue:CreateDatabase",
          "glue:DeleteDatabase",
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:UpdateDatabase",
          "glue:CreateTable",
          "glue:DeleteTable",
          "glue:BatchDeleteTable",
          "glue:UpdateTable",
          "glue:GetTable",
          "glue:GetTables",
          "glue:BatchCreatePartition",
          "glue:CreatePartition",
          "glue:DeletePartition",
          "glue:BatchDeletePartition",
          "glue:UpdatePartition",
          "glue:GetPartition",
          "glue:GetPartitions",
          "glue:BatchGetPartition"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })

  tags = local.common_tags
}

# Attach Glue catalog policy to Glue role
resource "aws_iam_role_policy_attachment" "glue_catalog" {
  role       = aws_iam_role.glue_role.name
  policy_arn = aws_iam_policy.glue_catalog_policy.arn
}

# IAM role for the CDC application
resource "aws_iam_role" "cdc_app_role" {
  name = "${var.name_prefix}-cdc-app-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"  # Adjust based on where your app runs
        }
      }
    ]
  })

  tags = local.common_tags
}

# Custom policy for Athena access
resource "aws_iam_policy" "athena_policy" {
  name        = "${var.name_prefix}-athena-policy"
  description = "Policy for accessing Athena for querying Iceberg tables"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StopQueryExecution",
          "athena:GetWorkGroup",
          "athena:BatchGetQueryExecution",
          "athena:GetNamedQuery",
          "athena:ListNamedQueries",
          "athena:CreateNamedQuery",
          "athena:DeleteNamedQuery",
          "athena:GetQueryResultsStream",
          "athena:ListQueryExecutions",
          "athena:GetDataCatalog",
          "athena:ListDataCatalogs",
          "athena:GetDatabase",
          "athena:ListDatabases",
          "athena:GetTableMetadata",
          "athena:ListTableMetadata"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })

  tags = local.common_tags
}

# Attach S3, Glue, and Athena policies to CDC app role
resource "aws_iam_role_policy_attachment" "cdc_app_s3" {
  role       = aws_iam_role.cdc_app_role.name
  policy_arn = aws_iam_policy.s3_access_policy.arn
}

resource "aws_iam_role_policy_attachment" "cdc_app_glue" {
  role       = aws_iam_role.cdc_app_role.name
  policy_arn = aws_iam_policy.glue_catalog_policy.arn
}

resource "aws_iam_role_policy_attachment" "cdc_app_athena" {
  role       = aws_iam_role.cdc_app_role.name
  policy_arn = aws_iam_policy.athena_policy.arn
}
