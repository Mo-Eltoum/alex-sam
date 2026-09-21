locals {
  vector_bucket_name = "alex-vectors-${data.aws_caller_identity.current.account_id}"
}

# Vector buckets live in the s3vectors API, not aws_s3_bucket.
# scripts/bootstrap_vectors.py creates the bucket + financial-research index.

resource "random_password" "ingest_api_key" {
  length  = 32
  special = false
}
