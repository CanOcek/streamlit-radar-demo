from __future__ import annotations

import re
from typing import Any

from .models import ChatCitation


CITATION_PATTERN = re.compile(r"\bE\d+\b")


def citation_from_row(row: dict[str, Any], citation_id: str) -> ChatCitation:
    return ChatCitation(
        citation_id=citation_id,
        company=str(row.get("company") or ""),
        title=str(row.get("title") or row.get("heading") or "Untitled"),
        url=str(row.get("raw_url") or ""),
        source_id=row.get("source_id"),
        enrichment_id=row.get("enrichment_id"),
        pdf_segment_id=row.get("pdf_segment_id"),
        retrieval_source=str(row.get("retrieval_source") or ""),
        best_similarity=_safe_float(row.get("best_similarity")),
    )


def format_citation_for_prompt(citation: ChatCitation) -> str:
    parts = [
        citation.citation_id,
        f"company={citation.company or 'N/A'}",
        f"title={citation.title or 'Untitled'}",
    ]
    if citation.url:
        parts.append(f"url={citation.url}")
    if citation.source_id is not None:
        parts.append(f"source_id={citation.source_id}")
    if citation.enrichment_id is not None:
        parts.append(f"enrichment_id={citation.enrichment_id}")
    if citation.pdf_segment_id is not None:
        parts.append(f"pdf_segment_id={citation.pdf_segment_id}")
    if citation.best_similarity is not None:
        parts.append(f"similarity={citation.best_similarity:.2f}")
    return " | ".join(parts)


def extract_citation_ids(text: str, valid_ids: set[str]) -> list[str]:
    found = []
    seen = set()
    for match in CITATION_PATTERN.findall(text or ""):
        if match in valid_ids and match not in seen:
            found.append(match)
            seen.add(match)
    return found


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
