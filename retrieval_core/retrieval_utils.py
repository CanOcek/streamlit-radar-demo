from typing import Any

from shared.db import get_db_connection

DEFAULT_FIELD_NAMES = [
    "all",
    "short_summary",
    "evidence",
    "why_it_matters_for_pntn",
    "possible_business_suggestion",
]
DEFAULT_BUCKETS = ["main", "weak"]
DEFAULT_SOURCE_TYPES = [
    "webpages",
    "pdfs",
    "northdata_publications",
    "northdata_events",
]
DEFAULT_CHUNK_SCOPES = [
    "webpage_chunk",
    "pdf_chunk",
    "northdata_publication_chunk",
    "northdata_event_chunk",
]


def list_or_none(value: Any) -> list[Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    values = [item for item in value if item is not None]
    return values or None


def print_results(results: list[dict[str, Any]], query: str | None = None) -> None:
    print("\n" + "=" * 100)
    print(f"QUERY: {query}" if query else "FILTERED RETRIEVAL")
    print("=" * 100)

    if not results:
        print("No results found.")
        return

    for row in results:
        best_similarity = row.get("best_similarity")
        if best_similarity is not None:
            print(f"best similarity : {best_similarity:.4f}")

        matched_fields = row.get("matched_fields") or []
        if matched_fields:
            print(f"best field      : {matched_fields[0].get('field_name')}")

        print(f"hit_type        : {row.get('hit_type')}")
        print(f"retrieval_source: {row.get('retrieval_source')}")
        print(f"mode            : {row.get('enrichment_mode')}")
        print(f"source_type     : {row.get('source_type')}")
        print(f"scope           : {row.get('content_scope')}")
        print(f"company         : {row.get('company')}")
        print(f"page_type       : {row.get('page_type')}")
        print(f"title           : {row.get('title')}")
        print(f"date            : {row.get('date')}")
        print(f"url             : {row.get('raw_url')}")
        print(f"source_id       : {row.get('source_id')}")

        if row.get("pdf_segment_id") is not None:
            print(f"pdf_segment_id  : {row.get('pdf_segment_id')}")
            print(f"segment_index   : {row.get('segment_index')}")
        if row.get("webpage_chunk_id") is not None:
            print(f"webpage_chunk_id: {row.get('webpage_chunk_id')}")
        if row.get("pdf_chunk_id") is not None:
            print(f"pdf_chunk_id    : {row.get('pdf_chunk_id')}")
        if row.get("northdata_publication_chunk_id") is not None:
            print(f"nd_pub_chunk_id : {row.get('northdata_publication_chunk_id')}")
        if row.get("northdata_event_chunk_id") is not None:
            print(f"nd_event_chunk_id: {row.get('northdata_event_chunk_id')}")
        if row.get("chunk_index") is not None:
            print(f"chunk_index     : {row.get('chunk_index')}")

        if row.get("enrichment_mode") == "noise":
            print(f"noise_result    : {row.get('noise_result')}")
            print(f"noise_reason    : {row.get('noise_reason')}")
        else:
            print(f"bucket          : {row.get('bucket')}")
            print(f"category        : {row.get('category')}")
            print(f"secondary       : {row.get('secondary_categories')}")
            print(f"summary         : {row.get('short_summary')}")
            print(f"evidence        : {row.get('evidence')}")
            print(f"why it matters  : {row.get('why_it_matters_for_pntn')}")
            print(f"suggestion      : {row.get('possible_business_suggestion')}")
            print(f"signal_strength : {row.get('signal_strength')}")
            print(f"direction       : {row.get('direction')}")
            print(f"confidence      : {row.get('confidence')}")

        print("-" * 100)
