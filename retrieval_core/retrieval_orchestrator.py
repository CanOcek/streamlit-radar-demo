from typing import Any

try:
    from .chunk_vector_retrieval import search_chunk_embeddings
    from .content_hydration import hydrate_raw_content
    from .enrichment_vector_retrieval import search_enrichment_embeddings
    from .result_consolidation import consolidate_results, limit_unranked_results
    from .retrieval_models import RetrievalFilters, RetrievalOptions, VectorQuerySpec, RelatedContext
    from .signal_retrieval import fetch_enrichment_signals
except ImportError:
    from chunk_vector_retrieval import search_chunk_embeddings
    from content_hydration import hydrate_raw_content
    from enrichment_vector_retrieval import search_enrichment_embeddings
    from result_consolidation import consolidate_results, limit_unranked_results
    from retrieval_models import RetrievalFilters, RetrievalOptions, VectorQuerySpec, RelatedContext
    from signal_retrieval import fetch_enrichment_signals

from shared.embeddings import embed_text


def retrieve_signals(
    filters: RetrievalFilters | None = None,
    vector_queries: list[VectorQuerySpec] | None = None,
    options: RetrievalOptions | None = None,
) -> list[dict[str, Any]]:
    filters = filters or RetrievalFilters()
    options = options or RetrievalOptions()
    active_vector_queries = [
        spec for spec in (vector_queries or []) if spec.query and spec.query.strip()
    ]

    if not active_vector_queries:
        rows = fetch_enrichment_signals(filters=filters, limit=options.limit)
        rows = limit_unranked_results(rows, limit=options.limit)
        return _maybe_hydrate(rows, include_raw_content=options.include_raw_content)

    rows: list[dict[str, Any]] = []
    for spec in active_vector_queries:
        query_embedding = embed_query(spec.query)

        if spec.include_normal and spec.enrichment_fields:
            rows.extend(
                search_enrichment_embeddings(
                    query_embedding=query_embedding,
                    filters=filters,
                    field_names=spec.enrichment_fields,
                    limit=options.limit,
                )
            )

        if spec.include_normal and spec.include_chunk_embeddings:
            rows.extend(
                search_chunk_embeddings(
                    query_embedding=query_embedding,
                    filters=filters,
                    chunk_scopes=spec.chunk_scopes,
                    enrichment_mode="normal",
                    require_enrichment=spec.require_chunk_enrichment,
                    limit=options.limit,
                )
            )

        if spec.include_noise and spec.include_chunk_embeddings and not filters.categories:
            rows.extend(
                search_chunk_embeddings(
                    query_embedding=query_embedding,
                    filters=_noise_filters(filters),
                    chunk_scopes=spec.chunk_scopes,
                    enrichment_mode="noise",
                    require_enrichment=True,
                    limit=options.limit,
                )
            )

    rows = consolidate_results(
        rows,
        limit=options.limit if options.apply_limit_after_dedupe else None,
    )
    return _maybe_hydrate(rows, include_raw_content=options.include_raw_content)


def retrieve_for_llm2(
    filters: RetrievalFilters | None = None,
    vector_queries: list[VectorQuerySpec] | None = None,
    options: RetrievalOptions | None = None,
) -> list[dict[str, Any]]:
    return retrieve_signals(filters=filters, vector_queries=vector_queries, options=options)


def embed_query(query: str) -> list[float]:
    return embed_text(query)


def _noise_filters(filters: RetrievalFilters) -> RetrievalFilters:
    return RetrievalFilters(
        companies=filters.companies,
        page_type=filters.page_type,
        source_types=filters.source_types,
        buckets=None,
    )

def _maybe_hydrate(
    rows: list[dict[str, Any]],
    include_raw_content: bool,
) -> list[dict[str, Any]]:
    if not include_raw_content:
        return rows
    return hydrate_raw_content(rows)


