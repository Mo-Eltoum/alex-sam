# Alex SAM

Alex (Agentic Learning Equities eXplainer) is a multi-agent financial planner. This repo is a production-style rebuild of [Alex](https://github.com/ed-donner/alex) by [Ed Donner](https://github.com/ed-donner), the capstone for his Udemy course *AI in Production*. The original repository holds the course guides, the seven Terraform directories, and the MIT license this code is derived from. A longer comparison is in [course-vs-sam.md](course-vs-sam.md).

This rebuild uses **one Terraform root** for platform services, **AWS SAM** for every Lambda, and **SSM** to wire them together. No hand-copied ARNs between directories.

Destroy the [course stack](https://github.com/ed-donner/alex) before the first deploy here so names can stay `alex-*`.

## What changed from the course


| Course                                                | This repo                                                 |
| ----------------------------------------------------- | --------------------------------------------------------- |
| Seven Terraform dirs, local state each                | `infra/terraform/` — one apply, one `terraform.tfstate`   |
| `package_docker.py` + taint + `deploy_all_lambdas.py` | `sam build --use-container && sam deploy`                 |
| App Runner / public Function URL for researcher       | Researcher image Lambda on the same HttpApi (`/research`) |
| Paste `terraform output` into the next `tfvars`       | Terraform writes `/alex/*` SSM params; SAM reads them     |
| Shared `alex-lambda-agents-role`                      | Per-function IAM in the SAM template                      |




## Layout

```
alex-sam/
  backend/          uv workspace (agents, api, database, ingest, researcher)
  frontend/         Next.js (Pages Router) + Clerk
  infra/terraform/  SageMaker, Aurora, vectors, CloudFront, dashboards, SSM
  infra/sam/        All Lambdas, SQS, HttpApi
  scripts/          deploy, destroy, local run, vector index, requirements export
```



## Prerequisites

- AWS CLI configured as `aiengineer` (or equivalent) with the course **AlexAccess** group
- Terraform >= 1.5
- AWS SAM CLI
- Docker Desktop running (`sam build --use-container` needs it)
- `uv` and Node.js 20+
- Bedrock model access for **Nova Pro** in your Bedrock region (often `us-west-2` or your home region)
- Clerk app (publishable + secret + JWKS URL)
- Optional: Polygon.io key, OpenAI key (tracing), LangFuse keys

Copy env templates (never commit real secrets):

```bash
cp .env.example .env
cp frontend/.env.local.example frontend/.env.local   # if present; otherwise create .env.local
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
```

Fill `aws_region`, Clerk URLs, Bedrock model, Polygon/OpenAI/LangFuse as needed.

### Destroy the course stack first

From the **course** repo, reverse order. Confirm the console is empty of `alex-aurora-cluster`, `alex-planner`, and the old CloudFront distribution before continuing.

```bash
# course repo
cd terraform/8_enterprise && terraform destroy
cd ../7_frontend && terraform destroy
cd ../6_agents && terraform destroy
cd ../5_database && terraform destroy   # biggest cost
cd ../4_researcher && terraform destroy
cd ../3_ingestion && terraform destroy
cd ../2_sagemaker && terraform destroy
```

If destroy hangs: delete the SageMaker endpoint, empty S3 buckets, delete ECR images, then retry.

---



# Part 1 — AWS permissions

Same as the course. You should already have:

- IAM group `AlexAccess` (SageMaker, Bedrock, EventBridge, custom `s3vectors:*`)
- Guide 5 extras: RDS Data API, Secrets Manager, Lambda, SQS

Verify:

```bash
aws sts get-caller-identity
aws sagemaker list-endpoints
aws rds describe-db-clusters
```

If any command returns AccessDenied, fix IAM before going on. Do not debug Terraform or SAM for permission errors.

---



# Part 2 — SageMaker embeddings

Deploys `alex-embedding-endpoint` (`all-MiniLM-L6-v2`, serverless, 384-dim).

```bash
cd infra/terraform
terraform init
terraform apply \
  -target=aws_iam_role.sagemaker_role \
  -target=aws_iam_role_policy_attachment.sagemaker_full_access \
  -target=aws_sagemaker_model.embedding_model \
  -target=aws_sagemaker_endpoint_configuration.serverless_config \
  -target=time_sleep.wait_for_iam_propagation \
  -target=aws_sagemaker_endpoint.embedding_endpoint \
  -target=aws_ssm_parameter.sagemaker_endpoint
```

First create can take 3–5 minutes. Do not interrupt.

**Test** (from repo root, payload is `backend/vectorize_me.json`):

```bash
aws sagemaker-runtime invoke-endpoint \
  --endpoint-name alex-embedding-endpoint \
  --content-type application/json \
  --body fileb://backend/vectorize_me.json \
  --output json /dev/stdout
```

You should see a JSON array of 384 floats. Cold start can be 10–60s.

**Debug**


| Symptom                      | Check                                                                                           |
| ---------------------------- | ----------------------------------------------------------------------------------------------- |
| Endpoint already exists      | `terraform import aws_sagemaker_endpoint.embedding_endpoint alex-embedding-endpoint` then apply |
| IAM role invalid             | Wait a minute, destroy the SageMaker targets, apply again (IAM propagation)                     |
| Model not found / image pull | `sagemaker_image_uri` in `terraform.tfvars` must match your region’s HuggingFace DLC            |
| Status not InService         | `aws sagemaker describe-endpoint --endpoint-name alex-embedding-endpoint`                       |


Add to `.env`: `SAGEMAKER_ENDPOINT=alex-embedding-endpoint`

---



# Part 3 — Vector bucket + ingest Lambda



## 3a. Vector bucket (not a normal S3 bucket)

S3 Vectors uses the `s3vectors` API. Terraform only publishes the name `/alex/vector_bucket`. The bootstrap script creates the **vector** bucket and the `financial-research` index.

If you already applied the old `aws_s3_bucket.vectors` resource, apply again so Terraform **destroys that general-purpose bucket** (same name cannot be both types):

```bash
cd infra/terraform
terraform apply \
  -target=aws_ssm_parameter.vector_bucket \
  -target=random_password.ingest_api_key \
  -target=aws_ssm_parameter.ingest_api_key
```

Leave `VECTOR_BUCKET` empty in `.env` (do not keep the example `alex-vectors-123456789012`). Then from repo root:

```bash
uv run --directory scripts bootstrap_vectors.py
```

Expected: vector bucket `alex-vectors-{account-id}` and index `financial-research` (384 dim, cosine).

## 3b. Ingest function (SAM)

SAM does not take Aurora ARNs or bucket names on the prompt. Each parameter is an **SSM path** (`/alex/...`). Terraform writes the real values; CloudFormation reads them at deploy time.

Targeted applies in Parts 2–5 create SageMaker / vectors / Aurora SSM only. They **do not** create region, Bedrock, or Clerk. Apply those before the first `sam deploy` (Clerk can stay the `your-instance` placeholder until Part 7):

```bash
cd infra/terraform
terraform apply \
  -target=aws_ssm_parameter.aws_region \
  -target=aws_ssm_parameter.bedrock_region \
  -target=aws_ssm_parameter.bedrock_model_id \
  -target=aws_ssm_parameter.clerk_jwks_url \
  -target=aws_ssm_parameter.clerk_issuer
```

If you have not applied Aurora yet, skip to Part 5 first, then come back and `sam deploy` once. If you want ingest-only testing after Part 5 SSM exists:

```bash
uv run --directory scripts export_requirements.py
cd infra/sam
sam build --use-container
sam deploy --guided   # first time only; later: sam deploy
```

On `--guided`: press **Enter** on parameter prompts (keep the `/alex/...` defaults). Do not paste ARNs. Answer **Y** for IAM capabilities, confirm changeset, and save to `samconfig.toml`.

Zip and image Lambdas share this one template. `Runtime` is set on each zip function, not in `Globals` (an image function cannot inherit `Runtime` / `Handler` / `Layers`). Do not put `!Sub https://${AlexHttpApi}...` on a Lambda that is also an event source for that API — that is a CloudFormation circular dependency. SAM writes `/alex/http_api_url` after the API exists; researcher and scheduler read it at runtime.

`/alex/ingest_api_key` must be SSM type `String` (not `SecureString`). CloudFormation `AWS::SSM::Parameter::Value<String>` cannot resolve SecureString.

This will take some time to run. 

**Test ingest locally** (no deploy) after `sam build`:

`--env-vars env.json` sets `ALEX_API_KEY=local-dev-key`. `events/ingest.json` must send the same value as `x-api-key`. Without `--env-vars`, SAM fills `ALEX_API_KEY` from SSM and a local key returns 401.

```bash
sam local invoke IngestFunction \
  --event events/ingest.json \
  --env-vars env.json
```

**Test against AWS:**

```bash
cd backend/ingest
uv run test_ingest_s3vectors.py
uv run test_search_s3vectors.py
```

Or HTTP:

```bash
curl -X POST "$HTTP_API_URL/ingest" \
  -H "x-api-key: $ALEX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Test document via API", "metadata": {"source": "api_test"}}'
```

Get `HTTP_API_URL` and `ALEX_API_KEY` from:

```bash
aws ssm get-parameter --name /alex/http_api_url --query Parameter.Value --output text
aws ssm get-parameter --name /alex/ingest_api_key --query Parameter.Value --output text
```

(`http_api_url` exists only after `sam deploy`.)

**Debug**


| Symptom                                       | Check                                                                                                                                         |
| --------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Vector bucket not found                       | Must be an s3vectors bucket, not `aws_s3_bucket`. Empty placeholder `VECTOR_BUCKET` in `.env`. Run `bootstrap_vectors.py`. Region must match. |
| AccessDenied on `s3vectors:*`                 | IAM user policy `AlexS3VectorsAccess`; Lambda policy in SAM                                                                                   |
| 500 from ingest                               | `aws logs tail /aws/lambda/alex-ingest --follow` — SageMaker env, index name                                                                  |
| `sam local invoke` 401 `x-api-key`            | Pass `--env-vars env.json`. Event header `x-api-key` must equal `ALEX_API_KEY` (`local-dev-key`).                                              |
| `sam local invoke` index not found            | `env.json` `VECTOR_BUCKET` must be `alex-vectors-{account-id}`, not `alex-vectors-placeholder`. Index `financial-research` comes from `bootstrap_vectors.py`. |
| SAM build fails (Docker)                      | Docker Desktop running; `sam build --use-container`                                                                                           |
| SAM build: `Unexpected character: ':'`        | `samconfig.toml` must be TOML (`version = 0.1`), not YAML (`version: 0.1`).                                                                   |
| `Unable to fetch parameters [/alex/...]`      | Targeted Terraform skipped those SSM keys. Apply `aws_region`, `bedrock_*`, and `clerk_*` as above, then `sam deploy` (no `--guided`).         |
| `types not supported by CloudFormation`       | `/alex/ingest_api_key` is still SecureString. Terraform type is `String`; replace the parameter (`terraform apply -replace=aws_ssm_parameter.ingest_api_key`). |
| `Runtime, Handler, Layers cannot be present` when `PackageType` is `Image` | `Runtime` leaked from `Globals` onto Researcher. Keep `Runtime` on zip functions only. |
| Circular dependency involving `AlexHttpApi`   | A Lambda on that HttpApi must not `!Ref` / `!Sub` the API URL. Researcher/scheduler read `/alex/http_api_url` at runtime. You do not need nested stacks. |
| Reserved keys: `AWS_REGION`                   | Lambda forbids setting `AWS_REGION` in function env. It is injected by the runtime. Keep `AWS_REGION_NAME` (LiteLLM) and `DEFAULT_AWS_REGION` only. |
| Layer import error `from src import Database` | Layer must unpack `python/src/` — re-run `export_requirements.py`                                                                             |


---



# Part 4 — Researcher

Image Lambda (Playwright MCP + FastAPI) on HttpApi `POST /research`, not a public Function URL. Same SAM stack as the zip functions — no nested template.

Researcher does not get the HttpApi URL as a CloudFormation env var (that loops). After deploy it reads SSM `/alex/http_api_url` and POSTs `/ingest`. Local runs can still set `ALEX_API_ENDPOINT` in `.env`.

After platform SSM exists and `sam deploy`. The test reads SSM `/alex/http_api_url` (or `HTTP_API_URL` in `.env`). It does not use `terraform/4_researcher` or `git rev-parse`.

```bash
cd backend/researcher
uv run test_research.py
```

Health:

```bash
curl "$HTTP_API_URL/health"
```

**Debug**


| Symptom               | Check                                                                                          |
| --------------------- | ---------------------------------------------------------------------------------------------- |
| `git rev-parse` / `terraform/4_researcher` | Course test looked up App Runner. This repo reads SSM `/alex/http_api_url` after `sam deploy`. |
| Docker build fails    | Docker running; `--platform linux/amd64` is set in SAM metadata                                |
| Bedrock access denied | Model access in Bedrock console; `BEDROCK_REGION` / `researcher_model` in `samconfig` / tfvars |
| Ingest not called     | SSM `/alex/http_api_url` exists; Lambda can `ssm:GetParameter`; local `.env` has `ALEX_API_ENDPOINT` |
| Timeout               | Function timeout is 300s; first Playwright run is slow                                         |


Optional scheduler (EventBridge every 6 hours) is a SAM parameter `SchedulerEnabled=true`. It also looks up `/alex/http_api_url` at runtime (do not `!Sub` the HttpApi URL onto the scheduler).

---



# Part 5 — Aurora Serverless v2

Biggest cost (~$43/month at 0.5 ACU). Apply only when you will use it.

```bash
cd infra/terraform
terraform apply \
  -target=random_password.db_password \
  -target=random_id.suffix \
  -target=aws_secretsmanager_secret.db_credentials \
  -target=aws_secretsmanager_secret_version.db_credentials \
  -target=aws_db_subnet_group.aurora \
  -target=aws_security_group.aurora \
  -target=aws_rds_cluster.aurora \
  -target=aws_rds_cluster_instance.aurora \
  -target=aws_ssm_parameter.aurora_cluster_arn \
  -target=aws_ssm_parameter.aurora_secret_arn \
  -target=aws_ssm_parameter.database_name
```

Takes 10–15 minutes. Cluster status must be `available` and `EnableHttpEndpoint: true`.

```bash
aws rds describe-db-clusters --db-cluster-identifier alex-aurora-cluster \
  --query 'DBClusters[0].{Status:Status,Http:EnableHttpEndpoint}'
```

**Init schema**

```bash
cd backend/database
uv run test_data_api.py
uv run run_migrations.py
uv run seed_data.py
uv run verify_database.py
# optional sample user
uv run reset_db.py --with-test-data
```

SSM now has cluster + secret ARNs. `.env` can stay empty of ARNs for Lambdas (they read env injected by SAM). For local `uv run test_simple.py`, copy ARNs into `.env`:

```bash
terraform -chdir=infra/terraform output aurora_cluster_arn
terraform -chdir=infra/terraform output aurora_secret_arn
```

**Debug**


| Symptom                      | Check                                                |
| ---------------------------- | ---------------------------------------------------- |
| Cluster not found / Data API | Wait until `available`; `EnableHttpEndpoint` true    |
| Secret not found             | Output `aurora_secret_arn`; name has a random suffix |
| Migration fail               | `uv run reset_db.py` then migrate + seed again       |


---



# Part 6 — Agent orchestra

Five Lambdas: planner (SQS), tagger, reporter, charter, retirement. Shared layer for `alex-database` + common deps. Planner env `TAGGER_FUNCTION` etc. is set with SAM `!Ref`.

If you have not deployed SAM yet:

```bash
uv run --directory scripts export_requirements.py
cd infra/sam
sam build --use-container
sam deploy
```

**Local (in-process, needs Aurora + Bedrock in** `.env`**):**

```bash
cd backend/tagger && uv run test_simple.py
cd ../reporter && uv run test_simple.py
cd ../charter && uv run test_simple.py
cd ../retirement && uv run test_simple.py
cd ../planner && uv run test_simple.py   # MOCK_LAMBDAS=true
cd .. && uv run test_simple.py           # all five
```

**Lambda-runtime parity (Docker, no taint/deploy).** This does not re-test the agent logic. It runs the same zip inside the Lambda Python 3.12 image with the SAM layers mounted at `/opt/python`, which is what `uv run` on your Mac never does. `env.json` must contain the Aurora ARNs (empty strings override the template and crash `Database()` on import). `BEDROCK_REGION` must be `eu-west-1`.

```bash
cd infra/sam
sam local invoke TaggerFunction --event events/tagger.json --env-vars env.json
sam local invoke PlannerFunction --event events/planner-sqs.json --env-vars env.json
```

Planner SQS events are `{ "Records": [ { "body": "<job_id>" } ] }`, not a bare `{ "job_id": "..." }`.

**Deployed:**

```bash
cd backend/tagger && uv run test_full.py
# repeat reporter, charter, retirement, planner
cd ../.. && uv run test_full.py          # SQS path
```

**Debug**


| Symptom                         | Check                                                                            |
| ------------------------------- | -------------------------------------------------------------------------------- |
| `The provided model identifier is invalid` | `eu.amazon.nova-pro-v1:0` must be called with `BEDROCK_REGION` in the EU (here `eu-west-1`). `us-west-2` only accepts the `us.` profile. |
| LiteLLM region wrong            | SAM sets `AWS_REGION_NAME` to the Bedrock region                                 |
| Planner never runs              | SQS event source on planner; `aws sqs get-queue-attributes`                      |
| Messages in DLQ                 | Planner logs `/aws/lambda/alex-planner`; visibility is 910s > 900s timeout       |
| Empty results                   | Seed instruments; job has positions                                              |
| Rate limits                     | Nova Pro + tenacity retries; space requests                                      |


---



# Part 7 — Frontend and API

API Lambda (Mangum) is on HttpApi `ANY /api/{proxy+}`. Terraform CloudFront: S3 for the static site, `/api/*` to the HttpApi origin (from SSM after SAM).

```bash
# After sam deploy, SSM /alex/http_api_url exists
cd infra/terraform
terraform apply   # full apply: frontend bucket + CloudFront API origin + dashboards
```

Local app (hot reload, not SAM):

```bash
uv run --directory scripts run_local.py
```

- Frontend: [http://localhost:3000](http://localhost:3000)
- API: [http://localhost:8000/docs](http://localhost:8000/docs)

Production frontend:

```bash
uv run --directory scripts deploy.py
```

This builds Next.js, syncs `frontend/out` to the Terraform S3 bucket, and invalidates CloudFront.

**Debug**


| Symptom                | Check                                                                     |
| ---------------------- | ------------------------------------------------------------------------- |
| `Unexpected token '<'` / `<!DOCTYPE` | `/api/*` hit S3 and CloudFront returned `index.html`. Set `http_api_url` in `terraform.tfvars` to the HttpApi base (no `/ingest`) and apply so CloudFront has an `/api/*` behavior. |
| 401 from API           | Clerk keys in `frontend/.env.local` and SAM `ClerkJwksUrl`; sign in again |
| Analysis stays pending | SQS messages; planner trigger; Aurora not paused                          |
| CloudFront 403         | Bucket policy; wait for distribution; try incognito                       |
| Charts blank           | Charter job payload; browser console                                      |
| Double `/api/api`      | HttpApi path is `/api/{proxy+}` matching Mangum                           |


---



# Part 8 — Monitoring and observability

CloudWatch dashboards are in the same Terraform root (`monitoring.tf`). They apply with the full `terraform apply` in Part 7.

```bash
terraform -chdir=infra/terraform output dashboard_urls
```

LangFuse: set keys in `infra/sam/samconfig.toml` (or deploy parameters). Redeploy SAM. Watch:

```bash
cd backend
uv run watch_agents.py
```

Guardrails/explainability already live in the ported agent code (tagger rationale, planner structured logs). No extra Terraform.

---



# One-shot deploy (after you have walked the parts once)

```bash
# 1. Platform
cd infra/terraform && terraform init && terraform apply

# 2. Vector index
cd ../.. && uv run --directory scripts bootstrap_vectors.py

# 3. Lambdas
uv run --directory scripts export_requirements.py
cd infra/sam && sam build --use-container && sam deploy

# 4. CloudFront API origin + dashboards
cd ../terraform && terraform apply

# 5. Database schema
cd ../../backend/database
uv run run_migrations.py && uv run seed_data.py

# 6. Frontend
cd ../.. && uv run --directory scripts deploy.py
```



## Destroy this repo’s stack

```bash
uv run --directory scripts destroy.py
```

Empties the frontend bucket, `sam delete`, then `terraform destroy`. If SageMaker or ECR blocks destroy, delete those in the console and re-run.

## Two local modes


| Mode   | Command                                        | Use when                |
| ------ | ---------------------------------------------- | ----------------------- |
| App    | `uv run --directory scripts run_local.py`      | UI + FastAPI hot reload |
| Lambda | `sam local invoke ...` / `sam local start-api` | Runtime parity with AWS |


`sam local` does not mock Aurora or Bedrock. `test_simple.py` still needs those in `.env`.

## Cost

Aurora is the main bill. Destroy it when you are not working. Check AWS Billing as the course taught.