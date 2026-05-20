from collections import defaultdict
from typing import List

from .schemas import Stage1Signal


def _format_signal_block(signal: Stage1Signal, idx: int) -> str:
    secondary = ", ".join(signal.secondary_categories) if signal.secondary_categories else "None"

    return f"""
Signal {idx}
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

def format_signals_for_stage2(
    signals: List[Stage1Signal],
    mode: str,
    max_signals: int = 40
) -> str:
    """
    Formats signals differently depending on scope mode.
    This helps LLM2 reason clearly without changing the core logic.
    """
    if not signals:
        return "No signals available."

    selected = signals[:max_signals]

    if mode == "company_category":
        blocks = [_format_signal_block(signal, i) for i, signal in enumerate(selected, start=1)]
        return "\n\n---\n\n".join(blocks)

    if mode == "company_multi_category":
        grouped = defaultdict(list)
        for signal in selected:
            grouped[signal.category].append(signal)

        sections = []
        for category, cat_signals in grouped.items():
            blocks = [_format_signal_block(signal, i) for i, signal in enumerate(cat_signals, start=1)]
            sections.append(f"## CATEGORY: {category}\n\n" + "\n\n---\n\n".join(blocks))

        return "\n\n====================\n\n".join(sections)

    if mode == "multi_company_category":
        grouped = defaultdict(list)
        for signal in selected:
            grouped[signal.company].append(signal)

        sections = []
        for company, company_signals in grouped.items():
            blocks = [_format_signal_block(signal, i) for i, signal in enumerate(company_signals, start=1)]
            sections.append(f"## COMPANY: {company}\n\n" + "\n\n---\n\n".join(blocks))

        return "\n\n====================\n\n".join(sections)

    if mode == "multi_company_multi_category":
        grouped = defaultdict(lambda: defaultdict(list))
        for signal in selected:
            grouped[signal.company][signal.category].append(signal)

        company_sections = []
        for company, category_map in grouped.items():
            category_sections = []
            for category, cat_signals in category_map.items():
                blocks = [_format_signal_block(signal, i) for i, signal in enumerate(cat_signals, start=1)]
                category_sections.append(f"### CATEGORY: {category}\n\n" + "\n\n---\n\n".join(blocks))
            company_sections.append(f"## COMPANY: {company}\n\n" + "\n\n".join(category_sections))

        return "\n\n====================\n\n".join(company_sections)

    # fallback
    blocks = [_format_signal_block(signal, i) for i, signal in enumerate(selected, start=1)]
    return "\n\n---\n\n".join(blocks)