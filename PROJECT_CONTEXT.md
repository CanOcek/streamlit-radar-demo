# Streamlit Radar Demo Project Context

This file is a compact source map for future Codex sessions. It was rebuilt from the repository contents on 2026-05-13. Treat source files as the final authority when changing behavior.

## What This Repository Is

This checkout is a standalone Streamlit advisor demo for Business Development Radar. It does not crawl, parse, enrich, embed, schedule jobs, run Docker services, or initialize a local database. Instead, it connects to an already-populated Postgres/pgvector database, retrieves LLM1 evidence, and optionally runs an OpenAI-powered LLM2 synthesis over that evidence.

The original/full Business Development Radar repo appears to contain the crawler, PDF parsing, LLM1 enrichment, embedding, and scheduling pipeline. This trimmed project keeps only the runtime pieces needed for demo retrieval and LLM2 analysis:

```text
populated Postgres/pgvector database
  -> Streamlit scope/filter controls
  -> retrieval_core exact or vector retrieval
  -> optional raw content hydration
  -> LLM_stage2 signal formatting and OpenAI synthesis
  -> Streamlit evidence, prompt preview, and JSON/result views
```

`postgres/init.sql` is included here to document the expected database shape. It is not wired into an initializer in this repository.

## Repository Map

```text
.
├── app.py                         # Streamlit app entry point
├── README.md                      # local/Streamlit Cloud run notes
├── PROJECT_CONTEXT.md             # this file
├── requirements.txt               # minimal demo dependencies
├── .env.example                   # local env template
├── .devcontainer/devcontainer.json# Codespaces/devcontainer Streamlit setup
├── postgres/init.sql              # reference schema from the main system
├── shared/
│   ├── settings.py                # .env + Streamlit secrets lookup
│   ├── db.py                      # psycopg2 Postgres connection helper
│   └── embeddings.py              # OpenAI embedding helper
├── retrieval_core/
│   ├── retrieval_models.py        # filter/query/options dataclasses
│   ├── retrieval_orchestrator.py  # exact/vector retrieval coordinator
│   ├── signal_retrieval.py        # metadata-only source_enrichments query
│   ├── enrichment_vector_retrieval.py
│   ├── chunk_vector_retrieval.py
│   ├── result_consolidation.py    # dedupe/ranking of repeated hits
│   ├── content_hydration.py       # optional raw webpage/PDF segment fetch
│   └── retrieval_utils.py         # defaults, DB alias, console printer
└── LLM_stage2/
    ├── schemas.py                 # Stage1/Stage2 dataclasses
    ├── db_signal_adapter.py       # retrieval row -> Stage1Signal
    ├── formatter.py               # scope-aware signal prompt formatting
    ├── prompts2.py                # LLM2 system/user prompts
    └── stage2_runner.py           # retrieval wrapper and OpenAI call
```

Generated/local state can be present: `.git/`, `.idea/`, `.venv/`, `__pycache__/`, local `.env`, and editor or cache files. Do not treat those as authored project logic. Do not print or commit `.env`.

## Runtime And Configuration

Local run:

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit Community Cloud uses:

```text
Main file path: app.py
```

Required settings can come from `.env`, environment variables, or Streamlit secrets:

