from collections import defaultdict
from typing import List

from .schemas import Stage1Signal


def _format_signal_block(signal: Stage1Signal, idx: int, evidence_id: str) -> str:
    secondary = ", ".join(signal.secondary_categories) if signal.secondary_categories else "None"

    return f"""
Signal {idx}
Evidence ID: {evidence_id}
Company: {signal.company}
Bucket: {signal.bucket}
Signal strength: {signal.signal_strength or "N/A"}
Confidence: {signal.confidence or "N/A"}
PNTN fit check: {signal.pntn_fit_check or "N/A"}
Date: {signal.date or "N/A"}
Primary category: {signal.category}
Secondary categories: {secondary}
Title: {signal.title}

Short summary:
{signal.short_summary or "N/A"}

Evidence:
{signal.evidence or "N/A"}

Why it matters for PNTN:
{signal.why_it_matters_for_pntn or "N/A"}

Direction:
{signal.direction or "N/A"}

Possible business suggestion:
{signal.possible_business_suggestion or "N/A"}
""".strip()


def _indexed_signals(signals: List[Stage1Signal]) -> list[tuple[int, str, Stage1Signal]]:
    return [
        (idx, signal.evidence_id or f"E{idx}", signal)
        for idx, signal in enumerate(signals, start=1)
    ]


def format_signals_for_stage2(
    signals: List[Stage1Signal],
    mode: str,
) -> str:
    """
    Formats signals differently depending on scope mode.
    This helps LLM2 reason clearly without changing the core logic.
    """
    if not signals:
        return "No signals available."

    indexed_signals = _indexed_signals(signals)

    if mode == "company_category":
        blocks = [
            _format_signal_block(signal, idx, evidence_id)
            for idx, evidence_id, signal in indexed_signals
        ]
        return "\n\n---\n\n".join(blocks)

    if mode == "company_multi_category":
        grouped = defaultdict(list)
        for item in indexed_signals:
            grouped[item[2].category].append(item)

        sections = []
        for category, cat_signals in grouped.items():
            blocks = [
                _format_signal_block(signal, idx, evidence_id)
                for idx, evidence_id, signal in cat_signals
            ]
            sections.append(f"## CATEGORY: {category}\n\n" + "\n\n---\n\n".join(blocks))

        return "\n\n====================\n\n".join(sections)

    if mode == "multi_company_category":
        grouped = defaultdict(list)
        for item in indexed_signals:
            grouped[item[2].company].append(item)

        sections = []
        for company, company_signals in grouped.items():
            blocks = [
                _format_signal_block(signal, idx, evidence_id)
                for idx, evidence_id, signal in company_signals
            ]
            sections.append(f"## COMPANY: {company}\n\n" + "\n\n---\n\n".join(blocks))

        return "\n\n====================\n\n".join(sections)

    if mode == "multi_company_multi_category":
        grouped = defaultdict(lambda: defaultdict(list))
        for item in indexed_signals:
            signal = item[2]
            grouped[signal.company][signal.category].append(item)

        company_sections = []
        for company, category_map in grouped.items():
            category_sections = []
            for category, cat_signals in category_map.items():
                blocks = [
                    _format_signal_block(signal, idx, evidence_id)
                    for idx, evidence_id, signal in cat_signals
                ]
                category_sections.append(f"### CATEGORY: {category}\n\n" + "\n\n---\n\n".join(blocks))
            company_sections.append(f"## COMPANY: {company}\n\n" + "\n\n".join(category_sections))

        return "\n\n====================\n\n".join(company_sections)

    # fallback
    blocks = [
        _format_signal_block(signal, idx, evidence_id)
        for idx, evidence_id, signal in indexed_signals
    ]
    return "\n\n---\n\n".join(blocks)
