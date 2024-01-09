resource "aws_s3_bucket" "mysql_cdc_bucket" {
  bucket = "198jnuaifgu42h-mysql-cdc"
  force_destroy = true
}