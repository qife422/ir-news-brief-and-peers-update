#!/usr/bin/env python3
"""Validate structured IR brief data without external dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


VALID_STATUSES = {"example", "draft", "reviewed", "final"}
VALID_DIRECTIONS = {"positive", "negative", "mixed", "neutral", "uncertain"}
VALID_RELIABILITY = {"high", "medium", "low"}
PEER_METRICS = {
    "pe_25e",
    "pe_26e",
    "pe_27e",
    "ev_ebitda_25e",
    "ev_ebitda_26e",
    "ev_ebitda_27e",
    "eps_cagr",
    "peg",
    "revenue_growth",
    "ebitda_margin",
    "market_cap",
    "enterprise_value",
    "share_performance",
}


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _is_iso_date(value: Any) -> bool:
    if not _non_empty_string(value):
        return False
    candidate = value.strip().replace("Z", "+00:00")
    try:
        datetime.fromisoformat(candidate)
        return True
    except ValueError:
        return False


def _require_string(
    obj: dict[str, Any], key: str, path: str, errors: list[str]
) -> None:
    if not _non_empty_string(obj.get(key)):
        errors.append(f"{path}.{key}: required non-empty string")


def _validate_score(
    value: Any, path: str, minimum: int, maximum: int, errors: list[str]
) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        errors.append(f"{path}: required numeric score {minimum}-{maximum}")
    elif value < minimum or value > maximum:
        errors.append(f"{path}: must be between {minimum} and {maximum}")


def validate_report(data: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return ["root: report must be a JSON object"], warnings

    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("metadata: required object")
        metadata = {}

    for key in (
        "title",
        "report_date",
        "generated_at",
        "as_of",
        "timezone",
        "coverage_start",
        "coverage_end",
        "report_status",
    ):
        _require_string(metadata, key, "metadata", errors)

    for key in ("report_date", "generated_at", "as_of", "coverage_start", "coverage_end"):
        value = metadata.get(key)
        if _non_empty_string(value) and not _is_iso_date(value):
            errors.append(f"metadata.{key}: must be ISO-8601 date or datetime")

    status = str(metadata.get("report_status", "")).lower()
    if status and status not in VALID_STATUSES:
        errors.append(
            "metadata.report_status: must be Example, Draft, Reviewed, or Final"
        )
    if status == "final":
        approval = metadata.get("final_approval")
        if not isinstance(approval, dict):
            errors.append("metadata.final_approval: required for Final status")
        else:
            _require_string(approval, "approved_by", "metadata.final_approval", errors)
            _require_string(approval, "approved_at", "metadata.final_approval", errors)

    summaries = data.get("executive_summary")
    if not isinstance(summaries, list) or not summaries:
        errors.append("executive_summary: required non-empty array")
    else:
        for index, item in enumerate(summaries):
            path = f"executive_summary[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{path}: required object")
                continue
            _require_string(item, "text", path, errors)
            _require_string(item, "ir_action", path, errors)
            if item.get("direction") not in VALID_DIRECTIONS:
                errors.append(f"{path}.direction: invalid or missing direction")

    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("sources: required non-empty array")
        sources = []

    source_ids: set[str] = set()
    for index, source in enumerate(sources):
        path = f"sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{path}: required object")
            continue
        for key in ("id", "name", "source_type", "accessed_at", "reliability"):
            _require_string(source, key, path, errors)
        source_id = source.get("id")
        if _non_empty_string(source_id):
            if source_id in source_ids:
                errors.append(f"{path}.id: duplicate source ID {source_id}")
            source_ids.add(source_id)
        if source.get("reliability") not in VALID_RELIABILITY:
            errors.append(f"{path}.reliability: must be high, medium, or low")
        if not _is_iso_date(source.get("accessed_at")):
            errors.append(f"{path}.accessed_at: must be ISO-8601")
        has_timestamp = _is_iso_date(source.get("published_at"))
        missing_timestamp = source.get("timestamp_status") == "missing"
        if not has_timestamp and not missing_timestamp:
            errors.append(
                f"{path}: published_at is required unless timestamp_status is missing"
            )
        if not _non_empty_string(source.get("url")) and not _non_empty_string(
            source.get("source_note")
        ):
            errors.append(f"{path}: url or source_note is required")

    def validate_source_ref(value: Any, path: str) -> None:
        if not _non_empty_string(value):
            errors.append(f"{path}: required source ID")
        elif value not in source_ids:
            errors.append(f"{path}: unknown source ID {value}")

    all_news: list[tuple[str, Any]] = []
    for group_name in ("top_stories", "news"):
        group = data.get(group_name, [])
        if not isinstance(group, list):
            errors.append(f"{group_name}: must be an array")
            continue
        all_news.extend((f"{group_name}[{index}]", item) for index, item in enumerate(group))

    if not all_news:
        warnings.append("top_stories/news: no news items; HTML will show an empty state")

    for path, item in all_news:
        if not isinstance(item, dict):
            errors.append(f"{path}: required object")
            continue
        for key in (
            "title",
            "category",
            "published_at",
            "summary",
            "transmission_path",
            "ir_action",
            "horizon",
        ):
            _require_string(item, key, path, errors)
        if _non_empty_string(item.get("published_at")) and not _is_iso_date(
            item.get("published_at")
        ):
            errors.append(f"{path}.published_at: must be ISO-8601")
        if item.get("direction") not in VALID_DIRECTIONS:
            errors.append(f"{path}.direction: invalid or missing direction")
        _validate_score(item.get("impact"), f"{path}.impact", 1, 5, errors)
        _validate_score(item.get("urgency"), f"{path}.urgency", 1, 5, errors)
        _validate_score(
            item.get("materiality_score"), f"{path}.materiality_score", 0, 100, errors
        )
        refs = item.get("source_ids")
        if not isinstance(refs, list) or not refs:
            errors.append(f"{path}.source_ids: required non-empty array")
        else:
            for ref_index, source_id in enumerate(refs):
                validate_source_ref(source_id, f"{path}.source_ids[{ref_index}]")
        if _non_empty_string(item.get("image_url")):
            _require_string(item, "image_alt", path, errors)
            _require_string(item, "image_source", path, errors)

    market_pulse = data.get("market_pulse", [])
    if not isinstance(market_pulse, list):
        errors.append("market_pulse: must be an array")
        market_pulse = []
    if not market_pulse:
        warnings.append("market_pulse: empty; HTML will show an empty state")
    for index, metric in enumerate(market_pulse):
        path = f"market_pulse[{index}]"
        if not isinstance(metric, dict):
            errors.append(f"{path}: required object")
            continue
        for key in ("label", "unit", "as_of"):
            _require_string(metric, key, path, errors)
        if metric.get("value") is None:
            errors.append(f"{path}.value: required; use no row for unavailable metrics")
        if not _is_iso_date(metric.get("as_of")):
            errors.append(f"{path}.as_of: must be ISO-8601")
        validate_source_ref(metric.get("source_id"), f"{path}.source_id")
        trend = metric.get("trend", [])
        if trend and (
            not isinstance(trend, list)
            or any(not isinstance(value, (int, float)) for value in trend)
        ):
            errors.append(f"{path}.trend: must be an array of numbers")

    peers = data.get("peers", [])
    if not isinstance(peers, list):
        errors.append("peers: must be an array")
        peers = []
    if not peers:
        warnings.append("peers: empty; HTML will show a data-unavailable state")
    for index, peer in enumerate(peers):
        path = f"peers[{index}]"
        if not isinstance(peer, dict):
            errors.append(f"{path}: required object")
            continue
        for key in (
            "company",
            "ticker",
            "listing",
            "currency",
            "fiscal_basis",
            "share_basis",
            "as_of",
            "metric_basis",
        ):
            _require_string(peer, key, path, errors)
        if not _is_iso_date(peer.get("as_of")):
            errors.append(f"{path}.as_of: must be ISO-8601")
        validate_source_ref(peer.get("source_id"), f"{path}.source_id")
        if not any(peer.get(metric) is not None for metric in PEER_METRICS):
            errors.append(f"{path}: at least one supported peer metric is required")

    data_gaps = data.get("data_gaps", [])
    if not isinstance(data_gaps, list):
        errors.append("data_gaps: must be an array")
    elif any(not _non_empty_string(gap) for gap in data_gaps):
        errors.append("data_gaps: each item must be a non-empty string")

    prompt_used = data.get("prompt_used")
    if not isinstance(prompt_used, dict):
        errors.append("prompt_used: required object")
    else:
        for key in ("brief", "screening_criteria", "source_scope"):
            _require_string(prompt_used, key, "prompt_used", errors)

    return errors, warnings


def load_report(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Structured IR report JSON")
    args = parser.parse_args(argv)

    try:
        data = load_report(args.input)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    errors, warnings = validate_report(data)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if errors:
        print(f"Validation failed: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"Validation passed: 0 errors, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
