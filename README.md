# Streamlit Radar Demo

Standalone Streamlit advisor demo for the Business Development Radar prototype.

The Business Development Radar turns public company information into evidence-backed business-development signals for Plan.Net TechNest. This repository is the user-facing demo layer: it connects to an already populated Postgres/pgvector database, retrieves LLM1 evidence, adds selected North Data context, and runs LLM2 synthesis on demand.

The sibling repository `../busdevrad-collector` is the current source of truth
for crawling, PDF parsing, LLM1 enrichment, embedding jobs, scheduling, Docker,
the canonical schema, and database population. The older
`../business-development-radar` folder is not the active backend handoff target.

For report-derived product context, design rationale, source governance, evaluation results, and future-work notes, read `../docs/context/README.md`.

## What This Repo Does

- Provides the Streamlit interface for evidence retrieval and company-level synthesis.
- Lets users select companies, categories, signal strength, direction, confidence, and retrieval mode.
- Retrieves exact metadata matches and vector-search results from LLM1 enrichments and raw chunks.
- Hydrates raw content when requested.
- Retrieves supplemental North Data context for company structure, financials, patents, and trademarks.
- Runs LLM2 synthesis over retrieved LLM1 evidence.
- Presents results through layered tabs: overview/key takeaways, findings, evidence, company structure, financial metrics, and patents/trademarks.

## What This Repo Does Not Do

- It does not crawl websites.
- It does not parse PDFs with Docling.
- It does not run LLM1 enrichment jobs.
- It does not generate or backfill embeddings.
- It does not schedule backend processing jobs.
- It does not initialize or migrate a local database.

Keep ingestion and backend processing in `../busdevrad-collector` unless the
project direction explicitly changes.

## Product Model

The demo is designed around a layered decision-support workflow:

1. Select one or more companies and signal categories.
2. Retrieve stored LLM1 evidence from the database.
3. Optionally use vector queries to find semantically similar evidence.
4. Add selected North Data context.
5. Run LLM2 synthesis over the retrieved evidence set.
6. Review high-level takeaways, grouped findings, and the underlying evidence.

The main design principle is traceability. LLM2 findings should remain inspectable through the LLM1 records that support them, so users can validate the evidence before acting.

## Runtime Flow

```text
populated Postgres/pgvector database
  -> Streamlit company/category/filter controls
  -> retrieval_core exact or vector retrieval
  -> optional raw content hydration
  -> supplemental North Data context retrieval
  -> LLM_stage2 synthesis
  -> overview, findings, evidence, company context, financials, patents/trademarks
```

## Repository Map

```text
.
|-- app.py                         # Streamlit entry point
|-- ui_presets.py                  # optional company/category sidebar presets
|-- retrieval_core/                # exact retrieval, vector retrieval, consolidation, hydration
|-- LLM_stage2/                    # LLM2 schemas, prompt, formatting, runner
|-- shared/                        # settings, DB connection, embedding helper
|-- ui/assets/                     # branding assets
|-- postgres/init.sql              # reference schema copied from backend
|-- requirements.txt               # minimal runtime dependencies
|-- PROJECT_CONTEXT.md             # implementation source map and caveats
`-- .devcontainer/                 # development container configuration
```

Treat `PROJECT_CONTEXT.md` and source files as the implementation authority when this README is too high level.

## Requirements

- Python environment with the dependencies in `requirements.txt`.
- Streamlit.
- Access to a populated Postgres/pgvector database.
- OpenAI API key for query embeddings and LLM2 synthesis.
- `APP_PASSWORD` for the Streamlit login gate.

Required settings can come from `.env`, environment variables, or Streamlit secrets:

```text
APP_PASSWORD
DATABASE_URL
OPEN_AI_API_KEY
```

`OPENAI_API_KEY` can also be used for the API key. Instead of `DATABASE_URL`, separate Postgres settings are supported:

```text
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_DB
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_SSLMODE
```

Optional:

```text
OPENAI_MODEL
```

The LLM2 synthesis path defaults to `gpt-5.4`. Set `OPENAI_MODEL` in `.env`,
environment variables, or Streamlit secrets to intentionally use a different
Stage 2 model.

Do not commit `.env` or `.streamlit/secrets.toml`, and do not print secrets.

## Local Run

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the app:

```powershell
streamlit run app.py
```

The app requires a reachable populated database. Use `../busdevrad-collector`
to collect data, parse PDFs, run LLM1, and create embeddings before expecting
meaningful demo output.

## Streamlit Community Cloud

Use this repository with:

```text
Main file path: app.py
```

Add secrets in Streamlit Cloud settings:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DB?sslmode=require"
OPEN_AI_API_KEY = "..."
OPENAI_MODEL = "gpt-5.4"  # optional; default Stage 2 model
APP_PASSWORD = "..."
```

