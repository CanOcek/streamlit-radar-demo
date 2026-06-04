from __future__ import annotations

from typing import Any

from LLM_stage2.token_budget import row_has_stage2_body

from .citations import citation_from_row, format_citation_for_prompt
from .models import ChatContext, ChatEvidenceItem


def build_chat_context(
    rows: list[dict[str, Any]],
    stage2_result: dict[str, Any] | None,
    scope_companies: list[str],
    scope_categories: list[str],
) -> ChatContext:
    evidence_items = []
    for idx, row in enumerate((row for row in rows if row_has_stage2_body(row)), start=1):
        citation = citation_from_row(row, citation_id=f"E{idx}")
        evidence_items.append(
            ChatEvidenceItem(
                citation=citation,
                summary=str(row.get("short_summary") or ""),
                evidence=str(row.get("evidence") or ""),
                why_it_matters_for_pntn=str(row.get("why_it_matters_for_pntn") or ""),
                possible_business_suggestion=str(row.get("possible_business_suggestion") or ""),
                category=str(row.get("category") or ""),
                secondary_categories=[
                    str(item)
                    for item in (row.get("secondary_categories") or [])
                    if item
                ],
                direction=str(row.get("direction") or ""),
                confidence=str(row.get("confidence") or ""),
                signal_strength=str(row.get("signal_strength") or ""),
                date=str(row.get("date") or ""),
            )
        )

    return ChatContext(
        scope_companies=scope_companies,
        scope_categories=scope_categories,
        stage2_summary=str((stage2_result or {}).get("executive_summary") or ""),
        grouped_findings=list((stage2_result or {}).get("grouped_findings") or []),
        evidence_items=evidence_items,
    )


def format_context_for_prompt(context: ChatContext) -> str:
    scope = (
        "SCOPE\n"
        f"Companies: {context.scope_companies or ['all loaded companies']}\n"
        f"Categories: {context.scope_categories or ['all loaded categories']}\n"
    )
    stage2 = _format_stage2_result(context)
    evidence = "\n\n".join(
        _format_evidence_item(item)
        for item in context.evidence_items
    )
    if not evidence:
        evidence = "No evidence items are loaded."
    return "\n\n".join([scope, stage2, "LOADED EVIDENCE\n" + evidence]).strip()


def citation_sources_for_ids(
    context: ChatContext,
    citation_ids: list[str],
) -> list[dict[str, Any]]:
    citation_by_id = {
        item.citation.citation_id: item.citation
        for item in context.evidence_items
    }
    sources = []
    for citation_id in citation_ids:
        citation = citation_by_id.get(citation_id)
        if not citation:
            continue
        sources.append(
            {
                "citation_id": citation.citation_id,
                "company": citation.company,
                "title": citation.title,
                "url": citation.url,
                "source_id": citation.source_id,
                "enrichment_id": citation.enrichment_id,
                "pdf_segment_id": citation.pdf_segment_id,
                "best_similarity": citation.best_similarity,
            }
        )
    return sources


def _format_stage2_result(context: ChatContext) -> str:
    if not context.stage2_summary and not context.grouped_findings:
        return "CURRENT SYNTHESIS\nNo LLM2 synthesis result is loaded."

    findings = []
    for finding in context.grouped_findings[:8]:
        title = finding.get("title") or "Untitled finding"
        direction = finding.get("direction") or "N/A"
        confidence = finding.get("confidence") or "N/A"
        summary = finding.get("summary") or ""
        supporting = ", ".join(finding.get("supporting_signal_titles") or [])
        findings.append(
            "\n".join(
                [
                    f"- {title}",
                    f"  direction={direction}; confidence={confidence}",
                    f"  summary={summary}",
                    f"  supporting_signal_titles={supporting or 'N/A'}",
                ]
            )
        )

    return "\n".join(
        [
            "CURRENT SYNTHESIS",
            f"Executive summary: {context.stage2_summary or 'N/A'}",
            "Grouped findings:",
            *(findings or ["N/A"]),
        ]
    )


def _format_evidence_item(item: ChatEvidenceItem) -> str:
    secondary = ", ".join(item.secondary_categories) if item.secondary_categories else "N/A"
    return "\n".join(
        [
            format_citation_for_prompt(item.citation),
            f"date={item.date or 'N/A'}",
            f"category={item.category or 'N/A'}; secondary_categories={secondary}",
            f"direction={item.direction or 'N/A'}; confidence={item.confidence or 'N/A'}; signal_strength={item.signal_strength or 'N/A'}",
            f"short_summary={item.summary or 'N/A'}",
            f"evidence={item.evidence or 'N/A'}",
            f"why_it_matters_for_pntn={item.why_it_matters_for_pntn or 'N/A'}",
            f"possible_business_suggestion={item.possible_business_suggestion or 'N/A'}",
        ]
    )

