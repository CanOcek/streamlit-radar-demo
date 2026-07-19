from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from LLM_stage2 import run_stage2_from_signals
from LLM_stage2.db_signal_adapter import retrieval_rows_to_stage1_signals
from LLM_stage2.token_budget import limit_rows_by_stage2_tokens
from retrieval_core import (
    RetrievalFilters,
    RetrievalOptions,
    VectorQuerySpec,
    retrieve_for_llm2,
)


PUBLIC_DEMO_DATA_DIR = Path(__file__).resolve().parent / "public_demo_data"
PUBLIC_DEMO_CACHE_PATH = PUBLIC_DEMO_DATA_DIR / "preset_outputs.json"
PUBLIC_DEMO_CACHE_VERSION = 1

SOURCE_TYPE_OPTIONS = [
    "webpages",
    "pdfs",
    "northdata_publications",
    "northdata_events",
]
CHUNK_SCOPE_OPTIONS = [
    "webpage_chunk",
    "pdf_chunk",
    "northdata_publication_chunk",
    "northdata_event_chunk",
]


def load_public_demo_cache(
    cache_path: Path = PUBLIC_DEMO_CACHE_PATH,
) -> dict[str, Any]:
    if not cache_path.exists():
        return {"version": PUBLIC_DEMO_CACHE_VERSION, "presets": {}}

    with cache_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        return {"version": PUBLIC_DEMO_CACHE_VERSION, "presets": {}}

    payload.setdefault("version", PUBLIC_DEMO_CACHE_VERSION)
    payload.setdefault("presets", {})
    return payload


def save_public_demo_cache(
    payload: dict[str, Any],
    cache_path: Path = PUBLIC_DEMO_CACHE_PATH,
) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as file:
        json.dump(
            make_json_safe(payload),
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write("\n")


def cached_public_demo_payload(
    selected_preset: dict[str, Any],
    cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cache_payload = cache or load_public_demo_cache()
    preset_payload = (cache_payload.get("presets") or {}).get(selected_preset["id"])
    if not preset_payload:
        return {
            "rows": [],
            "signals": [],
            "accepted_row_keys": set(),
            "result": None,
            "error": (
                f"No pre-generated public demo output was found for "
                f"{selected_preset['label']}. Run scripts/generate_public_demo_cache.py."
            ),
        }

    rows = list(preset_payload.get("rows") or [])
    return {
        "rows": rows,
        "signals": retrieval_rows_to_stage1_signals(rows),
        "accepted_row_keys": set(preset_payload.get("accepted_row_keys") or []),
        "result": preset_payload.get("result"),
        "error": None,
        "meta": preset_payload.get("meta") or {},
    }


def generate_public_demo_preset_payload(
    selected_preset: dict[str, Any],
) -> dict[str, Any]:
    retrieval_settings = selected_preset["retrieval"]
    filters = public_demo_retrieval_filters(selected_preset)
    options = RetrievalOptions(
        limit=int(retrieval_settings.get("evidence_limit", 50)),
        min_vector_similarity=float(retrieval_settings.get("min_vector_similarity", 0.25)),
        include_raw_content=bool(retrieval_settings.get("include_raw_content", False)),
    )
    token_limit = int(retrieval_settings.get("token_limit", 300_000))

    retrieved_rows = retrieve_for_llm2(
        filters=filters,
        vector_queries=public_demo_vector_queries(selected_preset),
        options=options,
    )
    token_budget = limit_rows_by_stage2_tokens(
        rows=retrieved_rows,
        scope_companies=selected_preset["companies"],
        scope_categories=selected_preset["categories"],
        token_limit=token_limit,
    )
    result = run_stage2_from_signals(
        signals=token_budget.signals,
        companies=selected_preset["companies"],
        categories=selected_preset["categories"],
        include_secondary=bool(
            selected_preset["filters"].get("include_secondary_categories", True)
        ),
    )
    result.setdefault("_meta", {})
    result["_meta"].update(
        {
            "preset_id": selected_preset["id"],
            "preset_label": selected_preset["label"],
            "retrieval_row_count": len(retrieved_rows),
            "accepted_evidence_row_count": len(token_budget.rows),
            "token_count": token_budget.token_count,
            "token_limit": token_limit,
            "token_limit_reached": token_budget.limit_reached,
            "mode": result["_meta"].get("mode"),
        }
    )

    return {
        "preset_id": selected_preset["id"],
        "preset_label": selected_preset["label"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "retrieval": selected_preset["retrieval"],
        "filters": selected_preset["filters"],
        "companies": selected_preset["companies"],
        "categories": selected_preset["categories"],
        "result": result,
        "rows": token_budget.rows,
        "evidence_ids": [
            row.get("_stage2_evidence_id")
            for row in token_budget.rows
            if row.get("_stage2_evidence_id")
        ],
        "accepted_row_keys": sorted(token_budget.accepted_row_keys),
        "meta": {
            "retrieval_row_count": len(retrieved_rows),
            "accepted_evidence_row_count": len(token_budget.rows),
            "token_count": token_budget.token_count,
            "token_limit": token_limit,
            "token_limit_reached": token_budget.limit_reached,
        },
    }


def public_demo_retrieval_filters(selected_preset: dict[str, Any]) -> RetrievalFilters:
    preset_filters = selected_preset["filters"]
    use_unbounded_scope = bool(selected_preset.get("use_unbounded_scope"))
    return RetrievalFilters(
        companies=None if use_unbounded_scope else selected_preset["companies"],
        categories=None if use_unbounded_scope else selected_preset["categories"],
        include_secondary_categories=bool(
            preset_filters.get("include_secondary_categories", True)
        ),
        secondary_categories=None,
        page_type=None,
        signal_strength=preset_filters.get("signal_strength") or None,
        direction=preset_filters.get("direction") or None,
        confidence=preset_filters.get("confidence") or None,
        source_types=SOURCE_TYPE_OPTIONS,
    )


def public_demo_vector_queries(selected_preset: dict[str, Any]) -> list[VectorQuerySpec]:
    specs = []
    for item in selected_preset["retrieval"].get("vector_queries") or []:
        fields = item.get("enrichment_fields") or []
        include_chunks = bool(item.get("include_chunk_embeddings"))
        specs.append(
            VectorQuerySpec(
                query=item.get("query") or "",
                enrichment_fields=fields,
                include_chunk_embeddings=include_chunks,
                include_normal=bool(fields or include_chunks),
                include_noise=False,
                chunk_scopes=CHUNK_SCOPE_OPTIONS,
                require_chunk_enrichment=True,
            )
        )
    return specs


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [make_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(make_json_safe(item) for item in value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value
