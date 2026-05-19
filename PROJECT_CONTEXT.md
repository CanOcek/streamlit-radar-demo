# Streamlit Radar Demo Project Context

This file is the current source map for future work on this repository. It was
rebuilt from the repository contents on 2026-05-19. Treat source files as the
final authority when behavior and documentation disagree.

## What This Repository Is

`streamlit-radar-demo` is the standalone Streamlit advisor demo for Business
Development Radar. It connects to an already populated Postgres/pgvector
database, retrieves LLM1 evidence, adds selected North Data context, and runs
OpenAI-powered LLM2 synthesis on demand.

This repository intentionally does not crawl, parse PDFs, enrich sources, embed
documents, schedule jobs, or initialize a local database. Those responsibilities
belong to the sibling backend repository `business-development-radar`.

The runtime flow is:

```text
populated Postgres/pgvector database
  -> Streamlit company/category/filter controls
  -> retrieval_core exact or vector retrieval
  -> optional raw content hydration
  -> supplemental North Data context retrieval
  -> LLM_stage2 synthesis
  -> Streamlit evidence, findings, company structure, financials, patents/trademarks
```

## Repository Map

```text
.
├── app.py                         # Streamlit entry point
├── ui_presets.py                  # optional company/category sidebar presets
├── requirements.txt               # minimal runtime dependencies
├── README.md                      # short run/deploy notes
├── PROJECT_CONTEXT.md             # this source map
├── .env.example                   # local env template
├── .devcontainer/devcontainer.json
├── postgres/init.sql              # reference schema copied from backend
├── shared/
│   ├── settings.py                # env + Streamlit secrets lookup
│   ├── db.py                      # psycopg2 connection helper
│   └── embeddings.py              # OpenAI embedding helper
├── retrieval_core/
│   ├── retrieval_models.py        # dataclasses for filters/options/results/context
│   ├── retrieval_orchestrator.py  # exact/vector retrieval coordinator
│   ├── signal_retrieval.py        # metadata-only source_enrichments retrieval
│   ├── enrichment_vector_retrieval.py
│   ├── chunk_vector_retrieval.py
│   ├── result_consolidation.py
│   ├── content_hydration.py
│   ├── related_retrieval.py       # North Data related companies/persons
│   ├── financial_retrieval.py     # North Data financials
│   └── patents_trademarks_retrieval.py
├── LLM_stage2/
│   ├── schemas.py
│   ├── db_signal_adapter.py
│   ├── formatter.py
│   ├── prompts2.py
│   └── stage2_runner.py
└── ui/assets/
    ├── pntn_logo.png
    └── tum_logo.png
```

Generated/local state can exist: `.git/`, `.idea/`, `.venv/`, `__pycache__/`,
local `.env`, and Streamlit secrets. Do not print or commit secrets.

## Runtime And Configuration

Local run:

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit Community Cloud:

```text
Main file path: app.py
```

Required settings can come from `.env`, environment variables, or Streamlit
secrets:

- `APP_PASSWORD`: required by the login gate.
- `OPEN_AI_API_KEY` or `OPENAI_API_KEY`: required for query embeddings and LLM2.
- `OPENAI_MODEL`: optional; defaults to `gpt-4.1-mini`.
- `DATABASE_URL`: preferred single Postgres connection string.
- Or separate Postgres settings: `POSTGRES_HOST`, `POSTGRES_PORT`,
  `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SSLMODE`.

`shared/settings.py` loads `.env` from the repository root and falls back to
`st.secrets`. `shared/db.py` uses `DATABASE_URL` if set; otherwise it builds a
connection from separate Postgres settings and defaults to `POSTGRES_DB=neondb`,
`POSTGRES_PORT=5432`, and `POSTGRES_SSLMODE=require`.

`requirements.txt` is intentionally minimal:

```text
streamlit
openai
psycopg2-binary
python-dotenv
```

The devcontainer installs requirements and launches Streamlit on port `8501`.

