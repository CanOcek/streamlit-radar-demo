from __future__ import annotations

import re
from dataclasses import dataclass, field

from retrieval_core import RetrievalFilters, RetrievalOptions, VectorQuerySpec


DIRECTION_BY_TERMS = {
    "risk": {"risk", "risks", "threat", "threats", "concern", "concerns"},
    "opportunity": {"opportunity", "opportunities", "growth", "potential", "promising"},
    "neutral": {"neutral", "watch", "watchpoint", "watchpoints", "monitoring"},
}

CONFIDENCE_TERMS = {"high", "medium", "low"}
SIGNAL_STRENGTH_TERMS = {"strong", "weak"}

QUERY_STOPWORDS = {
    "about",
    "all",
    "and",
    "are",
    "around",
    "can",
    "company",
    "evidence",
    "fetch",
    "find",
    "for",
    "from",
    "get",
    "identify",
    "in",
    "into",
    "load",
    "look",
    "me",
    "new",
    "please",
    "retrieve",
    "scan",
    "search",
    "show",
    "signal",
    "signals",
    "the",
    "to",
    "what",
}


@dataclass(frozen=True)
class ChatRetrievalPlan:
    filters: RetrievalFilters | None
    vector_queries: list[VectorQuerySpec] = field(default_factory=list)
    options: RetrievalOptions | None = None
    scope_companies: list[str] = field(default_factory=list)
    scope_categories: list[str] = field(default_factory=list)
    clarification: str | None = None
    summary: str = ""

    @property
    def needs_clarification(self) -> bool:
        return bool(self.clarification)


def plan_retrieval_from_question(
    question: str,
    available_companies: list[str],
    available_categories: list[str],
    selected_companies: list[str],
    selected_categories: list[str],
    fallback_companies: list[str],
    fallback_categories: list[str],
    base_options: RetrievalOptions,
    include_secondary_categories: bool,
) -> ChatRetrievalPlan:
    matched_companies = _match_options(question, available_companies)
    matched_categories = _match_options(question, available_categories)

    companies = matched_companies or selected_companies
    categories = matched_categories or selected_categories

    if not companies:
        if len(fallback_companies) == 1:
            companies = fallback_companies
        else:
            return ChatRetrievalPlan(
                filters=None,
                clarification="Which company should I retrieve evidence for?",
            )

    if not categories:
        if len(fallback_categories) == 1:
            categories = fallback_categories
        elif companies:
            categories = fallback_categories
        else:
            return ChatRetrievalPlan(
                filters=None,
                clarification="Which category should I retrieve evidence for?",
            )

    directions = _directions_from_question(question)
    confidence = _confidence_from_question(question)
    signal_strength = _signal_strength_from_question(question)
    vector_query = _build_vector_query(
        question=question,
        companies=companies,
        categories=categories,
        directions=directions,
        confidence=confidence,
        signal_strength=signal_strength,
    )

    filters = RetrievalFilters(
        companies=companies,
        categories=categories,
        include_secondary_categories=include_secondary_categories,
        direction=directions or None,
        confidence=confidence or None,
        signal_strength=signal_strength or None,
    )
    vector_queries = [
        VectorQuerySpec(
            query=vector_query,
            include_chunk_embeddings=True,
            require_chunk_enrichment=True,
        )
    ]
    options = RetrievalOptions(
        limit=base_options.limit,
        include_raw_content=base_options.include_raw_content,
        min_vector_similarity=base_options.min_vector_similarity,
        apply_limit_after_dedupe=base_options.apply_limit_after_dedupe,
    )

    return ChatRetrievalPlan(
        filters=filters,
        vector_queries=vector_queries,
        options=options,
        scope_companies=companies,
        scope_categories=categories,
        summary=_format_plan_summary(
            companies=companies,
            categories=categories,
            directions=directions,
            confidence=confidence,
            signal_strength=signal_strength,
            vector_query=vector_query,
        ),
    )


def _match_options(question: str, options: list[str]) -> list[str]:
    normalized_question = _normalize(question)
    matches = []
    for option in options:
        if _option_matches(normalized_question, option):
            matches.append(option)
    return matches


def _option_matches(normalized_question: str, option: str) -> bool:
    normalized_option = _normalize(option)
    if not normalized_option:
        return False
    if _contains_phrase(normalized_question, normalized_option):
        return True

    # Allow partial category wording like "financial risks" -> "Financials".
    words = [word for word in normalized_option.split() if len(word) > 3]
    return any(
        _contains_phrase(normalized_question, variant)
        for word in words
        for variant in _word_variants(word)
    )


def _directions_from_question(question: str) -> list[str]:
    terms = _terms(question)
    return [
        direction
        for direction, direction_terms in DIRECTION_BY_TERMS.items()
        if terms & direction_terms
    ]


def _confidence_from_question(question: str) -> list[str]:
    terms = _terms(question)
    return [term for term in ("high", "medium", "low") if term in terms & CONFIDENCE_TERMS]


def _signal_strength_from_question(question: str) -> list[str]:
    terms = _terms(question)
    return [term for term in ("strong", "weak") if term in terms & SIGNAL_STRENGTH_TERMS]


def _build_vector_query(
    question: str,
    companies: list[str],
    categories: list[str],
    directions: list[str],
    confidence: list[str],
    signal_strength: list[str],
) -> str:
    query_terms = [
        term
        for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9/&.-]*", question)
        if term.lower() not in QUERY_STOPWORDS
    ]
    query = " ".join(query_terms).strip()
    if query:
        return query

    parts = [*categories]
    if directions:
        parts.extend(directions)
    if confidence:
        parts.extend(f"{item} confidence" for item in confidence)
    if signal_strength:
        parts.extend(signal_strength)
    parts.extend(companies)
    return " ".join(parts)


def _format_plan_summary(
    companies: list[str],
    categories: list[str],
    directions: list[str],
    confidence: list[str],
    signal_strength: list[str],
    vector_query: str,
) -> str:
    filters = []
    if directions:
        filters.append("direction=" + ", ".join(directions))
    if confidence:
        filters.append("confidence=" + ", ".join(confidence))
    if signal_strength:
        filters.append("signal_strength=" + ", ".join(signal_strength))

    filter_text = f"; filters: {'; '.join(filters)}" if filters else ""
    return (
        f"Retrieved evidence for {', '.join(companies)} "
        f"in {', '.join(categories)} using query \"{vector_query}\"{filter_text}."
    )


def _terms(question: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9/&.-]*", question.lower()))


def _contains_phrase(normalized_text: str, normalized_phrase: str) -> bool:
    return f" {normalized_phrase} " in f" {normalized_text} "


def _normalize(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _word_variants(word: str) -> set[str]:
    variants = {word}
    if word.endswith("ies") and len(word) > 4:
        variants.add(word[:-3] + "y")
    if word.endswith("s") and len(word) > 4:
        variants.add(word[:-1])
    return variants
