from typing import Any

from psycopg2.extras import RealDictCursor

try:
    from .retrieval_models import RetrievalFilters
    from .retrieval_utils import DEFAULT_CHUNK_SCOPES, get_db_connection, list_or_none
except ImportError:
    from retrieval_models import RetrievalFilters
    from retrieval_utils import DEFAULT_CHUNK_SCOPES, get_db_connection, list_or_none


def search_chunk_embeddings(
    query_embedding: list[float],
    filters: RetrievalFilters | None = None,
    chunk_scopes: list[str] | None = None,
    enrichment_mode: str = "normal",
    require_enrichment: bool = True,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if enrichment_mode not in {"normal", "noise"}:
        raise ValueError("enrichment_mode must be 'normal' or 'noise'.")

    filters = filters or RetrievalFilters()
    chunk_scopes = list_or_none(chunk_scopes) or list(DEFAULT_CHUNK_SCOPES)

    sql = """
    WITH scored_chunks AS (
        SELECT
            ce.source_id,
            a.source_type,
            CASE
                WHEN ce.content_scope = 'webpage_chunk' THEN 'source'
                WHEN ce.content_scope = 'pdf_chunk' THEN 'pdf_segment'
            END AS content_scope,
            CASE
                WHEN ce.content_scope = 'pdf_chunk' THEN ps.id
                ELSE NULL
            END AS pdf_segment_id,
            CASE
                WHEN ce.content_scope = 'pdf_chunk' THEN 'pdf_segment:' || ps.id::text
                ELSE 'source:' || ce.source_id::text
            END AS parent_key,
            ps.segment_index,
            ps.heading,
            ps.heading_path,

            ce.webpage_chunk_id,
            ce.pdf_chunk_id,
            ce.chunk_index,

            COALESCE(w.company, p.company) AS company,
            COALESCE(w.page_type, 'pdf_segment') AS page_type,
            COALESCE(w.title, ps.heading, p.title) AS title,
            COALESCE(w.date, p.date) AS date,
            COALESCE(w.raw_url, p.pdf_link) AS raw_url,

            se.id AS enrichment_id,
            sen.id AS noise_enrichment_id,
            CASE WHEN %(enrichment_mode)s = 'normal' THEN se.bucket ELSE 'noise' END AS bucket,
            CASE WHEN %(enrichment_mode)s = 'normal' THEN se.category ELSE NULL END AS category,
            CASE WHEN %(enrichment_mode)s = 'normal' THEN se.secondary_categories ELSE NULL END AS secondary_categories,
            CASE WHEN %(enrichment_mode)s = 'normal' THEN se.signal_strength ELSE NULL END AS signal_strength,
            CASE WHEN %(enrichment_mode)s = 'normal' THEN se.direction ELSE NULL END AS direction,
            CASE WHEN %(enrichment_mode)s = 'normal' THEN se.confidence ELSE NULL END AS confidence,

            CASE WHEN %(enrichment_mode)s = 'normal' THEN se.short_summary ELSE NULL END AS short_summary,
            CASE WHEN %(enrichment_mode)s = 'normal' THEN se.evidence ELSE NULL END AS evidence,
            CASE WHEN %(enrichment_mode)s = 'normal' THEN se.why_it_matters_for_pntn ELSE NULL END AS why_it_matters_for_pntn,
            CASE WHEN %(enrichment_mode)s = 'normal' THEN se.possible_business_suggestion ELSE NULL END AS possible_business_suggestion,
            CASE WHEN %(enrichment_mode)s = 'noise' THEN sen.result ELSE NULL END AS noise_result,
            CASE WHEN %(enrichment_mode)s = 'noise' THEN sen.reason ELSE NULL END AS noise_reason,

            ce.embedding::vector(3072) <=> %(query_embedding)s::vector(3072) AS best_distance,
            1 - (ce.embedding::vector(3072) <=> %(query_embedding)s::vector(3072)) AS best_similarity,
            JSONB_BUILD_ARRAY(
                JSONB_BUILD_OBJECT(
                    'field_name', 'chunk',
                    'content', ce.chunk_text,
                    'retrieval_source', 'chunk_embeddings',
                    'chunk_scope', ce.content_scope,
                    'webpage_chunk_id', ce.webpage_chunk_id,
                    'pdf_chunk_id', ce.pdf_chunk_id,
                    'chunk_index', ce.chunk_index,
                    'distance', ce.embedding::vector(3072) <=> %(query_embedding)s::vector(3072),
                    'similarity', 1 - (ce.embedding::vector(3072) <=> %(query_embedding)s::vector(3072))
                )
            ) AS matched_fields,

            'chunk_embedding'::text AS hit_type,
            'chunk_embeddings'::text AS retrieval_source,
            %(enrichment_mode)s::text AS enrichment_mode,
            CASE
                WHEN %(enrichment_mode)s = 'normal' THEN se.id IS NOT NULL
                WHEN %(enrichment_mode)s = 'noise' THEN sen.id IS NOT NULL
            END AS has_enrichment,
            CASE
                WHEN a.source_type = 'webpages' THEN w.updated_at
                ELSE COALESCE(ps.created_at, p.created_at, ce.created_at)
            END AS sort_timestamp

        FROM chunk_embeddings ce
        JOIN all_sources a ON a.id = ce.source_id

        LEFT JOIN webpage_chunks wc
            ON ce.content_scope = 'webpage_chunk'
            AND wc.id = ce.webpage_chunk_id
        LEFT JOIN webpages w
            ON w.id = wc.webpage_id

        LEFT JOIN pdf_chunks pc
            ON ce.content_scope = 'pdf_chunk'
            AND pc.id = ce.pdf_chunk_id
        LEFT JOIN pdf_segments ps
            ON ps.id = pc.segment_id
        LEFT JOIN pdfs p
            ON p.id = pc.pdf_id

        LEFT JOIN source_enrichments se
            ON (
                ce.content_scope = 'webpage_chunk'
                AND se.content_scope = 'source'
                AND se.source_id = ce.source_id
            )
            OR (
                ce.content_scope = 'pdf_chunk'
                AND se.content_scope = 'pdf_segment'
                AND se.pdf_segment_id = pc.segment_id
            )

        LEFT JOIN source_enrichments_noise sen
            ON (
                ce.content_scope = 'webpage_chunk'
                AND sen.content_scope = 'source'
                AND sen.source_id = ce.source_id
            )
            OR (
                ce.content_scope = 'pdf_chunk'
                AND sen.content_scope = 'pdf_segment'
                AND sen.pdf_segment_id = pc.segment_id
            )

        WHERE
            ce.content_scope = ANY(%(chunk_scopes)s)
            AND (%(source_types)s IS NULL OR a.source_type = ANY(%(source_types)s))
            AND (
                (a.source_type = 'webpages' AND w.id IS NOT NULL)
                OR
                (a.source_type = 'pdfs' AND ps.id IS NOT NULL AND p.id IS NOT NULL)
            )
            AND (%(companies)s IS NULL OR COALESCE(w.company, p.company) = ANY(%(companies)s))
            AND (%(page_type)s IS NULL OR COALESCE(w.page_type, 'pdf_segment') = ANY(%(page_type)s))
            AND (
                NOT %(require_enrichment)s
                OR (%(enrichment_mode)s = 'normal' AND se.id IS NOT NULL)
                OR (%(enrichment_mode)s = 'noise' AND sen.id IS NOT NULL)
            )
            AND (
                %(enrichment_mode)s <> 'normal'
                OR %(categories)s IS NULL
                OR se.category = ANY(%(categories)s)
                OR (
                    %(include_secondary_categories)s
                    AND se.secondary_categories && %(categories)s
                )
            )
            AND (
                %(enrichment_mode)s <> 'normal'
                OR %(secondary_categories)s IS NULL
                OR se.secondary_categories && %(secondary_categories)s
            )
            AND (
                %(enrichment_mode)s <> 'normal'
                OR %(buckets)s IS NULL
                OR se.bucket = ANY(%(buckets)s)
            )
            AND (
                %(enrichment_mode)s <> 'normal'
                OR %(signal_strength)s IS NULL
                OR se.signal_strength = ANY(%(signal_strength)s)
            )
            AND (
                %(enrichment_mode)s <> 'normal'
                OR %(direction)s IS NULL
                OR se.direction = ANY(%(direction)s)
            )
            AND (
                %(enrichment_mode)s <> 'normal'
                OR %(confidence)s IS NULL
                OR se.confidence = ANY(%(confidence)s)
            )
    ),
    ranked_chunks AS (
        SELECT
            scored_chunks.*,
            ROW_NUMBER() OVER (
                PARTITION BY parent_key
                ORDER BY best_distance ASC
            ) AS parent_rank
        FROM scored_chunks
    )
    SELECT
        source_id,
        source_type,
        content_scope,
        pdf_segment_id,
        segment_index,
        heading,
        heading_path,
        webpage_chunk_id,
        pdf_chunk_id,
        chunk_index,
        company,
        page_type,
        title,
        date,
        raw_url,
        enrichment_id,
        noise_enrichment_id,
        bucket,
        category,
        secondary_categories,
        signal_strength,
        direction,
        confidence,
        short_summary,
        evidence,
        why_it_matters_for_pntn,
        possible_business_suggestion,
        noise_result,
        noise_reason,
        best_distance,
        best_similarity,
        matched_fields,
        hit_type,
        retrieval_source,
        enrichment_mode,
        has_enrichment,
        sort_timestamp
    FROM ranked_chunks
    WHERE parent_rank = 1
    ORDER BY best_distance ASC
    LIMIT %(limit)s;
    """

    params = _filter_params(filters) | {
        "query_embedding": query_embedding,
        "chunk_scopes": chunk_scopes,
        "enrichment_mode": enrichment_mode,
        "require_enrichment": require_enrichment,
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
        "signal_strength": list_or_none(filters.signal_strength),
        "direction": list_or_none(filters.direction),
        "confidence": list_or_none(filters.confidence),
        "source_types": list_or_none(filters.source_types),
    }
