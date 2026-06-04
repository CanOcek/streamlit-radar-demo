from __future__ import annotations

from typing import Any

from openai import OpenAI

from shared.settings import get_setting

from .citations import extract_citation_ids
from .context import format_context_for_prompt
from .models import ChatAnswer, ChatContext
from .prompts import CHAT_SYSTEM_PROMPT, build_chat_user_prompt
from .ranking import select_relevant_evidence
from .token_budget import limit_context_by_tokens


def answer_from_current_evidence(
    question: str,
    chat_history: list[dict[str, Any]],
    context: ChatContext,
) -> ChatAnswer:
    if not context.evidence_items:
        return ChatAnswer(
            content="No retrieved evidence is loaded yet. Retrieve evidence first, then ask a follow-up question.",
            evidence_count=0,
            selected_evidence_count=0,
            omitted_evidence_count=0,
        )

    ranked_context = select_relevant_evidence(context, question)
    token_budget = limit_context_by_tokens(
        context=ranked_context,
        question=question,
        chat_history=chat_history,
    )
    selected_context = token_budget.context
    if not selected_context.evidence_items:
        return ChatAnswer(
            content=(
                "The loaded evidence could not fit within the chat token budget. "
                "Use a narrower evidence retrieval scope or increase CHAT_TOKEN_LIMIT."
            ),
            evidence_count=token_budget.total_evidence_count,
            selected_evidence_count=0,
            omitted_evidence_count=token_budget.total_evidence_count,
        )

    valid_ids = {item.citation.citation_id for item in selected_context.evidence_items}
    context_text = format_context_for_prompt(selected_context)
    if token_budget.omitted_evidence_count:
        context_text += (
            "\n\nCONTEXT LIMIT NOTE\n"
            f"{token_budget.selected_evidence_count} of {token_budget.total_evidence_count} "
            "loaded evidence items are visible for this answer. "
            f"{token_budget.omitted_evidence_count} lower-ranked evidence item(s) were omitted by the chat token budget. "
            "Do not make claims based on omitted evidence."
        )

    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    messages.extend(_compact_history(chat_history))
    messages.append(
        {
            "role": "user",
            "content": build_chat_user_prompt(
                question=question,
                context_text=context_text,
            ),
        }
    )

    response = _openai_client().chat.completions.create(
        model=get_setting("OPENAI_MODEL", "gpt-5.4"),
        temperature=0,
        messages=messages,
    )
    content = response.choices[0].message.content or ""
    return ChatAnswer(
        content=content,
        cited_evidence_ids=extract_citation_ids(content, valid_ids),
        evidence_count=token_budget.total_evidence_count,
        selected_evidence_count=token_budget.selected_evidence_count,
        omitted_evidence_count=token_budget.omitted_evidence_count,
    )


def _compact_history(chat_history: list[dict[str, Any]]) -> list[dict[str, str]]:
    compacted = []
    for message in chat_history[-6:]:
        role = message.get("role")
        if role not in {"user", "assistant"}:
            continue
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        compacted.append({"role": role, "content": content})
    return compacted


def _openai_client() -> OpenAI:
    api_key = get_setting("OPEN_AI_API_KEY") or get_setting("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPEN_AI_API_KEY is not configured.")
    return OpenAI(api_key=api_key)
