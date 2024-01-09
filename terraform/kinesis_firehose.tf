resource "aws_kinesis_firehose_delivery_stream" "mysql_cdc_to_s3_stream" {
  name        = "mysql_cdc_to_s3_stream"
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.mysql_cdc_stream.arn
    role_arn = aws_iam_role.firehose_role.arn
  }

  extended_s3_configuration {
    role_arn   = aws_iam_role.firehose_role.arn
    bucket_arn = aws_s3_bucket.mysql_cdc_bucket.arn

    buffering_size = 64

    dynamic_partitioning_configuration {
      enabled = "true"
    }

    prefix              = "schema=!{partitionKeyFromQuery:schema}/table=!{partitionKeyFromQuery:table}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/"
    error_output_prefix = "errors/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/!{firehose:error-output-type}/"

    processing_configuration {
      enabled = "true"

      processors {
        type = "RecordDeAggregation"
        parameters {
          parameter_name  = "SubRecordType"
          parameter_value = "JSON"
        }
      }

      processors {
        type = "AppendDelimiterToRecord"
      }

      processors {
        type = "MetadataExtraction"
        parameters {
          parameter_name  = "JsonParsingEngine"
          parameter_value = "JQ-1.6"
        }
        parameters {
          parameter_name  = "MetadataExtractionQuery"
          parameter_value = "{schema:.schema,table:.table}"
        }
      }
    }
  }
}

data "aws_iam_policy_document" "firehose_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "firehose_role" {
  name               = "firehose_role"
  assume_role_policy = data.aws_iam_policy_document.firehose_assume_role.json
}

resource "aws_iam_policy" "firehose_policy" {
  name = "firehose_policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action = [
            "firehose:PutRecord",
            "firehose:PutRecordBatch"
        ]
        Resource = [
            "${aws_kinesis_firehose_delivery_stream.mysql_cdc_to_s3_stream.arn}"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "firehose_policy_attachment" {
  role       = aws_iam_role.firehose_role.name
  policy_arn = aws_iam_policy.firehose_policy.arn
}

resource "aws_iam_policy" "s3_firehose_policy" {
  name = "s3_firehose_policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action = [
            "s3:AbortMultipartUpload",
            "s3:GetBucketLocation",
            "s3:GetObject",
            "s3:ListBucket",
            "s3:ListBucketMultipartUploads",
            "s3:PutObject",
        ]
        Resource = [
            "${aws_s3_bucket.mysql_cdc_bucket.arn}",
            "${aws_s3_bucket.mysql_cdc_bucket.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "s3_firehose_policy_attachment" {
  role       = aws_iam_role.firehose_role.name
  policy_arn = aws_iam_policy.s3_firehose_policy.arn
}

resource "aws_iam_policy" "kinesis_policy" {
  name = "kinesis_policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action = [
            "kinesis:DescribeStream",
            "kinesis:GetShardIterator",
            "kinesis:GetRecords",
            "kinesis:ListShards"
        ]
        Resource = [
            "${aws_kinesis_stream.mysql_cdc_stream.arn}"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "kinesis_policy_attachment" {
  role       = aws_iam_role.firehose_role.name
  policy_arn = aws_iam_policy.kinesis_policy.arn
}