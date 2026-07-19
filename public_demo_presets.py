from __future__ import annotations

from copy import deepcopy
from typing import Any

from ui_presets import PRESET_CATEGORIES, PRESET_COMPANIES


ALL_LLM1_FIELDS = [
    "all",
    "short_summary",
    "evidence",
    "why_it_matters_for_pntn",
    "possible_business_suggestion",
]

ALL_DIRECTIONS = ["opportunity", "neutral", "risk"]
ALL_CONFIDENCES = ["high", "medium", "low"]
ALL_SIGNAL_STRENGTHS = ["strong", "medium"]

SHORT_SUMMARY_AND_EVIDENCE_FIELDS = [
    "short_summary",
    "evidence",
]

WHY_AND_SUGGESTION_FIELDS = [
    "why_it_matters_for_pntn",
    "possible_business_suggestion",
]


def get_public_demo_presets() -> list[dict[str, Any]]:
    return deepcopy(PUBLIC_DEMO_PRESETS)


def _exact_company_preset(company: str, label_company: str | None = None) -> dict[str, Any]:
    preset_id = company.lower().replace(" ", "-")
    display_company = label_company or company
    return {
        "id": f"{preset_id}-all-categories",
        "label": f"{display_company} - all categories",
        "companies": [company],
        "categories": PRESET_CATEGORIES,
        "use_unbounded_scope": False,
        "filters": {
            "signal_strength": ALL_SIGNAL_STRENGTHS,
            "direction": ALL_DIRECTIONS,
            "confidence": ALL_CONFIDENCES,
            "include_secondary_categories": True,
        },
        "retrieval": {
            "strategy": "Exact metadata fetch",
            "evidence_limit": 200,
            "token_limit": 300_000,
            "min_vector_similarity": 0.25,
            "include_raw_content": False,
            "vector_queries": [],
        },
    }


def _single_vector_preset(preset_id: str, label: str, query: str) -> dict[str, Any]:
    return {
        "id": preset_id,
        "label": label,
        "companies": PRESET_COMPANIES,
        "categories": PRESET_CATEGORIES,
        "use_unbounded_scope": True,
        "filters": {
            "signal_strength": ALL_SIGNAL_STRENGTHS,
            "direction": ALL_DIRECTIONS,
            "confidence": ALL_CONFIDENCES,
            "include_secondary_categories": True,
        },
        "retrieval": {
            "strategy": "Single vector query",
            "evidence_limit": 50,
            "token_limit": 300_000,
            "min_vector_similarity": 0.25,
            "include_raw_content": False,
            "vector_queries": [
                {
                    "query": query,
                    "enrichment_fields": ALL_LLM1_FIELDS,
                    "include_chunk_embeddings": True,
                }
            ],
        },
    }


PUBLIC_DEMO_PRESETS: list[dict[str, Any]] = [
    _exact_company_preset("Olympus"),
    _exact_company_preset("Scalable Capital"),
    _exact_company_preset("ECE", label_company="ECE Group"),
    _exact_company_preset("Raiffeisen"),
    _single_vector_preset(
        preset_id="all-companies-high-level-staff-vector",
        label='All companies - "Changes in High Level Staff"',
        query="Changes in High Level Staff",
    ),
    _single_vector_preset(
        preset_id="all-companies-ai-investment-vector",
        label='All companies - "Investment and Developments in AI"',
        query="Investment and Developments in AI",
    ),
    {
        "id": "all-companies-structural-change-opportunity-multi-vector",
        "label": "All companies - structural change + strong opportunity",
        "companies": PRESET_COMPANIES,
        "categories": PRESET_CATEGORIES,
        "use_unbounded_scope": True,
        "filters": {
            "signal_strength": ALL_SIGNAL_STRENGTHS,
            "direction": ALL_DIRECTIONS,
            "confidence": ALL_CONFIDENCES,
            "include_secondary_categories": True,
        },
        "retrieval": {
            "strategy": "Multi-query vector search",
            "evidence_limit": 50,
            "token_limit": 300_000,
            "min_vector_similarity": 0.25,
            "include_raw_content": False,
            "vector_queries": [
                {
                    "query": "significant structural change",
                    "enrichment_fields": SHORT_SUMMARY_AND_EVIDENCE_FIELDS,
                    "include_chunk_embeddings": True,
                },
                {
                    "query": "strong opportunity",
                    "enrichment_fields": WHY_AND_SUGGESTION_FIELDS,
                    "include_chunk_embeddings": True,
                },
            ],
        },
    },
]
