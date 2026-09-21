resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_secretsmanager_secret" "db_credentials" {
  name                    = "alex-aurora-credentials-${random_id.suffix.hex}"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "alexadmin"
    password = random_password.db_password.result
  })
}

resource "aws_db_subnet_group" "aurora" {
  name       = "alex-aurora-subnet-group"
  subnet_ids = data.aws_subnets.default.ids
}

resource "aws_security_group" "aurora" {
  name        = "alex-aurora-sg"
  description = "Security group for Alex Aurora cluster"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.default.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_rds_cluster" "aurora" {
  cluster_identifier = "alex-aurora-cluster"
  engine             = "aurora-postgresql"
  engine_mode        = "provisioned"
  engine_version     = "15.12"
  database_name      = "alex"
  master_username    = "alexadmin"
  master_password    = random_password.db_password.result

  serverlessv2_scaling_configuration {
    min_capacity = var.min_capacity
    max_capacity = var.max_capacity
  }

  enable_http_endpoint   = true
  db_subnet_group_name   = aws_db_subnet_group.aurora.name
  vpc_security_group_ids = [aws_security_group.aurora.id]

  backup_retention_period      = 7
  preferred_backup_window      = "03:00-04:00"
  preferred_maintenance_window = "sun:04:00-sun:05:00"
  skip_final_snapshot          = true
  apply_immediately            = true
}

resource "aws_rds_cluster_instance" "aurora" {
  identifier         = "alex-aurora-instance-1"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora.engine
  engine_version     = aws_rds_cluster.aurora.engine_version

  performance_insights_enabled = false
}
