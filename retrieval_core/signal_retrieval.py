from typing import Any

from psycopg2.extras import RealDictCursor

try:
    from .retrieval_models import RetrievalFilters
    from .retrieval_utils import get_db_connection, list_or_none
except ImportError:
    from retrieval_models import RetrievalFilters
    from retrieval_utils import get_db_connection, list_or_none


def fetch_enrichment_signals(
    filters: RetrievalFilters | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    filters = filters or RetrievalFilters()

    sql = """
    SELECT
        se.source_id,
        a.source_type,
        se.content_scope,
        se.pdf_segment_id,
        ps.segment_index,
        ps.heading,
        ps.heading_path,

        NULL::bigint AS webpage_chunk_id,
        NULL::bigint AS pdf_chunk_id,
        NULL::int AS chunk_index,

        COALESCE(w.company, p.company, np.company_name, ne.company_name) AS company,
        COALESCE(
            w.page_type,
            CASE
                WHEN np.id IS NOT NULL THEN COALESCE(NULLIF(np.source_name, ''), 'northdata_publication')
                WHEN ne.id IS NOT NULL THEN COALESCE(NULLIF(ne.type, ''), 'northdata_event')
            END,
            'pdf_segment'
        ) AS page_type,
        COALESCE(w.title, ps.heading, p.title, np.title, ne.description) AS title,
        COALESCE(w.date, p.date, np.date, ne.date) AS date,
        COALESCE(w.raw_url, p.pdf_link, np.publication_url, ne.company_url) AS raw_url,

        se.id AS enrichment_id,
        NULL::bigint AS noise_enrichment_id,
        se.bucket,
        se.category,
        se.secondary_categories,
        se.signal_strength,
        se.direction,
        se.confidence,

        se.short_summary,
        se.evidence,
        se.why_it_matters_for_pntn,
        se.possible_business_suggestion,
        NULL::text AS noise_result,
        NULL::text AS noise_reason,

        NULL::double precision AS best_distance,
        NULL::double precision AS best_similarity,
        '[]'::jsonb AS matched_fields,

        'enrichment'::text AS hit_type,
        'source_enrichments'::text AS retrieval_source,
        'normal'::text AS enrichment_mode,
        TRUE AS has_enrichment,
        CASE
            WHEN a.source_type = 'webpages' THEN w.updated_at
            ELSE COALESCE(ps.created_at, p.created_at, np.created_at, ne.created_at, se.created_at)
        END AS sort_timestamp

    FROM source_enrichments se
    JOIN all_sources a ON a.id = se.source_id
    LEFT JOIN webpages w
        ON se.content_scope = 'source'
        AND a.source_type = 'webpages'
        AND w.id = se.source_id
    LEFT JOIN pdf_segments ps
        ON se.content_scope = 'pdf_segment'
        AND a.source_type = 'pdfs'
        AND ps.id = se.pdf_segment_id
    LEFT JOIN pdfs p
        ON p.id = ps.pdf_id
    LEFT JOIN northdata_publications np
        ON se.content_scope = 'source'
        AND a.source_type = 'northdata_publications'
        AND np.id = se.source_id
    LEFT JOIN northdata_events ne
        ON se.content_scope = 'source'
        AND a.source_type = 'northdata_events'
        AND ne.id = se.source_id

    WHERE
        (%(source_types)s IS NULL OR a.source_type = ANY(%(source_types)s))
        AND (
            (a.source_type = 'webpages' AND w.id IS NOT NULL)
            OR
            (a.source_type = 'pdfs' AND ps.id IS NOT NULL AND p.id IS NOT NULL)
            OR
            (a.source_type = 'northdata_publications' AND np.id IS NOT NULL)
            OR
            (a.source_type = 'northdata_events' AND ne.id IS NOT NULL)
        )
        AND (%(companies)s IS NULL OR COALESCE(w.company, p.company, np.company_name, ne.company_name) = ANY(%(companies)s))
        AND (
            %(categories)s IS NULL
            OR se.category = ANY(%(categories)s)
            OR (
                %(include_secondary_categories)s
                AND se.secondary_categories && %(categories)s
            )
        )
        AND (%(secondary_categories)s IS NULL OR se.secondary_categories && %(secondary_categories)s)
        AND (
            %(page_type)s IS NULL
            OR COALESCE(
                w.page_type,
                CASE
                    WHEN np.id IS NOT NULL THEN COALESCE(NULLIF(np.source_name, ''), 'northdata_publication')
                    WHEN ne.id IS NOT NULL THEN COALESCE(NULLIF(ne.type, ''), 'northdata_event')
                END,
                'pdf_segment'
            ) = ANY(%(page_type)s)
        )
        AND (%(buckets)s IS NULL OR se.bucket = ANY(%(buckets)s))
        AND (%(signal_strength)s IS NULL OR se.signal_strength = ANY(%(signal_strength)s))
        AND (%(direction)s IS NULL OR se.direction = ANY(%(direction)s))
        AND (%(confidence)s IS NULL OR se.confidence = ANY(%(confidence)s))

    ORDER BY
        CASE se.bucket WHEN 'main' THEN 0 WHEN 'weak' THEN 1 ELSE 2 END,
        CASE se.confidence WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END,
        sort_timestamp DESC NULLS LAST,
        se.created_at DESC,
        se.id DESC
    LIMIT %(limit)s;
    """

    params = _filter_params(filters) | {"limit": limit}
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _filter_params(filters: RetrievalFilters) -> dict[str, Any]:
    return {
        "companies": list_or_none(filters.companies),
        "categories": list_or_none(filters.categories),
        "include_secondary_categories": filters.include_secondary_categories,
        "secondary_categories": list_or_none(filters.secondary_categories),
        "page_type": list_or_none(filters.page_type),
        "buckets": list_or_none(filters.buckets),
        "signal_strength": list_or_none(filters.signal_strength),
        "direction": list_or_none(filters.direction),
        "confidence": list_or_none(filters.confidence),
        "source_types": list_or_none(filters.source_types),
    }
