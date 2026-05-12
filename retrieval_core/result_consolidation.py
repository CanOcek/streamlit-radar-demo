from typing import Any


def consolidate_results(
    rows: list[dict[str, Any]],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    merged: dict[tuple[str, Any], dict[str, Any]] = {}

    for row in rows:
        parent_key = get_parent_key(row)
        existing = merged.get(parent_key)
        if existing is None:
            merged[parent_key] = dict(row)
            continue

        best = _pick_best_row(existing, row)
        best = _fill_missing_values(best, existing)
        best = _fill_missing_values(best, row)
        best["matched_fields"] = _merge_matched_fields(
            existing.get("matched_fields") or [],
            row.get("matched_fields") or [],
        )
        merged[parent_key] = best

    ranked = sorted(merged.values(), key=_rank_key)
    return ranked if limit is None else ranked[:limit]


def limit_unranked_results(
    rows: list[dict[str, Any]],
    limit: int | None = None,
) -> list[dict[str, Any]]:
    return rows if limit is None else rows[:limit]


def get_parent_key(row: dict[str, Any]) -> tuple[str, Any]:
    if row.get("content_scope") == "pdf_segment" and row.get("pdf_segment_id") is not None:
        return "pdf_segment", row["pdf_segment_id"]
    return "source", row.get("source_id")


def _pick_best_row(
    current: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    current_distance = current.get("best_distance")
    candidate_distance = candidate.get("best_distance")

    if current_distance is None and candidate_distance is not None:
        return dict(candidate)
    if candidate_distance is None:
        return dict(current)
    if current_distance is None or candidate_distance < current_distance:
        return dict(candidate)
    return dict(current)


def _fill_missing_values(
    target: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    for key, value in source.items():
        if target.get(key) is None and value is not None:
            target[key] = value
    return target


def _merge_matched_fields(
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    for field in first + second:
        key = (
            field.get("retrieval_source"),
            field.get("field_name"),
            field.get("webpage_chunk_id"),
            field.get("pdf_chunk_id"),
            field.get("content"),
        )
        existing = merged.get(key)
        if existing is None or _field_distance(field) < _field_distance(existing):
            merged[key] = field

    return sorted(merged.values(), key=_field_distance)


def _rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    distance = row.get("best_distance")
    return (
        distance is None,
        distance if distance is not None else float("inf"),
        row.get("sort_timestamp") is None,
        row.get("sort_timestamp") or "",
    )


def _field_distance(field: dict[str, Any]) -> float:
    distance = field.get("distance")
    return distance if distance is not None else float("inf")
