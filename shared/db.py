from __future__ import annotations

import psycopg2

from .settings import get_setting


def get_db_connection():
    database_url = get_setting("DATABASE_URL")
    if database_url:
        if "sslmode=" not in database_url:
            separator = "&" if "?" in database_url else "?"
            database_url = f"{database_url}{separator}sslmode=require"
        return psycopg2.connect(database_url)

    return psycopg2.connect(
        host=get_setting("POSTGRES_HOST", "localhost"),
        port=get_setting("POSTGRES_PORT", "5432"),
        dbname=get_setting("POSTGRES_DB", "neondb"),
        user=get_setting("POSTGRES_USER"),
        password=get_setting("POSTGRES_PASSWORD"),
        sslmode=get_setting("POSTGRES_SSLMODE", "require"),
        gssencmode="disable",
    )
