#!/usr/bin/env python3
"""Empty S3 frontend bucket, delete SAM stack, terraform destroy."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TF = ROOT / "infra" / "terraform"
SAM = ROOT / "infra" / "sam"


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print(">", " ".join(cmd))
    return subprocess.run(cmd, cwd=cwd, check=check)


def terraform_output(name: str) -> str:
    result = subprocess.run(
        ["terraform", "output", "-raw", name],
        cwd=TF,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def empty_bucket(bucket: str) -> None:
    if not bucket:
        return
    print(f"Emptying s3://{bucket}")
    run(["aws", "s3", "rm", f"s3://{bucket}/", "--recursive"], check=False)


def main() -> None:
    if not (TF / "terraform.tfstate").exists() and not (TF / ".terraform").exists():
        print("No Terraform state found; skipping terraform destroy")
    else:
        bucket = terraform_output("s3_bucket_name")
        empty_bucket(bucket)

    run(["sam", "delete", "--no-prompts"], cwd=SAM, check=False)
    run(["terraform", "destroy", "-auto-approve"], cwd=TF, check=False)
    print("Destroy finished. Check SageMaker endpoints and ECR if terraform still reports leftovers.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
