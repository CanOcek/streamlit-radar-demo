from dataclasses import dataclass
from typing import Any

try:
    import tiktoken
except ImportError:
    tiktoken = None

from shared.settings import get_setting

from .db_signal_adapter import retrieval_rows_to_stage1_signals
from .formatter import format_signals_for_stage2
from .prompts2 import STAGE2_SYSTEM_PROMPT, build_stage2_user_prompt
from .stage2_runner import infer_mode


LLM2_BODY_FIELDS = (
    "short_summary",
    "evidence",
    "why_it_matters_for_pntn",
    "possible_business_suggestion",
)


@dataclass(frozen=True)
class Stage2TokenBudget:
    rows: list[dict[str, Any]]
    signals: list[Any]
    token_count: int
    limit_reached: bool
    accepted_row_keys: set[str]


def limit_rows_by_stage2_tokens(
    rows: list[dict[str, Any]],
    scope_companies: list[str],
    scope_categories: list[str],
    token_limit: int,
) -> Stage2TokenBudget:
    keyed_rows = [
        _with_stage2_token_key(row, idx)
        for idx, row in enumerate(rows)
    ]
    body_rows = [row for row in keyed_rows if row_has_stage2_body(row)]
    signals = retrieval_rows_to_stage1_signals(body_rows)
    if not signals or token_limit <= 0:
        return Stage2TokenBudget([], [], 0, bool(signals), set())

    token_count = count_stage2_input_tokens(
        signals=signals,
        scope_companies=scope_companies,
        scope_categories=scope_categories,
    )
    if token_count <= token_limit:
        return Stage2TokenBudget(
            rows=body_rows,
            signals=signals,
            token_count=token_count,
            limit_reached=False,
            accepted_row_keys={row["_stage2_token_key"] for row in body_rows},
        )

    limited_rows: list[dict[str, Any]] = []
    limited_signals: list[Any] = []
    limited_token_count = 0

    for row, signal in zip(body_rows, signals):
        candidate_signals = limited_signals + [signal]
        candidate_token_count = count_stage2_input_tokens(
            signals=candidate_signals,
            scope_companies=scope_companies,
            scope_categories=scope_categories,
        )
        # Evidence rows are atomic for LLM2: if the next full row plus prompt
        # overhead does not fit, exclude it instead of truncating its text.
        if candidate_token_count > token_limit:
            break

        limited_rows.append(row)
        limited_signals = candidate_signals
        limited_token_count = candidate_token_count

    return Stage2TokenBudget(
        rows=limited_rows,
        signals=limited_signals,
        token_count=limited_token_count,
        limit_reached=True,
        accepted_row_keys={row["_stage2_token_key"] for row in limited_rows},
    )


def stage2_token_row_key(row: dict[str, Any]) -> str | None:
    value = row.get("_stage2_token_key")
    return str(value) if value else None


def row_has_stage2_body(row: dict[str, Any]) -> bool:
    return any(
        _has_text(row.get(field_name))
        for field_name in LLM2_BODY_FIELDS
    )


def count_stage2_input_tokens(
    signals,
    scope_companies: list[str],
    scope_categories: list[str],
) -> int:
    if not signals:
        return 0

    mode = infer_mode(scope_companies, scope_categories)
    formatted_signals = format_signals_for_stage2(signals, mode=mode)
    user_prompt = build_stage2_user_prompt(
        companies=scope_companies,
        categories=scope_categories,
        mode=mode,
        formatted_signals=formatted_signals,
    )
    return count_tokens(STAGE2_SYSTEM_PROMPT) + count_tokens(user_prompt)


def count_tokens(text: str) -> int:
    if not text:
        return 0
    if tiktoken is None:
        return max(1, round(len(text) / 4))

    model = get_setting("OPENAI_MODEL", "gpt-4.1-mini")
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        try:
            encoding = tiktoken.get_encoding("o200k_base")
        except ValueError:
            encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def _has_text(value: Any) -> bool:
    return bool(str(value or "").strip())


def _with_stage2_token_key(row: dict[str, Any], idx: int) -> dict[str, Any]:
    keyed = dict(row)
    keyed["_stage2_token_key"] = _row_key(row, idx)
    return keyed


def _row_key(row: dict[str, Any], idx: int) -> str:
    parts = [
        idx,
        row.get("source_id"),
        row.get("enrichment_id"),
        row.get("noise_enrichment_id"),
        row.get("pdf_segment_id"),
        row.get("webpage_chunk_id"),
        row.get("pdf_chunk_id"),
        row.get("chunk_index"),
        row.get("hit_type"),
        row.get("retrieval_source"),
    ]
    return "|".join("" if part is None else str(part) for part in parts)
