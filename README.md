# Streamlit Radar Demo

Standalone Streamlit advisor demo for Business Development Radar.

This app reads LLM1 enrichment and embedding data from a Neon Postgres/pgvector
database, retrieves evidence, and runs LLM2 synthesis on demand with OpenAI.
It intentionally does not include crawling, parsing, enrichment, embedding, Docker,
or scheduler code.

## Local Run

Create a local `.env` file from the example below, then run:

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud

Use this repository with:

```text
Main file path: app.py
```

Add secrets in Streamlit Cloud settings:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST/DB?sslmode=require"
OPEN_AI_API_KEY = "..."
OPENAI_MODEL = "gpt-4.1-mini"
APP_PASSWORD = "..."
```

You may also use separate Postgres settings instead of `DATABASE_URL`:

```toml
POSTGRES_HOST = "ep-example.region.aws.neon.tech"
POSTGRES_PORT = "5432"
POSTGRES_DB = "neondb"
POSTGRES_USER = "neondb_owner"
POSTGRES_PASSWORD = "..."
POSTGRES_SSLMODE = "require"
```

For Neon-backed worker jobs, use the direct Neon connection rather than a pooled
connection. This UI can use either direct or pooled connections, but direct is the
simplest demo setup.
