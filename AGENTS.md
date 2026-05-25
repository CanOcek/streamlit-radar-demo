# AGENTS.md

## First Step

Read `PROJECT_CONTEXT.md` before making changes. Treat source files as the final
authority when they disagree with docs.

This repository is the standalone Streamlit demo for Business Development Radar.
It connects to an already populated Postgres/pgvector database, retrieves LLM1
evidence, adds selected North Data context, and runs LLM2 synthesis.

The sibling repository `business-development-radar` owns crawling, PDF parsing,
LLM1 enrichment, embedding jobs, scheduling, Docker, and database population.

## Scope Notes

- Do not add crawler, Docling processing, scheduled worker, or ingestion code
  here unless explicitly requested.
- `postgres/init.sql` is reference-only in this repo.
- `.env` and `.streamlit/secrets.toml` may contain secrets. Do not print, quote,
  or commit them.
- Ignore `.venv`, `.idea`, `.git`, `__pycache__`, and local cache files unless
  the task specifically concerns them.

## Local Development

Run locally from the repository root:

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

Required runtime settings:

- `APP_PASSWORD`
- `DATABASE_URL` or separate Postgres settings
- `OPEN_AI_API_KEY` or `OPENAI_API_KEY`
- optional `OPENAI_MODEL`

## Coding Guidance

- Keep retrieval/query code inside `retrieval_core/`.
- Keep DB connection behavior centralized in `shared/db.py`.
- Keep environment/secrets lookup centralized in `shared/settings.py`.
- Keep UI rendering and session-state behavior in `app.py` unless an extraction
  meaningfully reduces complexity.
- Retrieval functions should return structured data, not Streamlit UI elements.
- Preserve graceful demo behavior for optional North Data context, but do not
  hide errors in core retrieval paths without reason.
- If a new package is required for a fresh install or Streamlit Cloud deploy,
  update `requirements.txt`.

## Verification

There is no formal test suite. For Python changes, run at least a syntax check
over touched files or the relevant package when practical. For docs-only
changes, state that no runtime tests were run.
