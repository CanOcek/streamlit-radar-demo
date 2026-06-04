from __future__ import annotations

import re

from .models import ChatContext, ChatEvidenceItem


QUESTION_STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "all",
    "also",
    "and",
    "any",
    "are",
    "based",
    "best",
    "can",
    "compare",
    "does",
    "evidence",
    "explain",
    "for",
    "from",
    "give",
    "here",
    "how",
    "into",
    "most",
    "next",
    "only",
    "show",
    "strongest",
    "support",
    "supports",
    "tell",
    "that",
    "the",
    "there",
    "this",
    "what",
    "which",
    "why",
    "with",
}

RISK_TERMS = {"risk", "risks", "threat", "threats", "concern", "concerns"}
OPPORTUNITY_TERMS = {
    "opportunity",
    "opportunities",
    "potential",
    "growth",
    "promising",
}
NEUTRAL_TERMS = {"neutral", "monitoring", "watch", "watchpoint", "watchpoints"}
CONFIDENCE_TERMS = {"high", "medium", "low"}
STRENGTH_TERMS = {"strong", "weak"}


def select_relevant_evidence(context: ChatContext, question: str) -> ChatContext:
    if not context.evidence_items:
        return context

    terms = _question_terms(question)
    ranked_items = sorted(
        enumerate(context.evidence_items),
        key=lambda indexed: _rank_key(indexed[0], indexed[1], question, terms, context),
    )
    return ChatContext(
        scope_companies=context.scope_companies,
        scope_categories=context.scope_categories,
        stage2_summary=context.stage2_summary,
        grouped_findings=context.grouped_findings,
        evidence_items=[item for _, item in ranked_items],
    )


def _rank_key(
    original_index: int,
    item: ChatEvidenceItem,
    question: str,
    terms: set[str],
    context: ChatContext,
) -> tuple[int, int]:
    # Python sorts ascending, so larger relevance scores are negated.
    return (-_score_item(item, question, terms, context), original_index)


def _score_item(
    item: ChatEvidenceItem,
    question: str,
    terms: set[str],
    context: ChatContext,
) -> int:
    haystack = _item_text(item)
    score = 0

    for term in terms:
        if term in haystack:
            score += 3

    question_lower = question.lower()
    company = item.citation.company.lower()
    if company and company in question_lower:
        score += 12

    category = item.category.lower()
    if category and category in question_lower:
        score += 10
    for secondary in item.secondary_categories:
        if secondary.lower() in question_lower:
            score += 6

    direction = item.direction.lower()
    if direction == "risk" and terms & RISK_TERMS:
        score += 10
    if direction == "opportunity" and terms & OPPORTUNITY_TERMS:
        score += 10
    if direction == "neutral" and terms & NEUTRAL_TERMS:
        score += 8

    confidence = item.confidence.lower()
    if confidence in terms & CONFIDENCE_TERMS:
        score += 5
    if confidence == "high":
        score += 2
    elif confidence == "medium":
        score += 1

    strength = item.signal_strength.lower()
    if strength in terms & STRENGTH_TERMS:
        score += 5
    if strength == "strong":
        score += 2

    if _supports_loaded_finding(item, context):
        score += 2

    if item.citation.best_similarity is not None:
        score += max(0, min(3, round(item.citation.best_similarity * 3)))

    return score


def _supports_loaded_finding(item: ChatEvidenceItem, context: ChatContext) -> bool:
    title = item.citation.title.strip().lower()
    if not title:
        return False
    for finding in context.grouped_findings:
        supporting_titles = finding.get("supporting_signal_titles") or []
        if any(title == str(supporting).strip().lower() for supporting in supporting_titles):
            return True
    return False


def _item_text(item: ChatEvidenceItem) -> str:
    parts = [
        item.citation.company,
        item.citation.title,
        item.summary,
        item.evidence,
        item.why_it_matters_for_pntn,
        item.possible_business_suggestion,
        item.category,
        item.direction,
        item.confidence,
        item.signal_strength,
        *item.secondary_categories,
    ]
    return " ".join(parts).lower()


def _question_terms(question: str) -> set[str]:
    raw_terms = re.findall(r"[A-Za-z0-9][A-Za-z0-9/&.-]*", question.lower())
    return {
        term
        for term in raw_terms
        if len(term) > 2 and term not in QUESTION_STOPWORDS
    }

