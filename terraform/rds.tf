##THIS CAN BE USED INSTEAD OF THE LOCAL MYSQL DOCKER CONTAINER
# resource "aws_rds_cluster_parameter_group" "cdc-parameter-group" {
#   name   = "cdc-parameter-group"
#   family = "aurora-mysql8.0"

#   parameter {
#     name  = "binlog_format"
#     value = "ROW"
#     apply_method = "pending-reboot"
#   }

#   parameter {
#     name = "binlog_row_metadata"
#     value = "FULL"
#     apply_method = "pending-reboot"
#   }

#   parameter {
#     name = "binlog_row_image"
#     value = "FULL"
#     apply_method = "pending-reboot"
#   }
# }

# resource "aws_db_subnet_group" "cdc-subnet-group" {
#   name       = "cdc-subnet-group"
#   subnet_ids = [aws_subnet.public-2a.id, aws_subnet.public-2b.id]
# }

# resource "aws_rds_cluster_instance" "cluster_instances" {
#   count              = 2
#   identifier         = "cdc-cluster-${count.index}"
#   cluster_identifier = aws_rds_cluster.cdc-cluster.id
#   instance_class     = "db.t3.medium"
#   engine             = aws_rds_cluster.cdc-cluster.engine
#   engine_version     = aws_rds_cluster.cdc-cluster.engine_version
#   publicly_accessible = true
# }

# resource "aws_rds_cluster" "cdc-cluster" {
#   cluster_identifier = "cdc-cluster"
#   engine             = "aurora-mysql"
#   engine_version     = "8.0.mysql_aurora.3.04.0"
#   availability_zones = ["us-east-2a", "us-east-2b"]
#   vpc_security_group_ids = [aws_security_group.public_web_sec_grp.id]
#   database_name      = "cdc_testing"
#   master_username    = "super_secret_username"
#   master_password    = "password"
#   skip_final_snapshot = true
#   db_subnet_group_name = aws_db_subnet_group.cdc-subnet-group.name
#   db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.cdc-parameter-group.name
# }