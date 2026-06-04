from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChatCitation:
    citation_id: str
    company: str
    title: str
    url: str
    source_id: Any = None
    enrichment_id: Any = None
    pdf_segment_id: Any = None
    retrieval_source: str = ""
    best_similarity: float | None = None


@dataclass(frozen=True)
class ChatEvidenceItem:
    citation: ChatCitation
    summary: str = ""
    evidence: str = ""
    why_it_matters_for_pntn: str = ""
    possible_business_suggestion: str = ""
    category: str = ""
    secondary_categories: list[str] = field(default_factory=list)
    direction: str = ""
    confidence: str = ""
    signal_strength: str = ""
    date: str = ""


@dataclass(frozen=True)
class ChatContext:
    scope_companies: list[str]
    scope_categories: list[str]
    stage2_summary: str = ""
    grouped_findings: list[dict[str, Any]] = field(default_factory=list)
    evidence_items: list[ChatEvidenceItem] = field(default_factory=list)


@dataclass(frozen=True)
class ChatAnswer:
    content: str
    cited_evidence_ids: list[str] = field(default_factory=list)
    evidence_count: int = 0
    selected_evidence_count: int = 0
    omitted_evidence_count: int = 0
