variable "aws_region" {
  description = "AWS region for platform resources"
  type        = string
}

variable "sagemaker_image_uri" {
  description = "HuggingFace DLC image for the embedding model (region-specific)"
  type        = string
  default     = "763104351884.dkr.ecr.us-east-1.amazonaws.com/huggingface-pytorch-inference:1.13.1-transformers4.26.0-cpu-py39-ubuntu20.04"
}

variable "embedding_model_name" {
  description = "HuggingFace model id"
  type        = string
  default     = "sentence-transformers/all-MiniLM-L6-v2"
}

variable "min_capacity" {
  description = "Aurora Serverless v2 min ACUs"
  type        = number
  default     = 0.5
}

variable "max_capacity" {
  description = "Aurora Serverless v2 max ACUs"
  type        = number
  default     = 1
}

variable "clerk_jwks_url" {
  description = "Clerk JWKS URL (passed through to SSM for SAM)"
  type        = string
}

variable "clerk_issuer" {
  description = "Clerk issuer URL"
  type        = string
  default     = ""
}

variable "bedrock_region" {
  description = "Bedrock region for dashboards and SAM"
  type        = string
  default     = "us-west-2"
}

variable "bedrock_model_id" {
  description = "Bedrock model id (without bedrock/ prefix)"
  type        = string
  default     = "us.amazon.nova-pro-v1:0"
}

variable "http_api_url" {
  description = "SAM HttpApi base URL (set after sam deploy). Empty on first apply."
  type        = string
  default     = ""
}

variable "openai_api_key" {
  description = "Optional OpenAI key for agent tracing (SSM for SAM)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "polygon_api_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "polygon_plan" {
  type    = string
  default = "free"
}

variable "langfuse_public_key" {
  type    = string
  default = ""
}

variable "langfuse_secret_key" {
  type      = string
  default   = ""
  sensitive = true
}

variable "langfuse_host" {
  type    = string
  default = "https://cloud.langfuse.com"
}
