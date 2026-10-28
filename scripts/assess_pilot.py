#!/usr/bin/env python3
"""Assess public coverage and the completeness of human pilot records.

This module does not generate wording, inspect holdout questions, verify source
authenticity, or accept an IR deliverable. All outputs remain pending human
acceptance. Only standard-library dependencies are used.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

from ir_workflow import build_report


CASE_TYPES = ("peer_update", "earnings_preparation", "meeting")
METRIC_NAMES = ("preparation_time", "factual_accuracy", "question_value", "feedback_reuse")
CORE_PATH = Path(__file__).with_name("ir_workflow.py")
BINDING_KEYS = ("workspace_sha256", "candidate_report_sha256", "generation_sha256", "core_sha256")


def _hash(value):
    try:
        payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        raise ValueError("input: must contain finite JSON values") from None
    return hashlib.sha256(payload).hexdigest()


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _time(value):
    if not _nonempty(value):
        raise ValueError("time: offset-aware timestamp required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("time: offset-aware timestamp required") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("time: offset-aware timestamp required")
    return parsed


def _generation(value):
    if not isinstance(value, dict) or not _nonempty(value.get("prompt")) or not isinstance(value.get("config"), dict):
        raise ValueError("generation: prompt and config required")
    _hash(value)
    return value


def _public_report(workspace):
    if not isinstance(workspace, dict):
        raise ValueError("workspace: object required")
    try:
        return build_report(workspace, audience="public")
    except (ValueError, KeyError, TypeError):
        # Core validation may mention supplied values. Do not echo those here.
        raise ValueError("workspace: invalid or not projectable") from None


def _bindings(workspace, generation, report=None):
    _generation(generation)
    report = report if report is not None else _public_report(workspace)
    try:
        core_hash = hashlib.sha256(CORE_PATH.read_bytes()).hexdigest()
    except OSError:
        raise ValueError("core: source unavailable") from None
    result = {"workspace_sha256": _hash(workspace),
              "candidate_report_sha256": _hash(report),
              "generation_sha256": _hash(generation), "core_sha256": core_hash}
    result["candidate_sha256"] = _hash(result)
    return result


def freeze_candidate(workspace, generation):
    """Bind exact supplied JSON, projected public report, generation and core.

    The caller must supply the authored candidate workspace. This is a content
    identity, not evidence that its author was blind to later actual questions.
    Canonical hashes ignore JSON whitespace/key ordering, not record content.
    """
    return {"schema_version": "1.0", "status": "candidate_frozen",
            "frozen_at": datetime.now(timezone.utc).isoformat(),
            **_bindings(workspace, generation), "proves_holdout_blindness": False}


def _example(record):
    return (str(record.get("status", "")).lower() == "example"
            or str(record.get("data_kind", "")).lower() == "example"
            or str(record.get("kind", "")).lower().startswith("example"))


def _coverage(workspace, report, requested):
    if not isinstance(requested, list):
        raise ValueError("required_coverage: array required")
    pairs = []
    for row in requested:
        if not isinstance(row, dict) or not _nonempty(row.get("company")):
            raise ValueError("required_coverage.company: nonempty string required")
        periods = row.get("periods")
        if not isinstance(periods, list) or not periods or any(not _nonempty(x) for x in periods):
            raise ValueError("required_coverage.periods: nonempty string array required")
        for period in periods:
            if (row["company"], period) not in pairs:
                pairs.append((row["company"], period))
    sources = {s["id"]: s for s in report["sources"]}
    original = {c["id"]: c for c in workspace.get("claims", [])}
    facts = {}
    if not _example(report["metadata"]):
        for topic in report["topics"]:
            for fact in topic["facts"]:
                citations = fact.get("citations", [])
                if (fact.get("status") != "confirmed" or _example(original.get(fact["id"], {}))
                        or not citations or any(_example(sources.get(c["source_id"], {})) for c in citations)):
                    continue
                key = (fact["company"], fact["period"])
                bucket = facts.setdefault(key, {"claim_ids": set(), "source_ids": set()})
                bucket["claim_ids"].add(fact["id"])
                bucket["source_ids"].update(c["source_id"] for c in citations)
    result = []
    for company, period in pairs:
        bucket = facts.get((company, period), {"claim_ids": set(), "source_ids": set()})
        result.append({"company": company, "period": period,
                       "status": "covered" if bucket["claim_ids"] else "missing",
                       "claim_ids": sorted(bucket["claim_ids"]), "source_ids": sorted(bucket["source_ids"])})
    return result


def _number(value, field, integer=False):
    try:
        finite = isinstance(value, (int, float)) and math.isfinite(value)
    except (OverflowError, TypeError):
        finite = False
    if (isinstance(value, bool) or not finite
            or value < 0 or (integer and not isinstance(value, int))):
        raise ValueError("metrics." + field + ": nonnegative finite number required")
    return value


def _ratio(numerator, denominator):
    if denominator == 0:
        return None
    try:
        result = numerator / denominator
        finite = math.isfinite(result)
    except (OverflowError, ZeroDivisionError):
        finite = False
    if not finite:
        raise ValueError("metrics: derived ratio is not finite")
    return result


def _metric(name, row):
    if row is None:
        return None
    if not isinstance(row, dict):
        raise ValueError("metrics: object or null required")
    # A reference is needed to find the underlying timing sheet or count review.
    # It is a human assertion: this script does not open or semantically score it.
    if not _nonempty(row.get("evidence_ref")):
        return None
    if name == "preparation_time":
        fields = ("manual_minutes", "assisted_minutes")
        if any(row.get(k) is None for k in fields):
            return None
        manual, assisted = (_number(row[k], name + "." + k) for k in fields)
        comparable = row.get("comparable_scope") is True
        return {"manual_minutes": manual, "assisted_minutes": assisted,
                "comparable_scope": comparable,
                "minutes_saved": manual - assisted if comparable else None,
                "reduction_fraction": _ratio(manual - assisted, manual) if comparable else None}
    count_fields = {
        "factual_accuracy": ("checked", "supported", "contradicted", "unsupported", "uncertain"),
        "question_value": ("reviewed", "accepted", "accepted_after_edit", "rejected"),
        "feedback_reuse": ("eligible_items", "used_items"),
    }[name]
    if any(row.get(k) is None for k in count_fields):
        return None
    values = {k: _number(row[k], name + "." + k, integer=True) for k in count_fields}
    if name in {"factual_accuracy", "question_value"}:
        denominator = count_fields[0]
        if sum(values[k] for k in count_fields[1:]) != values[denominator]:
            raise ValueError("metrics." + name + ": counts do not reconcile")
        numerator = values["supported"] if name == "factual_accuracy" else values["accepted"] + values["accepted_after_edit"]
        values["supported_fraction" if name == "factual_accuracy" else "adoption_fraction"] = _ratio(numerator, values[denominator])
    else:
        if values["used_items"] > values["eligible_items"]:
            raise ValueError("metrics.feedback_reuse: counts do not reconcile")
        values["reuse_fraction"] = _ratio(values["used_items"], values["eligible_items"])
    return values


def _human_review(row, freeze, freeze_status):
    if row is None:
        return "not_recorded"
    if not isinstance(row, dict):
        raise ValueError("human_review: object or null required")
    if not all(_nonempty(row.get(k)) for k in ("reviewer", "at", "scope")):
        return "not_recorded"
    reviewed_at = _time(row["at"])
    if (freeze_status != "matched" or row.get("candidate_sha256") != freeze.get("candidate_sha256")
            or reviewed_at < _time(freeze["frozen_at"])):
        return "unbound"
    if reviewed_at > datetime.now(timezone.utc):
        return "future"
    return "recorded"


def _holdout(row, freeze, freeze_status):
    if row is None:
        return "not_recorded"
    if not isinstance(row, dict):
        raise ValueError("holdout: object or null required")
    if row.get("contaminated") is True:
        return "contaminated"
    if row.get("contaminated") is not False or not _nonempty(row.get("opened_at")):
        return "not_recorded"
    opened = _time(row["opened_at"])
    if opened > datetime.now(timezone.utc):
        return "future_opening"
    if freeze_status != "matched" or row.get("frozen_candidate_sha256") != freeze.get("candidate_sha256"):
        return "unbound"
    try:
        frozen = _time(freeze.get("frozen_at"))
    except ValueError:
        return "unbound"
    if opened < frozen:
        return "opened_before_freeze"
    # A declaration is not a verified blind evaluation or a semantic pass.
    return "declared_uncontaminated"


def assess_pilot(workspace, plan, freeze=None):
    """Return coverage gaps and structural pilot-review status, never Final."""
    if not isinstance(plan, dict):
        raise ValueError("plan: object required")
    report = _public_report(workspace)
    coverage = _coverage(workspace, report, plan.get("required_coverage", []))
    if freeze is not None and not isinstance(freeze, dict):
        raise ValueError("freeze: object or null required")
    generation = plan.get("generation")
    if generation is not None:
        _generation(generation)
    changed = []
    if freeze is None:
        freeze_status = "missing"
    elif generation is None:
        freeze_status, changed = "mismatch", ["generation_sha256"]
    else:
        expected = _bindings(workspace, generation, report)
        changed = [key for key in (*BINDING_KEYS, "candidate_sha256") if freeze.get(key) != expected[key]]
        try:
            frozen_at = _time(freeze.get("frozen_at"))
            if frozen_at > datetime.now(timezone.utc):
                changed.append("frozen_at")
        except ValueError:
            changed.append("frozen_at")
        freeze_status = "mismatch" if changed else "matched"
    supplied = plan.get("cases", [])
    if not isinstance(supplied, list):
        raise ValueError("cases: array required")
    by_type = {}
    for case in supplied:
        if not isinstance(case, dict) or case.get("case_type") not in CASE_TYPES:
            raise ValueError("cases.case_type: supported type required")
        if case["case_type"] in by_type:
            raise ValueError("cases.case_type: duplicate type")
        by_type[case["case_type"]] = case
    results = []
    for case_type in CASE_TYPES:
        case = by_type.get(case_type, {})
        kind = case.get("data_kind")
        if kind is not None and (not isinstance(kind, str) or kind not in {"public_real", "authorized_real", "Example"}):
            raise ValueError("cases.data_kind: unsupported value")
        blockers = []
        inputs = kind in {"public_real", "authorized_real"} and not _example(workspace.get("metadata", {}))
        if not inputs:
            blockers.append("real_inputs_not_confirmed")
        permitted = _nonempty(case.get("permission_ref"))
        if not permitted:
            blockers.append("permission_not_recorded")
        if freeze_status != "matched":
            blockers.append("candidate_not_frozen" if freeze_status == "missing" else "candidate_mismatch")
        review_status = _human_review(case.get("human_review"), freeze, freeze_status)
        if review_status != "recorded":
            blockers.append("human_review_" + review_status)
        raw_metrics = case.get("metrics")
        if raw_metrics is not None and not isinstance(raw_metrics, dict):
            raise ValueError("metrics: object or null required")
        metrics = {name: _metric(name, (raw_metrics or {}).get(name)) for name in METRIC_NAMES}
        if any(v is None for v in metrics.values()):
            blockers.append("metrics_not_recorded")
        holdout_status = _holdout(case.get("holdout"), freeze, freeze_status)
        if holdout_status != "declared_uncontaminated":
            blockers.append("holdout_" + holdout_status)
        if (review_status == "recorded" and holdout_status == "declared_uncontaminated"
                and _time(case["human_review"]["at"]) < _time(case["holdout"]["opened_at"])):
            blockers.append("review_before_holdout")
        status = ("pending_inputs" if not inputs or not permitted else
                  "pending_freeze" if freeze_status != "matched" else
                  "pending_business_review" if blockers else "review_record_complete")
        results.append({"case_type": case_type, "status": status, "blockers": blockers,
                        "metrics": metrics, "holdout_status": holdout_status})
    return {"schema_version": "1.0", "status": "Draft",
            "business_acceptance": "pending_human_acceptance",
            "freeze_status": freeze_status, "freeze_changes": changed,
            "coverage": coverage, "cases": results,
            "limitations": ["Coverage counts eligible confirmed public facts, not document counts or semantic completeness.",
                            "Source authenticity, permission and human-review declarations require human verification.",
                            "Candidate identity and holdout declarations do not prove author blindness.",
                            "review_record_complete describes structure, not business acceptance or Final."]}


def _load(path, role):
    try:
        with Path(path).open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError, UnicodeError):
        raise ValueError(role + ": JSON unavailable or invalid") from None


def _write_new(path, value):
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    try:
        with Path(path).open("x", encoding="utf-8") as handle:
            handle.write(payload)
    except OSError:
        raise ValueError("output: exclusive creation failed") from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freezing = commands.add_parser("freeze")
    freezing.add_argument("workspace")
    freezing.add_argument("generation")
    freezing.add_argument("output")
    assessment = commands.add_parser("assess")
    assessment.add_argument("workspace")
    assessment.add_argument("plan")
    assessment.add_argument("output")
    assessment.add_argument("--freeze")
    args = parser.parse_args(argv)
    try:
        workspace = _load(args.workspace, "workspace")
        if args.command == "freeze":
            result = freeze_candidate(workspace, _load(args.generation, "generation"))
        else:
            plan = _load(args.plan, "plan")
            frozen = _load(args.freeze, "freeze") if args.freeze else None
            result = assess_pilot(workspace, plan, frozen)
        _write_new(args.output, result)
    except (ValueError, OverflowError):
        # Stable diagnostics avoid disclosing supplied source text or paths.
        print("Pilot assessment failed: invalid input or output unavailable.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
