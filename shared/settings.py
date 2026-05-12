from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")


@lru_cache(maxsize=1)
def _streamlit_secrets() -> dict[str, Any]:
    try:
        import streamlit as st

        return dict(st.secrets)
    except Exception:
        return {}


def get_setting(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value not in (None, ""):
        return value

    secrets = _streamlit_secrets()
    value = secrets.get(name)
    if value not in (None, ""):
        return str(value)

    return default
