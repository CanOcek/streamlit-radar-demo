from __future__ import annotations

from typing import Literal


ChatIntent = Literal[
    "answer_from_loaded_evidence",
    "retrieve_more_evidence",
    "clarify_scope",
    "summarize_current_result",
    "run_structured_synthesis",
]


RETRIEVAL_TRIGGERS = (
    "find ",
    "search ",
    "retrieve ",
    "fetch ",
    "look for ",
    "look up ",
    "load evidence",
    "get evidence",
    "show evidence",
    "show me evidence",
    "scan for ",
    "identify signals",
    "new evidence",
)

SYNTHESIS_TRIGGERS = (
    "synthesize",
    "synthesis",
    "summarise this",
    "summarize this",
    "top opportunities and risks",
)

SUMMARY_TRIGGERS = (
    "summarize current",
    "summarise current",
    "what is loaded",
    "what evidence is loaded",
)


def classify_chat_intent(
    message: str,
    has_loaded_evidence: bool,
) -> ChatIntent:
    normalized = f" {message.strip().lower()} "

    if any(trigger in normalized for trigger in SYNTHESIS_TRIGGERS):
        return "run_structured_synthesis"

    if any(trigger in normalized for trigger in RETRIEVAL_TRIGGERS):
        return "retrieve_more_evidence"

    if has_loaded_evidence:
        if any(trigger in normalized for trigger in SUMMARY_TRIGGERS):
            return "summarize_current_result"
        return "answer_from_loaded_evidence"

    # With no loaded evidence, business questions that name a scope should try
    # retrieval. Ambiguity is handled by the retrieval planner.
    return "retrieve_more_evidence"

