# How the agents work together

Alex has six agents. Five of them run when a user asks for a portfolio analysis. The researcher runs on its own schedule and never talks to the planner. They share two stores: Aurora (portfolios, jobs, reports) and S3 Vectors (market write-ups).

Every agent that calls a model uses Bedrock **Nova Pro** through LiteLLM (`BEDROCK_MODEL_ID`, for this deployment `eu.amazon.nova-pro-v1:0`).

## The two loops

```mermaid
flowchart TB
  subgraph analysis [User analysis]
    User[Signed-in user] --> Api[API Lambda<br/>POST /api/analyze]
    Api --> Aurora[(Aurora<br/>job row)]
    Api --> Sqs[SQS alex-analysis-jobs]
    Sqs --> Planner[Planner Lambda]
    Planner --> Tagger[Tagger Lambda]
    Tagger --> Aurora
    Planner --> Prices[Polygon prices]
    Prices --> Aurora
    Planner --> Reporter[Reporter Lambda]
    Planner --> Charter[Charter Lambda]
    Planner --> Retirement[Retirement Lambda]
    Reporter --> Vectors[(S3 Vectors<br/>financial-research)]
    Reporter --> Aurora
    Charter --> Aurora
    Retirement --> Aurora
    User --> Jobs[GET /api/jobs]
    Jobs --> Aurora
  end

  subgraph research [Background research]
    Clock[Scheduler Lambda<br/>every 6 hours] --> Researcher[Researcher Lambda]
    Researcher --> Web[Playwright browser]
    Researcher --> Ingest[Ingest Lambda<br/>POST /ingest]
    Ingest --> Sage[SageMaker embeddings]
    Ingest --> Vectors
  end
```

The analysis loop is request/response through SQS, so the browser does not wait for the whole run. The API creates a job, returns the job id, and the frontend polls `/api/jobs`. The research loop fills the knowledge base that the reporter searches later.

## What each agent does

| Agent | Lambda | Who starts it | What it does | What it writes |
| --- | --- | --- | --- | --- |
| Planner | `alex-planner` | SQS | Decides which specialists to call | Job status: `running`, `completed`, or `failed` |
| Tagger | `alex-tagger` | Planner, before the planner model runs | Classifies a symbol that has no allocations yet | Instrument rows in Aurora |
| Reporter | `alex-reporter` | Planner tool `invoke_reporter` | Writes the portfolio narrative | Report on the job, after reading S3 Vectors |
| Charter | `alex-charter` | Planner tool `invoke_charter` | Builds chart JSON for the UI | Chart payload on the job |
| Retirement | `alex-retirement` | Planner tool `invoke_retirement` | Projects retirement income | Projection payload on the job |
| Researcher | `alex-researcher` | Scheduler, or `POST /research` | Browses the web and writes a market note | Calls ingest, which stores a vector |

Ingest is not an agent. It embeds text with SageMaker (`all-MiniLM-L6-v2`, 384 dimensions) and stores it in the `financial-research` index. The researcher is the only agent that calls it.

## One analysis, step by step

```mermaid
sequenceDiagram
  participant U as Browser
  participant A as API Lambda
  participant Q as SQS
  participant P as Planner
  participant T as Tagger
  participant R as Reporter
  participant C as Charter
  participant Ret as Retirement
  participant DB as Aurora
  participant V as S3 Vectors

  U->>A: POST /api/analyze
  A->>DB: Insert job
  A->>Q: Message body is the job id
  A-->>U: job id
  Q->>P: Invoke planner
  P->>DB: status = running
  P->>DB: Find symbols with no allocations
  opt Some symbols are unclassified
    P->>T: instruments list
    T->>DB: Save asset class, region, sector
  end
  P->>DB: Refresh prices
  P->>P: Nova Pro chooses tools
  P->>R: invoke_reporter if there are positions
  R->>V: Search notes for those symbols
  R->>DB: Save the report
  P->>C: invoke_charter if there are at least 2 positions
  C->>DB: Save charts
  P->>Ret: invoke_retirement if the user has retirement goals
  Ret->>DB: Save the projection
  P->>DB: status = completed
  U->>A: GET /api/jobs/id
  A->>DB: Read job
  A-->>U: Report, charts, projection
```

Tagger is not a tool the planner model can call. The handler runs it in code first, and only when a held symbol has no allocation data. After that, the planner model is allowed only three tools: `invoke_reporter`, `invoke_charter`, and `invoke_retirement`. Each tool is a synchronous `lambda:Invoke` of that function. The instructions tell the model to call them in that order, then answer "Done".

If Nova Pro rate-limits the planner, the handler retries with backoff. A failure marks the job `failed` and the message can land on the dead-letter queue after three receives.

## How the researcher stays separate

```mermaid
sequenceDiagram
  participant S as Scheduler
  participant R as Researcher
  participant B as Playwright
  participant I as Ingest
  participant E as SageMaker
  participant V as S3 Vectors
  participant Rep as Reporter

  Note over S,V: Not part of a user job
  S->>R: POST /research every 6 hours
  R->>B: Open finance pages
  R->>I: ingest_financial_document
  I->>E: Embed the text
  I->>V: Put vector
  Note over Rep,V: Later, during a user analysis
  Rep->>V: Query vectors for the portfolio symbols
```

The planner never invokes the researcher. The reporter is the agent that reads what the researcher stored. That is why an analysis can still finish when the researcher has not run yet: the reporter simply has less market context.

The scheduler is off unless the SAM parameter `SchedulerEnabled` is `true`. A person can still start one research run with `POST /research`.
