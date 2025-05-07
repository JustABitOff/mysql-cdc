# MySQL CDC to Apache Iceberg - Terraform Configuration

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
  required_version = ">= 1.0.0"
}

provider "aws" {
  region = var.aws_region

  # Uncomment these if you need to use specific profile or assume a role
  # profile = var.aws_profile
  # assume_role {
  #   role_arn = var.aws_role_arn
  # }
}

# Create a random suffix for resources that need globally unique names
resource "random_id" "suffix" {
  byte_length = 4
}

# Local variables for resource naming and tagging
locals {
  name_prefix = var.name_prefix
  common_tags = {
    Project     = "MySQL-CDC-Iceberg"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}
