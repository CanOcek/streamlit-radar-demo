from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from public_demo_cache import (  # noqa: E402
    PUBLIC_DEMO_CACHE_PATH,
    PUBLIC_DEMO_CACHE_VERSION,
    generate_public_demo_preset_payload,
    load_public_demo_cache,
    save_public_demo_cache,
)
from public_demo_presets import get_public_demo_presets  # noqa: E402


def main() -> None:
    args = parse_args()
    presets = get_public_demo_presets()
    selected_presets = filter_presets(presets, args.preset)

    if not selected_presets:
        available = ", ".join(preset["id"] for preset in presets)
        raise SystemExit(f"No matching preset found. Available presets: {available}")

    cache = load_public_demo_cache(PUBLIC_DEMO_CACHE_PATH)
    cache["version"] = PUBLIC_DEMO_CACHE_VERSION
    cache.setdefault("presets", {})

    for idx, preset in enumerate(selected_presets, start=1):
        print(f"[{idx}/{len(selected_presets)}] Generating {preset['id']}")
        payload = generate_public_demo_preset_payload(preset)
        cache["presets"][preset["id"]] = payload
        save_public_demo_cache(cache, PUBLIC_DEMO_CACHE_PATH)
        print(
            "  saved "
            f"{payload['meta']['accepted_evidence_row_count']} evidence row(s), "
            f"{payload['meta']['token_count']:,} token(s)"
        )

    print(f"Cache written to {PUBLIC_DEMO_CACHE_PATH}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate saved public demo LLM2 outputs and ordered evidence rows."
    )
    parser.add_argument(
        "--preset",
        action="append",
        default=[],
        help="Preset ID to generate. Repeat for multiple presets. Defaults to all presets.",
    )
    return parser.parse_args()


def filter_presets(
    presets: list[dict[str, Any]],
    selected_ids: list[str],
) -> list[dict[str, Any]]:
    if not selected_ids:
        return presets

    selected = set(selected_ids)
    return [preset for preset in presets if preset["id"] in selected]


if __name__ == "__main__":
    main()
