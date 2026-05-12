from __future__ import annotations

from openai import OpenAI

from .settings import get_setting


EMBED_MODEL = "text-embedding-3-large"


def embed_text(text: str, model: str = EMBED_MODEL) -> list[float]:
    if not text:
        return []

    api_key = get_setting("OPEN_AI_API_KEY") or get_setting("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPEN_AI_API_KEY is not configured.")

    response = OpenAI(api_key=api_key).embeddings.create(
        model=model,
        input=text,
    )
    return response.data[0].embedding
