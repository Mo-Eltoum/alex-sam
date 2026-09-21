output "sagemaker_endpoint_name" {
  value = aws_sagemaker_endpoint.embedding_endpoint.name
}

output "vector_bucket_name" {
  value = local.vector_bucket_name
}

output "aurora_cluster_arn" {
  value = aws_rds_cluster.aurora.arn
}

output "aurora_secret_arn" {
  value     = aws_secretsmanager_secret.db_credentials.arn
  sensitive = true
}

output "database_name" {
  value = aws_rds_cluster.aurora.database_name
}

output "ingest_api_key" {
  value     = random_password.ingest_api_key.result
  sensitive = true
}

output "s3_bucket_name" {
  value = aws_s3_bucket.frontend.id
}

output "cloudfront_url" {
  value = "https://${aws_cloudfront_distribution.main.domain_name}"
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.main.id
}

output "dashboard_urls" {
  value = {
    ai_model_usage    = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.ai_model_usage.dashboard_name}"
    agent_performance = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.agent_performance.dashboard_name}"
  }
}