## Streamlit App

`app.py` is the only UI entry point. It configures a wide page, loads branding
assets, requires `APP_PASSWORD`, and runs the main workspace.

Main UI behavior:

- password gate before showing the app
- sidebar branding with PNTN and TUM logos
- company/category selection from `ui_presets.py` or live DB values
- retrieval filters for signal strength, direction, confidence, and secondary
  category inclusion
- optional raw content hydration
- exact metadata retrieval, single vector query, or multi-query vector search
- evidence limit and minimum vector similarity controls
- session-state storage for retrieved rows, Stage1 signals, North Data context,
  and LLM2 result
- tabs for overview, findings, evidence, company structure, financials, and
  patents/trademarks

`ui_presets.py` currently restricts visible companies to:

- Epson
- Olympus
- Raiffeisen
- Stiebel Eltron

Preset categories:

- Financials
- News / Products
- Partnerships / Acquisitions
- Hiring
- Innovative Themes
- Legal & C-Level Updates

If a preset list is empty, the app falls back to database-loaded values.

## Retrieval Core

The package export surface in `retrieval_core/__init__.py` includes:

- `RetrievalFilters`
- `RetrievalOptions`
- `VectorQuerySpec`
- `retrieve_signals(...)`
- `retrieve_for_llm2(...)`
- `retrieve_related_context(...)`
- `retrieve_financial_context(...)`
- `retrieve_patent_context(...)`
- `retrieve_trademark_context(...)`

`retrieval_orchestrator.py` chooses between exact metadata retrieval and vector
retrieval:

- no active vector query -> `fetch_enrichment_signals(...)`
- vector query -> embed query with `shared.embeddings.embed_text(...)`
- then search enrichment embeddings and/or raw chunk embeddings
- filter by minimum similarity
- consolidate duplicate parent hits
- optionally hydrate raw content

Defaults in `retrieval_core/retrieval_utils.py`:

- enrichment fields: `all`, `short_summary`, `evidence`,
  `why_it_matters_for_pntn`, `possible_business_suggestion`
- buckets: `main`, `weak`
- source types: `webpages`, `pdfs`
- chunk scopes: `webpage_chunk`, `pdf_chunk`

The UI overrides source types to:

- `webpages`
- `pdfs`
- `northdata_publications`
- `northdata_events`

## Exact And Enrichment Retrieval

`signal_retrieval.py` retrieves rows from `source_enrichments` joined to:

- `webpages`
- `pdf_segments` and `pdfs`
- `northdata_publications`
- `northdata_events`

It normalizes row shape across these sources with fields such as company,
page type, title, date, URL, enrichment id, bucket, category, evidence,
suggestion, retrieval source, and sort timestamp.

`enrichment_vector_retrieval.py` searches `enrichment_embeddings` by pgvector
cosine distance and joins through the same source families as exact retrieval:
webpages, PDFs, North Data publications, and North Data events.

## Chunk Retrieval

`chunk_vector_retrieval.py` searches `chunk_embeddings` for:

- `webpage_chunk`
- `pdf_chunk`

It supports:

- normal mode joined to `source_enrichments`
- noise mode joined to `source_enrichments_noise`
- optional `require_enrichment`
- filters for company, page type, bucket, signal strength, direction,
  confidence, category, secondary category, and source type

Chunk retrieval currently handles webpage/PDF chunks, not North Data chunks.
Noise chunk retrieval is only triggered when category filters are not active.

## Result Consolidation And Hydration

`result_consolidation.py` dedupes hits by parent:

- PDF segment hits key on `pdf_segment_id`
- other hits key on `source_id`

The best distance wins, missing values are filled from duplicate hits, matched
fields are merged, and final ranking uses vector distance with timestamp
fallback.

`content_hydration.py` can attach raw content from:

- `webpages.raw_text`
- `pdf_segments.segment_text`
- `northdata_publications.text`
- `northdata_events.description`

