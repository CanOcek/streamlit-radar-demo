from dataclasses import dataclass, field
from typing import Any

try:
    from .retrieval_utils import (
        DEFAULT_BUCKETS,
        DEFAULT_CHUNK_SCOPES,
        DEFAULT_FIELD_NAMES,
        DEFAULT_SOURCE_TYPES,
    )
except ImportError:
    from retrieval_utils import (
        DEFAULT_BUCKETS,
        DEFAULT_CHUNK_SCOPES,
        DEFAULT_FIELD_NAMES,
        DEFAULT_SOURCE_TYPES,
    )


@dataclass
class RetrievalFilters:
    companies: list[str] | None = None
    categories: list[str] | None = None
    include_secondary_categories: bool = False
    secondary_categories: list[str] | None = None
    page_type: str | list[str] | None = None
    buckets: list[str] | None = field(default_factory=lambda: list(DEFAULT_BUCKETS))
    signal_strength: str | list[str] | None = None
    direction: str | list[str] | None = None
    confidence: str | list[str] | None = None
    source_types: list[str] | None = field(default_factory=lambda: list(DEFAULT_SOURCE_TYPES))


@dataclass
class VectorQuerySpec:
    query: str
    enrichment_fields: list[str] | None = field(default_factory=lambda: list(DEFAULT_FIELD_NAMES))
    include_chunk_embeddings: bool = False
    include_normal: bool = True
    include_noise: bool = False
    chunk_scopes: list[str] | None = field(default_factory=lambda: list(DEFAULT_CHUNK_SCOPES))
    require_chunk_enrichment: bool = True


@dataclass
class RetrievalOptions:
    limit: int = 40
    include_raw_content: bool = False
    apply_limit_after_dedupe: bool = True
    min_vector_similarity: float = 0.20


RetrievalRow = dict[str, Any]


@dataclass
class RelatedContext:
    """Container for related companies and persons for a given scope."""
    related_companies: list[tuple[str, str, str, str, str, Any]]  # (related_to, company_name, company_url, description, status, roles)
    related_persons: list[tuple[str, str, str, str]]  # (related_to, full_name, description, roles)

@dataclass
class FinancialContext:
    """Container for financial data retrieved from northdata_companies."""
    financials: list[dict[str, Any]] = field(default_factory=list)