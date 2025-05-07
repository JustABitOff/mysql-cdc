# Input variables for MySQL CDC to Apache Iceberg Terraform configuration

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-2"  # Default from .env file
}

variable "aws_profile" {
  description = "AWS profile to use for authentication"
  type        = string
  default     = "default"
}

variable "name_prefix" {
  description = "Prefix to use for naming resources"
  type        = string
  default     = "brzw-cdc-iceberg"
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for Iceberg tables"
  type        = string
  default     = "brzw-cdc-testing"  # Default from .env file
}

variable "connection_name" {
  description = "Arbitrary connection identifier used in S3 paths and Iceberg catalog"
  type        = string
  default     = "local_mysql"  # Default from .env file
}

variable "mysql_schema" {
  description = "MySQL schema to replicate"
  type        = string
  default     = "cdc_database"  # Default from .env file
}

variable "mysql_tables" {
  description = "List of MySQL tables to replicate"
  type        = list(string)
  default     = ["users"]  # Default from .env file
}

variable "force_destroy_bucket" {
  description = "Whether to force destroy the S3 bucket even if it contains objects"
  type        = bool
  default     = false
}

variable "glue_database_name" {
  description = "Name of the AWS Glue database"
  type        = string
  default     = "cdc_iceberg_db"
}