## Supplemental North Data Context

The app retrieves extra context outside the main LLM1 evidence path:

- `related_retrieval.py`: related companies and related persons from North Data.
- `financial_retrieval.py`: financials JSON from `northdata_companies`.
- `patents_trademarks_retrieval.py`: Patent and Trademark events from
  `northdata_events`.

These functions return empty contexts on errors so the demo remains usable if a
table or query fails.

## LLM2 Synthesis

`LLM_stage2` turns retrieved LLM1 rows into grouped business-development
findings.

Important files:

- `db_signal_adapter.py`: converts retrieval rows to `Stage1Signal`, including
  HTML-unescaping categories.
- `formatter.py`: formats up to 40 signals differently by scope mode.
- `prompts2.py`: system prompt and JSON-response user prompt template.
- `stage2_runner.py`: retrieves when requested, calls OpenAI Chat Completions,
  parses JSON, and adds `_meta`.
- `schemas.py`: dataclasses for Stage1 and Stage2 structures.

Scope mode is inferred from selected company/category counts:

- one company + one category -> `company_category`
- one company + multiple categories -> `company_multi_category`
- multiple companies + one category -> `multi_company_category`
- multiple companies + multiple categories -> `multi_company_multi_category`

The OpenAI call uses:

```python
response_format={"type": "json_object"}
temperature=0
model=get_setting("OPENAI_MODEL", "gpt-4.1-mini")
```

If no signals are available, LLM2 returns a neutral low-confidence empty result
without calling OpenAI.

The LLM2 prompt still contains some source-specific guardrail wording, including
Lufthansa examples. Review it before presenting the demo as fully generalized.

## Database Shape Expected

`postgres/init.sql` is a reference schema copied from the backend project. It is
not wired to Compose or a migration runner in this repository.

The demo expects these tables to be populated by the backend:

- `all_sources`
- `webpages`
- `pdfs`
- `pdf_segments`
- `pdf_chunks`
- `webpage_chunks`
- `source_enrichments`
- `source_enrichments_noise`
- `enrichment_embeddings`
- `chunk_embeddings`
- selected North Data tables, especially `northdata_publications`,
  `northdata_events`, `northdata_companies`, `northdata_related_companies`, and
  `northdata_related_persons`

Vector queries assume pgvector-compatible Postgres and 3072-dimensional
embeddings from `text-embedding-3-large`.

## Relationship To Backend Repo

The sibling `business-development-radar` repository is responsible for:

- crawling configured sources
- storing raw webpages, PDFs, and North Data
- parsing PDFs into segments/chunks
- chunking webpages
- running LLM1 enrichment
- creating enrichment and raw chunk embeddings
- scheduling crawl/process jobs

This demo should stay focused on retrieval, synthesis, and presentation. Do not
add crawler, Docling, embedding-job, Docker scheduler, or ingestion code here
unless the project direction explicitly changes.

## Known Caveats

- No formal test suite exists.
- `APP_PASSWORD` is required even for local use.
- Vector search and LLM2 require network/API access and an OpenAI key.
- `postgres/init.sql` is reference-only in this repo.
- Chunk retrieval does not cover North Data chunks.
- Supplemental North Data context functions swallow exceptions and return empty
  results, which is good for demo resilience but can hide DB issues.
- `stage2_runner.py` still adds a non-existent `scripts/` directory to
  `sys.path`; it is harmless but a carryover from the backend layout.
- The prompt has some source-specific examples that should be generalized before
  final reporting.
- `.env` and Streamlit secrets may contain credentials; never print them.

## Development Guidance

- Keep this repository deployment-friendly and small.
- Prefer `shared.settings.get_setting(...)` for config access.
- Prefer `shared.db.get_db_connection(...)` for DB access.
- Keep retrieval functions returning structured data; keep UI rendering in
  `app.py`.
- Do not copy backend ingestion responsibilities into this repo.
- If a new package is required for a fresh install, update `requirements.txt`.
