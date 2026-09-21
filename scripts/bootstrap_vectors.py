#!/usr/bin/env python3
"""Create the S3 Vectors bucket and financial-research index (384, cosine).

A vector bucket is not a normal S3 bucket. Terraform only publishes the name;
this script creates the s3vectors resources.
"""

import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)

INDEX_NAME = "financial-research"
DIMENSION = 384
DISTANCE = "cosine"
PLACEHOLDER_ACCOUNT = "123456789012"


def bucket_name(account: str) -> str:
    configured = os.environ.get("VECTOR_BUCKET", "").strip()
    if not configured or PLACEHOLDER_ACCOUNT in configured:
        return f"alex-vectors-{account}"
    return configured


def ensure_vector_bucket(client, name: str) -> None:
    try:
        client.create_vector_bucket(vectorBucketName=name)
        print(f"Created vector bucket {name}")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"ConflictException", "ResourceAlreadyExistsException"}:
            print(f"Vector bucket {name} already exists")
            return
        raise


def ensure_index(client, bucket: str) -> None:
    try:
        client.create_index(
            vectorBucketName=bucket,
            indexName=INDEX_NAME,
            dataType="float32",
            dimension=DIMENSION,
            distanceMetric=DISTANCE,
        )
        print(f"Created index {INDEX_NAME} on {bucket} ({DIMENSION} dim, {DISTANCE})")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"ConflictException", "ResourceAlreadyExistsException"}:
            print(f"Index {INDEX_NAME} already exists on {bucket}")
            return
        raise


def main() -> None:
    region = os.environ.get("DEFAULT_AWS_REGION") or os.environ.get("AWS_REGION")
    sts = boto3.client("sts", region_name=region)
    account = sts.get_caller_identity()["Account"]
    bucket = bucket_name(account)
    print(f"Region={region}  vector bucket={bucket}")
    client = boto3.client("s3vectors", region_name=region)

    try:
        ensure_vector_bucket(client, bucket)
        ensure_index(client, bucket)
    except ClientError as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        print(
            "If a normal S3 bucket already uses this name, destroy it in Terraform "
            "(vectors.tf no longer creates a general-purpose bucket), then rerun.",
            file=sys.stderr,
        )
        raise


if __name__ == "__main__":
    main()
