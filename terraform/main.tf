provider "aws" {
  default_tags {
    tags = {
      Environment = "cdc mysql"
    }
  }
}