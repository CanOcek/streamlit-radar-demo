from typing import Any

from psycopg2.extras import RealDictCursor

try:
    from .retrieval_utils import get_db_connection
except ImportError:
    from retrieval_utils import get_db_connection


def hydrate_raw_content(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows

    webpage_ids = sorted(
        {
            row["source_id"]
            for row in rows
            if row.get("source_type") == "webpages"
            and row.get("source_id") is not None
        }
    )
    pdf_segment_ids = sorted(
        {
            row["pdf_segment_id"]
            for row in rows
            if row.get("content_scope") == "pdf_segment"
            and row.get("pdf_segment_id") is not None
        }
    )
    northdata_publication_ids = sorted(
        {
            row["source_id"]
            for row in rows
            if row.get("source_type") == "northdata_publications"
            and row.get("source_id") is not None
        }
    )
    northdata_event_ids = sorted(
        {
            row["source_id"]
            for row in rows
            if row.get("source_type") == "northdata_events"
            and row.get("source_id") is not None
        }
    )

    webpage_content = _fetch_webpage_content(webpage_ids)
    pdf_segment_content = _fetch_pdf_segment_content(pdf_segment_ids)
    northdata_publication_content = _fetch_northdata_publication_content(
        northdata_publication_ids
    )
    northdata_event_content = _fetch_northdata_event_content(northdata_event_ids)

    hydrated_rows = []
    for row in rows:
        hydrated = dict(row)
        if row.get("source_type") == "webpages":
            hydrated["raw_content"] = webpage_content.get(row.get("source_id"))
        elif row.get("content_scope") == "pdf_segment":
            hydrated["raw_content"] = pdf_segment_content.get(row.get("pdf_segment_id"))
        elif row.get("source_type") == "northdata_publications":
            hydrated["raw_content"] = northdata_publication_content.get(
                row.get("source_id")
            )
        elif row.get("source_type") == "northdata_events":
            hydrated["raw_content"] = northdata_event_content.get(row.get("source_id"))
        else:
            hydrated["raw_content"] = None
        hydrated_rows.append(hydrated)

    return hydrated_rows


def _fetch_webpage_content(source_ids: list[int]) -> dict[int, str]:
    if not source_ids:
        return {}

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, raw_text
                FROM webpages
                WHERE id = ANY(%s)
                """,
                (source_ids,),
            )
            return {row["id"]: row.get("raw_text") or "" for row in cur.fetchall()}
    finally:
        conn.close()


def _fetch_pdf_segment_content(segment_ids: list[int]) -> dict[int, str]:
    if not segment_ids:
        return {}

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, segment_text
                FROM pdf_segments
                WHERE id = ANY(%s)
                """,
                (segment_ids,),
            )
            return {row["id"]: row.get("segment_text") or "" for row in cur.fetchall()}
    finally:
        conn.close()


def _fetch_northdata_publication_content(source_ids: list[int]) -> dict[int, str]:
    if not source_ids:
        return {}

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, text
                FROM northdata_publications
                WHERE id = ANY(%s)
                """,
                (source_ids,),
            )
            return {row["id"]: row.get("text") or "" for row in cur.fetchall()}
    finally:
        conn.close()


def _fetch_northdata_event_content(source_ids: list[int]) -> dict[int, str]:
    if not source_ids:
        return {}

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, description
                FROM northdata_events
                WHERE id = ANY(%s)
                """,
                (source_ids,),
            )
            return {row["id"]: row.get("description") or "" for row in cur.fetchall()}
    finally:
        conn.close()
