resource "aws_ssm_parameter" "sagemaker_endpoint" {
  name  = "/alex/sagemaker_endpoint"
  type  = "String"
  value = aws_sagemaker_endpoint.embedding_endpoint.name
}

resource "aws_ssm_parameter" "vector_bucket" {
  name  = "/alex/vector_bucket"
  type  = "String"
  value = local.vector_bucket_name
}

resource "aws_ssm_parameter" "ingest_api_key" {
  name  = "/alex/ingest_api_key"
  # String (not SecureString): CloudFormation AWS::SSM::Parameter::Value<String> cannot resolve SecureString.
  type  = "String"
  value = random_password.ingest_api_key.result
}

resource "aws_ssm_parameter" "aurora_cluster_arn" {
  name  = "/alex/aurora_cluster_arn"
  type  = "String"
  value = aws_rds_cluster.aurora.arn
}

resource "aws_ssm_parameter" "aurora_secret_arn" {
  name  = "/alex/aurora_secret_arn"
  type  = "String"
  value = aws_secretsmanager_secret.db_credentials.arn
}

resource "aws_ssm_parameter" "database_name" {
  name  = "/alex/database_name"
  type  = "String"
  value = aws_rds_cluster.aurora.database_name
}

resource "aws_ssm_parameter" "clerk_jwks_url" {
  name  = "/alex/clerk_jwks_url"
  type  = "String"
  value = var.clerk_jwks_url
}

resource "aws_ssm_parameter" "clerk_issuer" {
  name  = "/alex/clerk_issuer"
  type  = "String"
  value = var.clerk_issuer
}

resource "aws_ssm_parameter" "bedrock_region" {
  name  = "/alex/bedrock_region"
  type  = "String"
  value = var.bedrock_region
}

resource "aws_ssm_parameter" "bedrock_model_id" {
  name  = "/alex/bedrock_model_id"
  type  = "String"
  value = var.bedrock_model_id
}

resource "aws_ssm_parameter" "aws_region" {
  name  = "/alex/aws_region"
  type  = "String"
  value = var.aws_region
}

resource "aws_ssm_parameter" "polygon_api_key" {
  count = var.polygon_api_key != "" ? 1 : 0
  name  = "/alex/polygon_api_key"
  type  = "SecureString"
  value = var.polygon_api_key
}

resource "aws_ssm_parameter" "openai_api_key" {
  count = var.openai_api_key != "" ? 1 : 0
  name  = "/alex/openai_api_key"
  type  = "SecureString"
  value = var.openai_api_key
}

resource "aws_ssm_parameter" "langfuse_public_key" {
  count = var.langfuse_public_key != "" ? 1 : 0
  name  = "/alex/langfuse_public_key"
  type  = "String"
  value = var.langfuse_public_key
}

resource "aws_ssm_parameter" "langfuse_secret_key" {
  count = var.langfuse_secret_key != "" ? 1 : 0
  name  = "/alex/langfuse_secret_key"
  type  = "SecureString"
  value = var.langfuse_secret_key
}

resource "aws_ssm_parameter" "langfuse_host" {
  name  = "/alex/langfuse_host"
  type  = "String"
  value = var.langfuse_host
}