- `APP_PASSWORD`: required by the app login gate.
- `OPEN_AI_API_KEY` or `OPENAI_API_KEY`: required for embeddings and LLM2.
- `OPENAI_MODEL`: optional, defaults to `gpt-4.1-mini` in `LLM_stage2/stage2_runner.py`.
- `DATABASE_URL`: preferred single Postgres connection string.
- Or separate Postgres settings: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SSLMODE`.

`shared/settings.py` loads `.env` from the repository root and then falls back to `st.secrets`. `shared/db.py` uses `DATABASE_URL` if present; otherwise it builds a `psycopg2.connect(...)` call from the separate Postgres settings and defaults to `POSTGRES_DB=neondb`, `POSTGRES_PORT=5432`, and `POSTGRES_SSLMODE=require`.

`requirements.txt` is intentionally minimal:

```text
streamlit
openai
psycopg2-binary
python-dotenv
```

The devcontainer installs requirements and starts:

```text
streamlit run app.py --server.enableCORS false --server.enableXsrfProtection false
```

on forwarded port `8501`.

## Streamlit App

`app.py` is the only UI entry point. It inserts the repository root into `sys.path`, imports `retrieval_core` and `LLM_stage2`, configures a wide Streamlit page, and then runs `main()`.

Primary behavior:

- Requires `APP_PASSWORD`; unauthenticated users see only a password form.
- Loads live company/category/page-type options from Postgres with `@st.cache_data(ttl=60)`.
- Lets the user choose companies and categories, plus exact-name extra companies.
- Supports three retrieval strategies:
  - exact metadata fetch, with no embedding call
  - single vector query
  - multi-query vector search
- Supports filters for source type, page type, bucket, relevance, direction, confidence, signal strength, and secondary categories.
- For vector retrieval, the user can search selected LLM1 enrichment fields and optionally chunk embeddings.
- Stores retrieved rows and converted `Stage1Signal` objects in `st.session_state`.
- Runs LLM2 only after evidence has been retrieved and a non-empty scope is selected.
- Renders overview, grouped findings, evidence rows, LLM2 input prompt preview, and raw JSON.

The app currently hard-codes category labels:

- `Financials`
- `News / Products`
- `Partnerships / Acquisitions`
- `Hiring`
- `Innovative Themes`
- `Legal & C-Level Updates`

It also merges these with live categories from `source_enrichments`.

## Retrieval Core

The package export surface is:

- `RetrievalFilters`
- `RetrievalOptions`
- `VectorQuerySpec`
- `retrieve_signals(...)`
- `retrieve_for_llm2(...)`

Defaults in `retrieval_core/retrieval_utils.py`:

- enrichment fields: `all`, `short_summary`, `evidence`, `why_it_matters_for_pntn`, `possible_business_suggestion`
- buckets: `main`, `weak`
- source types: `webpages`, `pdfs`
- chunk scopes: `webpage_chunk`, `pdf_chunk`

`retrieve_signals(...)` chooses the path:

- No active vector query: call `fetch_enrichment_signals(...)`, limit the unranked rows, and optionally hydrate raw content.
- Active vector query: embed each query with `shared.embeddings.embed_text(...)`, search requested enrichment embeddings and/or chunk embeddings, consolidate duplicate parent hits, then optionally hydrate raw content.

`signal_retrieval.py` queries `source_enrichments` joined to `webpages`, `pdf_segments`, and `pdfs`. It returns a normalized row shape with source metadata, LLM1 fields, ranking placeholders, and retrieval provenance.

`enrichment_vector_retrieval.py` searches `enrichment_embeddings` by cosine distance using pgvector operators, filters through the joined `source_enrichments` metadata, groups per enrichment row, and aggregates matched fields into JSON.

`chunk_vector_retrieval.py` searches `chunk_embeddings` for webpage and PDF chunks. It can operate in:

- `normal` mode, joining to `source_enrichments`
- `noise` mode, joining to `source_enrichments_noise`

Chunk search can require an enrichment/noise row or allow raw chunk hits without enrichment, depending on `VectorQuerySpec.require_chunk_enrichment`.

`result_consolidation.py` dedupes hits by parent:

- PDF segment hits key on `pdf_segment_id`.
- Other hits key on `source_id`.
- The best distance wins, missing values are filled from duplicates, matched fields are merged, and final ordering is by vector distance with timestamp fallback.

`content_hydration.py` can add `raw_content` from `webpages.raw_text` or `pdf_segments.segment_text` when `RetrievalOptions.include_raw_content=True`.

Important retrieval limitation: this demo retrieval path handles `webpages` and `pdfs`. North Data tables are present in the schema reference but are not integrated into the active retrieval code.

## LLM2 Synthesis

`LLM_stage2` turns retrieved LLM1 rows into grouped business-development findings.

Key files:

- `db_signal_adapter.py`: converts retrieval rows to `Stage1Signal`, HTML-unescaping categories.
- `formatter.py`: formats up to 40 signals differently by scope mode.
- `prompts2.py`: contains the system prompt and JSON-response user prompt template.
- `stage2_runner.py`: runs retrieval when requested, calls OpenAI Chat Completions, parses JSON, and adds `_meta`.
- `schemas.py`: dataclasses for prompt/result structures.

Scope mode is inferred by selected company/category counts:

- one company + one category: `company_category`
- one company + multiple categories: `company_multi_category`
- multiple companies + one category: `multi_company_category`
- multiple companies + multiple categories: `multi_company_multi_category`

The OpenAI call uses:

```python
response_format={"type": "json_object"}
temperature=0
model=get_setting("OPENAI_MODEL", "gpt-4.1-mini")
```

If no signals are available, `_empty_stage2_result(...)` returns a neutral, low-confidence empty result without calling OpenAI.

## Database Shape Expected By The Demo

`postgres/init.sql` enables `vector` and `pg_trgm`, then defines the schema expected from the main pipeline. The demo reads from a subset of these tables.

Core source tables:

- `all_sources`: global source registry. `source_type` allows webpages, PDFs, and several North Data types.
- `webpages`: normalized/raw URL, company, page type, title, text, date, crawl metadata, content hashes, and timestamps.
- `pdfs`: PDF URL, company, title/date/language, parent URL, optional stored HTML, and crawl metadata.
- `pdf_segments`: segment-level PDF text and headings.
- `pdf_chunks`: chunk-level PDF text linked to segments.
- `webpage_chunks`: raw webpage chunks.

LLM1 and embedding tables used by retrieval:

- `source_enrichments`: useful LLM1 outputs for source-level webpage rows and PDF-segment rows.
- `source_enrichments_noise`: rejected/noise LLM1 outputs.
- `enrichment_embeddings`: embeddings for LLM1 fields.
- `chunk_embeddings`: embeddings for raw webpage/PDF chunks.

North Data tables present but not used by the demo retrieval path:

- `northdata_publications`
- `publication_topics`
- `northdata_companies`
- `northdata_events`
- `northdata_related_companies`
- `northdata_related_persons`
- `northdata_sheets`

Indexes include HNSW vector indexes over `embedding::halfvec(3072)`, source/filter indexes, GIN over `source_enrichments.secondary_categories`, and uniqueness constraints that allow only one useful/noise enrichment per source or PDF segment.

## Inferred Main-Repo Responsibilities

The old context file described the original repository. From that context and the schema, this demo expects the main system to have already handled:

- collecting webpages and PDFs from configured company sources
- storing source rows in `all_sources`, `webpages`, and `pdfs`
- parsing PDFs into `pdf_segments` and `pdf_chunks`
- chunking webpages into `webpage_chunks`
- running LLM1 enrichment into `source_enrichments` or `source_enrichments_noise`
- embedding enrichment fields into `enrichment_embeddings`
- embedding raw chunks into `chunk_embeddings`
- optionally collecting North Data rows, though they are not surfaced here

None of that ingestion or processing code is present in this checkout.

## Known Caveats

- `postgres/init.sql` is reference-only in this repo; there is no Compose file or migration runner here.
- No formal test suite exists.
- Retrieval SQL assumes the schema in `postgres/init.sql` and pgvector-compatible Postgres.
- Vector retrieval calls OpenAI embeddings at query time, so it requires network/API access and an API key.
- LLM2 calls OpenAI Chat Completions, so synthesis also requires network/API access and an API key.
- `APP_PASSWORD` is required even for local Streamlit use.
- The app exposes only `webpages` and `pdfs` source types in the UI.
- Noise chunk retrieval is disabled when category filters are active in `retrieval_orchestrator.py`.
- `stage2_runner.py` still inserts a `scripts` directory into `sys.path`, a carryover from the original repo layout; this checkout has no `scripts/` directory.
- The LLM2 prompt contains some source-specific guardrail wording, including a Lufthansa-specific example, so review it before generalizing the demo.
- `.env` may contain secrets and should not be read aloud, printed, or committed.
