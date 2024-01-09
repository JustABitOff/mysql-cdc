resource "aws_dynamodb_table" "cdc_stream_state" {
  name           = "cdc_stream_state"
  hash_key       = "server_id"
  read_capacity  = 5
  write_capacity = 5

  attribute {
    name = "server_id"
    type = "N"
  }
}