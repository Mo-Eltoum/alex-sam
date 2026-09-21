#!/usr/bin/env python3
"""Terraform -> SAM -> CloudFront origin -> frontend S3 sync."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TF = ROOT / "infra" / "terraform"
SAM = ROOT / "infra" / "sam"
FRONTEND = ROOT / "frontend"
IS_WINDOWS = sys.platform == "win32"


def run(cmd: list[str] | str, cwd: Path | None = None, env: dict | None = None, capture: bool = False) -> str:
    print(">", cmd if isinstance(cmd, str) else " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        shell=isinstance(cmd, str),
        check=True,
        capture_output=capture,
        text=True,
    )
    return (result.stdout or "").strip() if capture else ""


def terraform_output(name: str) -> str:
    return run(["terraform", "output", "-raw", name], cwd=TF, capture=True)


def sam_http_api_url() -> str:
    raw = run(["sam", "list", "stack-outputs", "--output", "json"], cwd=SAM, capture=True)
    try:
        outputs = json.loads(raw)
    except json.JSONDecodeError:
        return terraform_output("cloudfront_url") and ""
    if isinstance(outputs, list):
        for item in outputs:
            if item.get("OutputKey") == "HttpApiUrl":
                return item.get("OutputValue", "")
    if isinstance(outputs, dict):
        return outputs.get("HttpApiUrl", "")
    return ""


def main() -> None:
    if not (TF / "terraform.tfvars").exists():
        sys.exit("Copy infra/terraform/terraform.tfvars.example to terraform.tfvars first")

    if not (TF / ".terraform").exists():
        run(["terraform", "init"], cwd=TF)
    run(["terraform", "apply", "-auto-approve"], cwd=TF)

    run([sys.executable, str(ROOT / "scripts" / "export_requirements.py")])

    run(["sam", "build", "--use-container"], cwd=SAM)
    run(["sam", "deploy", "--no-confirm-changeset"], cwd=SAM)

    http_api = sam_http_api_url()
    if not http_api:
        try:
            http_api = run(
                [
                    "aws",
                    "ssm",
                    "get-parameter",
                    "--name",
                    "/alex/http_api_url",
                    "--query",
                    "Parameter.Value",
                    "--output",
                    "text",
                ],
                capture=True,
            )
        except subprocess.CalledProcessError:
            http_api = ""

    if http_api:
        run(
            ["terraform", "apply", "-auto-approve", f"-var=http_api_url={http_api}"],
            cwd=TF,
        )

    bucket = terraform_output("s3_bucket_name")
    dist_id = terraform_output("cloudfront_distribution_id")
    cloudfront_url = terraform_output("cloudfront_url")

    if not (FRONTEND / "node_modules").exists():
        run("npm install" if IS_WINDOWS else ["npm", "install"], cwd=FRONTEND)

    env = os.environ.copy()
    env["NODE_ENV"] = "production"
    if http_api:
        env["NEXT_PUBLIC_API_URL"] = http_api
    run("npm run build" if IS_WINDOWS else ["npm", "run", "build"], cwd=FRONTEND, env=env)

    out = FRONTEND / "out"
    if not out.exists():
        sys.exit("frontend/out missing — check next.config output: export")

    run(["aws", "s3", "sync", str(out) + "/", f"s3://{bucket}/", "--delete"])
    if dist_id:
        run(
            [
                "aws",
                "cloudfront",
                "create-invalidation",
                "--distribution-id",
                dist_id,
                "--paths",
                "/*",
            ]
        )

    print("\nDeploy complete")
    print(f"  CloudFront: {cloudfront_url}")
    print(f"  HttpApi:    {http_api}")


if __name__ == "__main__":
    main()
