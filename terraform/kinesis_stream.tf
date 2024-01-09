resource "aws_kinesis_stream" "mysql_cdc_stream" {
  name             = "mysql_cdc_stream"
  retention_period = 24

  stream_mode_details {
    stream_mode = "ON_DEMAND"
  }
}