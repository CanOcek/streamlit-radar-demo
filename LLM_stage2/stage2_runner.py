import json
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from retrieval_core import RetrievalFilters, RetrievalOptions, retrieve_for_llm2  # noqa: E402
from shared.settings import get_setting  # noqa: E402

from .db_signal_adapter import retrieval_rows_to_stage1_signals
from .formatter import format_signals_for_stage2
from .prompts2 import STAGE2_SYSTEM_PROMPT, build_stage2_user_prompt
from .schemas import Stage1Signal


load_dotenv(PROJECT_ROOT / ".env")


def infer_mode(companies: list[str], categories: list[str]) -> str:
    if len(companies) == 1 and len(categories) == 1:
        return "company_category"
    if len(companies) == 1 and len(categories) > 1:
        return "company_multi_category"
    if len(companies) > 1 and len(categories) == 1:
        return "multi_company_category"
    return "multi_company_multi_category"


def run_stage2_from_retrieval(
    filters: RetrievalFilters,
    vector_queries,
    options: RetrievalOptions,
    companies: list[str],
    categories: list[str],
    include_secondary: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = retrieve_for_llm2(
        filters=filters,
        vector_queries=vector_queries,
        options=options,
    )
    signals = retrieval_rows_to_stage1_signals(rows)
    result = run_stage2_from_signals(
        signals=signals,
        companies=companies,
        categories=categories,
        include_secondary=include_secondary,
    )
    result.setdefault("_meta", {})
    result["_meta"]["retrieval_row_count"] = len(rows)
    return result, rows


def run_stage2_from_signals(
    signals: list[Stage1Signal],
    companies: list[str],
    categories: list[str],
    include_secondary: bool = False,
    mode: str | None = None,
) -> dict[str, Any]:
    mode = mode or infer_mode(companies, categories)

    if not signals:
        return _empty_stage2_result(
            companies=companies,
            categories=categories,
            mode=mode,
            include_secondary=include_secondary,
        )

    formatted_signals = format_signals_for_stage2(signals, mode=mode)
    user_prompt = build_stage2_user_prompt(
        companies=companies,
        categories=categories,
        mode=mode,
        formatted_signals=formatted_signals,
    )

    response = _openai_client().chat.completions.create(
        model=get_setting("OPENAI_MODEL", "gpt-5.4"),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": STAGE2_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content
    parsed = json.loads(content)
    parsed["_meta"] = {
        "signal_count": len(signals),
        "include_secondary": include_secondary,
        "mode": mode,
    }
    return parsed


def run_stage2(
    company: str,
    category: str,
    include_weak: bool = True,
    include_secondary: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    buckets = ["main", "weak"] if include_weak else ["main"]
    filters = RetrievalFilters(
        companies=[company],
        categories=[category],
        include_secondary_categories=include_secondary,
        buckets=buckets,
    )
    result, _rows = run_stage2_from_retrieval(
        filters=filters,
        vector_queries=[],
        options=RetrievalOptions(limit=limit),
        companies=[company],
        categories=[category],
        include_secondary=include_secondary,
    )
    return result


def build_stage2_prompt_preview(
    signals: list[Stage1Signal],
    companies: list[str],
    categories: list[str],
    mode: str | None = None,
) -> str:
    mode = mode or infer_mode(companies, categories)
    formatted_signals = format_signals_for_stage2(signals, mode=mode)
    return build_stage2_user_prompt(
        companies=companies,
        categories=categories,
        mode=mode,
        formatted_signals=formatted_signals,
    )


def _empty_stage2_result(
    companies: list[str],
    categories: list[str],
    mode: str,
    include_secondary: bool,
) -> dict[str, Any]:
    return {
        "scope": {
            "companies": companies,
            "categories": categories,
            "mode": mode,
        },
        "executive_summary": "No relevant signals found for the selected scope.",
        "overall_direction": "neutral",
        "overall_confidence": "low",
        "grouped_findings": [],
        "top_opportunities": [],
        "emerging_opportunities": [],
        "top_risks": [],
        "recommended_follow_up": [],
        "_meta": {
            "signal_count": 0,
            "include_secondary": include_secondary,
            "mode": mode,
        },
    }


def _openai_client() -> OpenAI:
    api_key = get_setting("OPEN_AI_API_KEY") or get_setting("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPEN_AI_API_KEY is not configured.")
    return OpenAI(api_key=api_key)
