resource "aws_iam_role" "sagemaker_role" {
  name = "alex-sagemaker-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "sagemaker.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "sagemaker_full_access" {
  role       = aws_iam_role.sagemaker_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}

resource "aws_sagemaker_model" "embedding_model" {
  name               = "alex-embedding-model"
  execution_role_arn = aws_iam_role.sagemaker_role.arn

  primary_container {
    image = var.sagemaker_image_uri
    environment = {
      HF_MODEL_ID = var.embedding_model_name
      HF_TASK     = "feature-extraction"
    }
  }

  depends_on = [aws_iam_role_policy_attachment.sagemaker_full_access]
}

resource "aws_sagemaker_endpoint_configuration" "serverless_config" {
  name = "alex-embedding-serverless-config"

  production_variants {
    model_name = aws_sagemaker_model.embedding_model.name

    serverless_config {
      memory_size_in_mb = 3072
      max_concurrency   = 2
    }
  }
}

resource "time_sleep" "wait_for_iam_propagation" {
  depends_on      = [aws_iam_role_policy_attachment.sagemaker_full_access]
  create_duration = "15s"
}

resource "aws_sagemaker_endpoint" "embedding_endpoint" {
  name                 = "alex-embedding-endpoint"
  endpoint_config_name = aws_sagemaker_endpoint_configuration.serverless_config.name

  depends_on = [time_sleep.wait_for_iam_propagation]
}
