from typing import Any

from psycopg2.extras import RealDictCursor

try:
    from .retrieval_models import RetrievalFilters
    from .retrieval_utils import DEFAULT_FIELD_NAMES, get_db_connection, list_or_none
except ImportError:
    from retrieval_models import RetrievalFilters
    from retrieval_utils import DEFAULT_FIELD_NAMES, get_db_connection, list_or_none


def search_enrichment_embeddings(
    query_embedding: list[float],
    filters: RetrievalFilters | None = None,
    field_names: list[str] | None = None,
    limit: int = 40,
) -> list[dict[str, Any]]:
    filters = filters or RetrievalFilters()
    field_names = list_or_none(field_names) or list(DEFAULT_FIELD_NAMES)

    sql = """
    SELECT
        se.source_id,
        se.source_type,
        se.content_scope,
        se.pdf_segment_id,
        ps.segment_index,
        ps.heading,
        ps.heading_path,

        NULL::bigint AS webpage_chunk_id,
        NULL::bigint AS pdf_chunk_id,
        NULL::int AS chunk_index,

        COALESCE(w.company, p.company) AS company,
        COALESCE(w.page_type, 'pdf_segment') AS page_type,
        COALESCE(w.title, ps.heading, p.title) AS title,
        COALESCE(w.date, p.date) AS date,
        COALESCE(w.raw_url, p.pdf_link) AS raw_url,

        se.id AS enrichment_id,
        NULL::bigint AS noise_enrichment_id,
        se.bucket,
        se.is_relevant,
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

        MIN(ee.embedding::vector(3072) <=> %(query_embedding)s::vector(3072)) AS best_distance,
        1 - MIN(ee.embedding::vector(3072) <=> %(query_embedding)s::vector(3072)) AS best_similarity,
        JSONB_AGG(
            JSONB_BUILD_OBJECT(
                'field_name', ee.field_name,
                'content', ee.content,
                'retrieval_source', 'enrichment_embeddings',
                'distance', ee.embedding::vector(3072) <=> %(query_embedding)s::vector(3072),
                'similarity', 1 - (ee.embedding::vector(3072) <=> %(query_embedding)s::vector(3072))
            )
            ORDER BY ee.embedding::vector(3072) <=> %(query_embedding)s::vector(3072)
        ) AS matched_fields,

        'enrichment_embedding'::text AS hit_type,
        'enrichment_embeddings'::text AS retrieval_source,
        'normal'::text AS enrichment_mode,
        TRUE AS has_enrichment,
        CASE
            WHEN se.source_type = 'webpages' THEN w.updated_at
            ELSE COALESCE(ps.created_at, p.created_at, se.created_at)
        END AS sort_timestamp

    FROM enrichment_embeddings ee
    JOIN source_enrichments se ON se.id = ee.enrichment_id
    LEFT JOIN webpages w
        ON se.content_scope = 'source'
        AND se.source_type = 'webpages'
        AND w.id = se.source_id
    LEFT JOIN pdf_segments ps
        ON se.content_scope = 'pdf_segment'
        AND se.source_type = 'pdfs'
        AND ps.id = se.pdf_segment_id
    LEFT JOIN pdfs p
        ON p.id = ps.pdf_id

    WHERE
        ee.field_name = ANY(%(field_names)s)
        AND (%(source_types)s IS NULL OR se.source_type = ANY(%(source_types)s))
        AND (
            (se.source_type = 'webpages' AND w.id IS NOT NULL)
            OR
            (se.source_type = 'pdfs' AND ps.id IS NOT NULL AND p.id IS NOT NULL)
        )
        AND (%(companies)s IS NULL OR COALESCE(w.company, p.company) = ANY(%(companies)s))
        AND (
            %(categories)s IS NULL
            OR se.category = ANY(%(categories)s)
            OR (
                %(include_secondary_categories)s
                AND se.secondary_categories && %(categories)s
            )
        )
        AND (%(secondary_categories)s IS NULL OR se.secondary_categories && %(secondary_categories)s)
        AND (%(page_type)s IS NULL OR COALESCE(w.page_type, 'pdf_segment') = ANY(%(page_type)s))
        AND (%(buckets)s IS NULL OR se.bucket = ANY(%(buckets)s))
        AND (%(is_relevant)s IS NULL OR se.is_relevant = %(is_relevant)s)
        AND (%(signal_strength)s IS NULL OR se.signal_strength = ANY(%(signal_strength)s))
        AND (%(direction)s IS NULL OR se.direction = ANY(%(direction)s))
        AND (%(confidence)s IS NULL OR se.confidence = ANY(%(confidence)s))

    GROUP BY
        se.source_id,
        se.source_type,
        se.content_scope,
        se.pdf_segment_id,
        ps.segment_index,
        ps.heading,
        ps.heading_path,
        COALESCE(w.company, p.company),
        COALESCE(w.page_type, 'pdf_segment'),
        COALESCE(w.title, ps.heading, p.title),
        COALESCE(w.date, p.date),
        COALESCE(w.raw_url, p.pdf_link),
        se.id,
        se.bucket,
        se.is_relevant,
        se.category,
        se.secondary_categories,
        se.signal_strength,
        se.direction,
        se.confidence,
        se.short_summary,
        se.evidence,
        se.why_it_matters_for_pntn,
        se.possible_business_suggestion,
        CASE
            WHEN se.source_type = 'webpages' THEN w.updated_at
            ELSE COALESCE(ps.created_at, p.created_at, se.created_at)
        END

    ORDER BY best_distance ASC
    LIMIT %(limit)s;
    """

    params = _filter_params(filters) | {
        "field_names": field_names,
        "query_embedding": query_embedding,
        "limit": limit,
    }
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
        "is_relevant": filters.is_relevant,
        "signal_strength": list_or_none(filters.signal_strength),
        "direction": list_or_none(filters.direction),
        "confidence": list_or_none(filters.confidence),
        "source_types": list_or_none(filters.source_types),
    }
