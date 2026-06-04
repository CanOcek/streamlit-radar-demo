from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import tiktoken
except ImportError:
    tiktoken = None

from shared.settings import get_setting

from .context import format_context_for_prompt
from .models import ChatContext
from .prompts import CHAT_SYSTEM_PROMPT, build_chat_user_prompt


DEFAULT_CHAT_TOKEN_LIMIT = 24_000


@dataclass(frozen=True)
class ChatTokenBudget:
    context: ChatContext
    token_count: int
    total_evidence_count: int
    selected_evidence_count: int
    omitted_evidence_count: int
    limit_reached: bool


def limit_context_by_tokens(
    context: ChatContext,
    question: str,
    chat_history: list[dict[str, Any]],
    token_limit: int | None = None,
) -> ChatTokenBudget:
    token_limit = token_limit or _chat_token_limit()
    total_count = len(context.evidence_items)
    if total_count == 0:
        return ChatTokenBudget(
            context=context,
            token_count=0,
            total_evidence_count=0,
            selected_evidence_count=0,
            omitted_evidence_count=0,
            limit_reached=False,
        )

    full_token_count = _count_chat_input_tokens(
        context=context,
        question=question,
        chat_history=chat_history,
    )
    if full_token_count <= token_limit:
        return ChatTokenBudget(
            context=context,
            token_count=full_token_count,
            total_evidence_count=total_count,
            selected_evidence_count=total_count,
            omitted_evidence_count=0,
            limit_reached=False,
        )

    selected_items = []
    selected_token_count = 0
    for item in context.evidence_items:
        candidate = ChatContext(
            scope_companies=context.scope_companies,
            scope_categories=context.scope_categories,
            stage2_summary=context.stage2_summary,
            grouped_findings=context.grouped_findings,
            evidence_items=[*selected_items, item],
        )
        candidate_token_count = _count_chat_input_tokens(
            context=candidate,
            question=question,
            chat_history=chat_history,
        )
        if candidate_token_count > token_limit:
            break
        selected_items.append(item)
        selected_token_count = candidate_token_count

    limited_context = ChatContext(
        scope_companies=context.scope_companies,
        scope_categories=context.scope_categories,
        stage2_summary=context.stage2_summary,
        grouped_findings=context.grouped_findings,
        evidence_items=selected_items,
    )
    return ChatTokenBudget(
        context=limited_context,
        token_count=selected_token_count,
        total_evidence_count=total_count,
        selected_evidence_count=len(selected_items),
        omitted_evidence_count=total_count - len(selected_items),
        limit_reached=True,
    )


def count_tokens(text: str) -> int:
    if not text:
        return 0
    if tiktoken is None:
        return max(1, round(len(text) / 4))

    model = get_setting("OPENAI_MODEL", "gpt-5.4")
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        try:
            encoding = tiktoken.get_encoding("o200k_base")
        except ValueError:
            encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def _chat_token_limit() -> int:
    raw_value = get_setting("CHAT_TOKEN_LIMIT")
    if raw_value:
        try:
            return max(1, int(raw_value))
        except ValueError:
            pass
    return DEFAULT_CHAT_TOKEN_LIMIT


def _count_chat_input_tokens(
    context: ChatContext,
    question: str,
    chat_history: list[dict[str, Any]],
) -> int:
    history_text = "\n".join(
        f"{message.get('role')}: {message.get('content')}"
        for message in chat_history[-6:]
        if message.get("role") in {"user", "assistant"} and message.get("content")
    )
    user_prompt = build_chat_user_prompt(
        question=question,
        context_text=format_context_for_prompt(context),
    )
    return (
        count_tokens(CHAT_SYSTEM_PROMPT)
        + count_tokens(history_text)
        + count_tokens(user_prompt)
    )

