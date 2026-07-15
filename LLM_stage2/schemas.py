from dataclasses import dataclass, field
from typing import List


@dataclass
class Stage1Signal:
    evidence_id: str
    company: str
    title: str
    date: str
    bucket: str
    category: str
    secondary_categories: List[str]
    short_summary: str
    evidence: str
    why_it_matters_for_pntn: str
    direction: str
    possible_business_suggestion: str
    confidence: str
    pntn_fit_check: str = ""
    signal_strength: str = ""
    page_type: str = ""
    source_type: str = ""
    url: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class Scope:
    companies: List[str]
    categories: List[str]
    mode: str  # company_category | company_multi_category | multi_company_category | multi_company_multi_category


@dataclass
class GroupedFinding:
    finding_id: str
    title: str
    finding_type: str  # shared_pattern | company_specific | category_specific | cross_category_pattern
    companies: List[str]
    categories: List[str]
    summary: str
    why_it_matters_for_pntn: str
    direction: str
    confidence: str
    supporting_signal_titles: List[str] = field(default_factory=list)
    supporting_signals: List["SupportingSignal"] = field(default_factory=list)


@dataclass
class SupportingSignal:
    signal_id: str
    title: str
    reason_used: str


@dataclass
class RankedItem:
    title: str
    companies: List[str]
    categories: List[str]
    reason: str


@dataclass
class Stage2Result:
    scope: Scope
    executive_summary: str
    overall_direction: str
    overall_confidence: str
    grouped_findings: List[GroupedFinding]
    top_opportunities: List[RankedItem]
    emerging_opportunities: List[RankedItem]
    top_risks: List[RankedItem]
    recommended_follow_up: List[str]

