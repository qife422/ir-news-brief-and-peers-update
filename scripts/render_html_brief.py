#!/usr/bin/env python3
"""Render validated IR brief JSON into a self-contained HTML report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from validate_ir_data import load_report, validate_report


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = SCRIPT_DIR.parent / "assets" / "html" / "ir-brief-template.html"
DATA_MARKER = "__REPORT_DATA_JSON__"


def _safe_json(data: Any) -> str:
    return (
        json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def render_report(
    input_path: Path,
    output_path: Path,
    template_path: Path = DEFAULT_TEMPLATE,
    *,
    force: bool = False,
) -> tuple[list[str], list[str]]:
    data = load_report(input_path)
    errors, warnings = validate_report(data)
    if errors:
        return errors, warnings
    if output_path.exists() and not force:
        return [f"output exists: {output_path}; use --force to overwrite"], warnings
    if input_path.resolve() == output_path.resolve():
        return ["input and output paths must be different"], warnings

    template = template_path.read_text(encoding="utf-8")
    if template.count(DATA_MARKER) != 1:
        return [f"template must contain exactly one {DATA_MARKER} marker"], warnings

    html = template.replace(DATA_MARKER, _safe_json(data))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return [], warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Structured IR report JSON")
    parser.add_argument("output", type=Path, help="HTML output path")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output")
    args = parser.parse_args(argv)

    try:
        errors, warnings = render_report(
            args.input, args.output, args.template, force=args.force
        )
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        return 1
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
