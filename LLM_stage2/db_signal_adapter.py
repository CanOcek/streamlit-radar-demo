import html
from typing import Any

from .schemas import Stage1Signal


def retrieval_rows_to_stage1_signals(rows: list[dict[str, Any]]) -> list[Stage1Signal]:
    return [retrieval_row_to_stage1_signal(row) for row in rows]


def with_stage2_evidence_ids(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated = []
    for idx, row in enumerate(rows, start=1):
        item = dict(row)
        item["_stage2_evidence_id"] = item.get("_stage2_evidence_id") or f"E{idx}"
        annotated.append(item)
    return annotated


def retrieval_row_to_stage1_signal(row: dict[str, Any]) -> Stage1Signal:
    title = row.get("title") or row.get("heading") or ""
    category = html.unescape(row.get("category") or "")
    secondary_categories = [
        html.unescape(item or "")
        for item in (row.get("secondary_categories") or [])
    ]

    return Stage1Signal(
        evidence_id=row.get("_stage2_evidence_id") or row.get("evidence_id") or "",
        company=row.get("company") or "",
        title=title,
        date=row.get("date") or "",
        bucket=row.get("bucket") or "",
        category=category,
        secondary_categories=secondary_categories,
        short_summary=row.get("short_summary") or "",
        evidence=row.get("evidence") or "",
        why_it_matters_for_pntn=row.get("why_it_matters_for_pntn") or "",
        direction=row.get("direction") or "",
        possible_business_suggestion=row.get("possible_business_suggestion") or "",
        confidence=row.get("confidence") or "",
        pntn_fit_check=row.get("pntn_fit_check") or "",
        signal_strength=row.get("signal_strength") or "",
        page_type=row.get("page_type") or "",
        source_type=row.get("source_type") or "",
        url=row.get("raw_url") or "",
        raw=row,
    )