Separate Postgres settings can be used instead of `DATABASE_URL`:

```toml
POSTGRES_HOST = "ep-example.region.aws.neon.tech"
POSTGRES_PORT = "5432"
POSTGRES_DB = "neondb"
POSTGRES_USER = "neondb_owner"
POSTGRES_PASSWORD = "..."
POSTGRES_SSLMODE = "require"
```

For Neon-backed worker jobs, use the direct Neon connection rather than a pooled connection. This UI can use either direct or pooled connections, but direct is the simplest demo setup.

## UI Structure

The primary Streamlit dashboard is organized around the same layered evidence model as the overall project:

- Overview / Key Takeaways: executive summary, business-development outlook, direction, confidence, signal count, opportunities, risks, and suggested actions.
- Findings: grouped LLM2 findings with direction, confidence, categories, business relevance, and supporting signals.
- Evidence: LLM1 records with category, direction, confidence, source evidence, and PNTN relevance.
- Company Structure: North Data-derived related companies and persons.
- Financial Metrics: North Data-derived financial context.
- Patents & Trademarks: North Data-derived intellectual property context.

The North Data tabs provide factual company context. They should not be treated as the same thing as LLM-generated signal synthesis.

## Retrieval Modes

The demo supports:

- exact metadata retrieval from `source_enrichments`;
- enrichment vector retrieval over embedded LLM1 fields;
- raw chunk vector retrieval over webpage/PDF/North Data chunks;
- optional raw content hydration;
- supplemental North Data retrieval outside the main LLM1 evidence path.

Vector queries assume pgvector-compatible Postgres and 3072-dimensional embeddings from `text-embedding-3-large`.

## LLM2 Synthesis

`LLM_stage2` turns retrieved LLM1 rows into grouped business-development findings. If no signals are available, it returns a neutral low-confidence empty result without calling OpenAI.

The current Stage 2 implementation defaults to `gpt-5.4` and can be overridden
with `OPENAI_MODEL`. Review `LLM_stage2/prompts2.py` before major production
prompt changes.

## Known Caveats

- Prototype-stage demo.
- There is no comprehensive UI/integration test suite.
- `APP_PASSWORD` is required even for local use.
- `postgres/init.sql` is reference-only in this repository.
- The database must already be populated by `../busdevrad-collector`.
- Vector search and LLM2 require OpenAI API access, including access to the
  configured Stage 2 model, which defaults to `gpt-5.4`.
- North Data chunk retrieval requires the backend 20260708 SQL migration and
  `embed-northdata-chunks` or `process-northdata` to have run.
- Supplemental North Data context functions are intentionally resilient and may return empty results on errors.

## Development Guidance

- Read `PROJECT_CONTEXT.md` before changing implementation.
- Keep retrieval/query code inside `retrieval_core/`.
- Keep settings lookup centralized in `shared/settings.py`.
- Keep DB connection behavior centralized in `shared/db.py`.
- Keep UI rendering in `app.py` unless extraction clearly reduces complexity.
- Retrieval functions should return structured data, not Streamlit UI elements.
- If a new package is required for a fresh install or Streamlit Cloud deploy, update `requirements.txt`.

## Related Documentation

- `PROJECT_CONTEXT.md`: detailed implementation map and current caveats.
- `../busdevrad-collector/README.md`: backend pipeline and job orchestration.
- `../docs/context/README.md`: report-derived project context and design rationale.
