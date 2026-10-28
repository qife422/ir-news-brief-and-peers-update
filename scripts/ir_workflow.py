#!/usr/bin/env python3
"""Deterministic, local IR workspace projections; no networking or model calls.

The workspace is an append-only evidence record. Reports are separate allowlisted
projections, never copies of that record. Textual support still requires IR review.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SCHEMA_VERSION = "1.0"
COLLECTIONS = ("sources", "excerpts", "claims", "topics", "questions", "answers",
               "feedback", "financials", "meetings", "events")
VISIBILITIES = {"public", "internal", "licensed"}
AUDIENCES = {"public", "internal"}
DEFINITIONS = ("company", "metric", "period", "currency", "unit",
               "accounting_basis", "share_basis", "definition_id")
EVENT_TYPES = {"source_retract", "source_supersede", "feedback_confirm",
               "feedback_revoke", "answer_review"}


def _dt(value):
    if not isinstance(value, str):
        raise ValueError("expected an ISO timestamp with an explicit UTC offset")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid ISO timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp must have an explicit UTC offset")
    return result.astimezone(timezone.utc)


def _digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _text_digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError("expected a finite decimal value")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid decimal value") from exc
    if not result.is_finite():
        raise ValueError("decimal value must be finite")
    return result


def _permission(record, audience, allowed):
    return (record.get("authorized") is True
            and record.get("visibility") in allowed
            and audience in record.get("audiences", [])
            and (audience != "public" or record.get("visibility") == "public"))


def _source_known(src):
    return all(src.get(field) is not None for field in ("published_at", "available_at", "version_at"))


def _choice(value, choices):
    return isinstance(value, str) and value in choices


def _has_permission(record):
    return any(field in record for field in ("authorized", "visibility", "audiences"))


def _refs(record, field):
    value = record.get(field, [])
    return value if isinstance(value, list) else []


def _index(data, collection):
    return {row["id"]: row for row in data.get(collection, [])}


def _lookup(index, ident):
    return index.get(ident, {}) if isinstance(ident, str) else {}


def _groups(claim):
    return claim.get("support_groups") or [claim.get("excerpt_ids", [])]


def validate_workspace(data):
    """Return structural errors and warnings; diagnostics do not echo raw text."""
    errors, warnings = [], []
    if not isinstance(data, dict):
        return ["workspace: expected an object"], warnings
    meta = data.get("metadata")
    if not isinstance(meta, dict):
        return ["metadata: expected an object"], warnings
    if meta.get("schema_version") != SCHEMA_VERSION:
        errors.append("metadata.schema_version: expected 1.0")
    for field in ("id", "subject_company", "timezone"):
        if not isinstance(meta.get(field), str) or not meta[field].strip():
            errors.append(f"metadata.{field}: required nonempty string")
    if not _choice(meta.get("status"), {"Example", "Draft", "Reviewed", "Final"}):
        errors.append("metadata.status: invalid delivery status")
    if meta.get("status") == "Example":
        warnings.append("Example input: demonstration only, not formal IR data")
    if not _choice(meta.get("audience"), AUDIENCES):
        errors.append("metadata.audience: expected public or internal")
    allowed = meta.get("allowed_visibility")
    if not isinstance(allowed, list) or not allowed or any(not _choice(v, VISIBILITIES) for v in allowed):
        errors.append("metadata.allowed_visibility: explicit permitted visibility list required")
    try:
        _dt(meta.get("as_of"))
    except ValueError as exc:
        errors.append(f"metadata.as_of: {exc}")
    try:
        ZoneInfo(meta.get("timezone", ""))
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        errors.append("metadata.timezone: valid IANA timezone required")

    indexes = {}
    for name in COLLECTIONS:
        rows = data.get(name, [])
        if not isinstance(rows, list):
            errors.append(f"{name}: expected an array")
            indexes[name] = {}
            continue
        index = {}
        for i, row in enumerate(rows):
            path = f"{name}[{i}]"
            if not isinstance(row, dict):
                errors.append(f"{path}: expected an object")
                continue
            ident = row.get("id")
            if not isinstance(ident, str) or not ident.strip():
                errors.append(f"{path}.id: stable nonempty ID required")
            elif ident in index:
                errors.append(f"{path}.id: duplicate ID")
            else:
                index[ident] = row
        indexes[name] = index

    def required(row, fields, path):
        for field in fields:
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f"{path}.{field}: required nonempty string")

    def time_field(row, field, path, optional=False):
        if optional and row.get(field) is None:
            return None
        try:
            return _dt(row.get(field))
        except ValueError as exc:
            errors.append(f"{path}.{field}: {exc}")
            return None

    def permission(row, path):
        if not isinstance(row.get("authorized"), bool):
            errors.append(f"{path}.authorized: explicit boolean required")
        if not _choice(row.get("visibility"), VISIBILITIES):
            errors.append(f"{path}.visibility: explicit visibility required")
        audiences = row.get("audiences")
        if not isinstance(audiences, list) or not audiences or any(not _choice(a, AUDIENCES) for a in audiences):
            errors.append(f"{path}.audiences: explicit audience list required")

    def references(row, field, target, path, nonempty=False):
        values = row.get(field, [])
        if not isinstance(values, list) or (nonempty and not values):
            errors.append(f"{path}.{field}: {'nonempty ' if nonempty else ''}reference array required")
            return []
        for ref in values:
            if not isinstance(ref, str) or ref not in indexes[target]:
                errors.append(f"{path}.{field}: unresolved reference")
        if any(not isinstance(x, str) for x in values):
            return []
        if len(set(values)) != len(values):
            errors.append(f"{path}.{field}: duplicate reference")
        return values

    def company_evidence(row, excerpt_ids, path):
        for ref in excerpt_ids:
            excerpt = _lookup(indexes["excerpts"], ref)
            source = _lookup(indexes["sources"], excerpt.get("source_id"))
            if source and source.get("company") != row.get("company"):
                errors.append(f"{path}: source company does not match asserted company")

    for i, source in enumerate(indexes["sources"].values()):
        path = f"sources[{i}]"
        required(source, ("company", "title", "kind", "url", "version", "content_sha256"), path)
        permission(source, path)
        times = {}
        for field in ("published_at", "available_at", "version_at", "retrieved_at"):
            if field != "retrieved_at" and source.get(field) is None:
                times[field] = None
                warnings.append(f"{path}.{field}: unknown time; source excluded from historical projections")
            else:
                times[field] = time_field(source, field, path)
        if times["available_at"] and any(times[f] and times[f] > times["available_at"]
                                        for f in ("published_at", "version_at")):
            errors.append(f"{path}: publication/version cannot be after first availability")
        if times["retrieved_at"] and times["version_at"] and times["retrieved_at"] < times["version_at"]:
            errors.append(f"{path}: retrieval cannot precede the material version")
        if not isinstance(source.get("content_sha256"), str) or not re.fullmatch(r"[a-fA-F0-9]{64}", source["content_sha256"]):
            errors.append(f"{path}.content_sha256: SHA-256 fingerprint required")
        if not _choice(source.get("status"), {"active", "retracted", "superseded"}):
            errors.append(f"{path}.status: invalid source state")
        if source.get("status") != "active":
            time_field(source, "invalidated_at", path)
        for field in ("material_id", "independence_key", "published_date_raw", "time_precision", "time_note", "fingerprint_scope"):
            if field in source:
                required(source, (field,), path)

    for i, excerpt in enumerate(indexes["excerpts"].values()):
        path = f"excerpts[{i}]"
        required(excerpt, ("source_id", "locator", "text"), path)
        if not isinstance(excerpt.get("source_id"), str) or excerpt["source_id"] not in indexes["sources"]:
            errors.append(f"{path}.source_id: unresolved reference")
        if "content_sha256" in excerpt and isinstance(excerpt.get("text"), str):
            if excerpt["content_sha256"] != _text_digest(excerpt["text"]):
                errors.append(f"{path}.content_sha256: excerpt fingerprint mismatch")

    for i, claim in enumerate(indexes["claims"].values()):
        path = f"claims[{i}]"
        required(claim, ("company", "text", "period", "definition"), path)
        refs = references(claim, "excerpt_ids", "excerpts", path, True)
        company_evidence(claim, refs, path)
        if not _choice(claim.get("status"), {"confirmed", "pending"}):
            errors.append(f"{path}.status: confirmed or pending required")
        if _has_permission(claim):
            permission(claim, path)
        for field in ("valid_from", "valid_until"):
            time_field(claim, field, path, True)
        groups = claim.get("support_groups")
        if groups is not None:
            if not isinstance(groups, list) or not groups or any(not isinstance(g, list) or not g for g in groups):
                errors.append(f"{path}.support_groups: nonempty groups required")
            else:
                seen_keys = set()
                for group in groups:
                    keys = set()
                    for ref in group:
                        if not isinstance(ref, str) or ref not in refs:
                            errors.append(f"{path}.support_groups: group must use declared excerpt IDs")
                            continue
                        ex = _lookup(indexes["excerpts"], ref)
                        src = _lookup(indexes["sources"], ex.get("source_id"))
                        key = src.get("independence_key")
                        if len(groups) > 1 and (not isinstance(key, str) or not key):
                            errors.append(f"{path}.support_groups: explicit source independence_key required")
                        if isinstance(key, str) and key:
                            keys.add(key)
                    if seen_keys & keys:
                        errors.append(f"{path}.support_groups: repeated same-origin support is not independent")
                    seen_keys.update(keys)
                if set(refs) != {x for group in groups for x in group if isinstance(x, str)}:
                    errors.append(f"{path}.support_groups: must cover declared excerpt IDs")

    for i, topic in enumerate(indexes["topics"].values()):
        path = f"topics[{i}]"
        required(topic, ("title",), path)
        permission(topic, path)
        references(topic, "claim_ids", "claims", path)
        priority = topic.get("base_priority", 0)
        if isinstance(priority, bool) or not isinstance(priority, (int, float)) or not 0 <= priority <= 5:
            errors.append(f"{path}.base_priority: number between 0 and 5 required")
        for field in ("analysis", "actions", "gaps"):
            if not isinstance(topic.get(field, []), list):
                errors.append(f"{path}.{field}: expected an array")
                continue
            for j, node in enumerate(topic.get(field, [])):
                subpath = f"{path}.{field}[{j}]"
                if isinstance(node, str) and field != "analysis":
                    continue
                if not isinstance(node, dict):
                    errors.append(f"{subpath}: expected a content object")
                    continue
                required(node, ("id", "text"), subpath)
                if _has_permission(node):
                    permission(node, subpath)
                references(node, "claim_ids", "claims", subpath, True)
                if field == "analysis" and not _choice(node.get("type"), {"analysis", "hypothesis"}):
                    errors.append(f"{subpath}.type: analysis or hypothesis required")

    for i, question in enumerate(indexes["questions"].values()):
        path = f"questions[{i}]"
        required(question, ("topic_id", "text"), path)
        permission(question, path)
        if not isinstance(question.get("topic_id"), str) or question["topic_id"] not in indexes["topics"]:
            errors.append(f"{path}.topic_id: unresolved reference")
        if not _choice(question.get("origin"), {"anticipated", "actual", "paraphrase"}):
            errors.append(f"{path}.origin: anticipated, actual or paraphrase required")
        references(question, "trigger_claim_ids", "claims", path, question.get("origin") == "anticipated")
        if not isinstance(question.get("follow_ups", []), list) or any(not isinstance(x, str) for x in question.get("follow_ups", [])):
            errors.append(f"{path}.follow_ups: string array required")

    for i, answer in enumerate(indexes["answers"].values()):
        path = f"answers[{i}]"
        required(answer, ("question_id", "version"), path)
        permission(answer, path)
        if not isinstance(answer.get("question_id"), str) or answer["question_id"] not in indexes["questions"]:
            errors.append(f"{path}.question_id: unresolved reference")
        statements = answer.get("statements")
        if not isinstance(statements, list) or not statements:
            errors.append(f"{path}.statements: nonempty statement array required")
        else:
            for j, statement in enumerate(statements):
                subpath = f"{path}.statements[{j}]"
                if not isinstance(statement, dict):
                    errors.append(f"{subpath}: expected an object")
                    continue
                required(statement, ("text",), subpath)
                if _has_permission(statement):
                    permission(statement, subpath)
                refs = references(statement, "claim_ids", "claims", subpath, True)
                kind = statement.get("kind", "fact")
                if not _choice(kind, {"fact", "company_position", "analysis"}):
                    errors.append(f"{subpath}.kind: invalid statement kind")
                if _choice(kind, {"fact", "company_position"}):
                    required(statement, ("company",), subpath)
                    if any(indexes["claims"].get(ref, {}).get("company") != statement.get("company") for ref in refs):
                        errors.append(f"{subpath}: peer evidence cannot support another company's fact or position")
        for field in ("valid_from", "valid_until"):
            time_field(answer, field, path, True)
        review = answer.get("review", {})
        if not isinstance(review, dict):
            errors.append(f"{path}.review: expected an object")
        elif "status" in review and not _choice(review["status"], {"reviewed", "pending"}):
            errors.append(f"{path}.review.status: reviewed or pending required")
        elif review.get("status") == "reviewed":
            required(review, ("reviewer", "scope", "digest"), f"{path}.review")
            time_field(review, "at", f"{path}.review")
            time_field(review, "valid_until", f"{path}.review", True)

    for i, meeting in enumerate(indexes["meetings"].values()):
        path = f"meetings[{i}]"
        required(meeting, ("title",), path)
        permission(meeting, path)
        time_field(meeting, "at", path)
        references(meeting, "question_ids", "questions", path)

    for i, feedback in enumerate(indexes["feedback"].values()):
        path = f"feedback[{i}]"
        for field, target in (("question_id", "questions"), ("meeting_id", "meetings"), ("excerpt_id", "excerpts")):
            if not isinstance(feedback.get(field), str) or feedback[field] not in indexes[target]:
                errors.append(f"{path}.{field}: unresolved reference")
        if not _choice(feedback.get("kind"), {"actual", "anticipated", "paraphrase"}):
            errors.append(f"{path}.kind: invalid feedback kind")
        confirmation = feedback.get("confirmation", {})
        if not isinstance(confirmation, dict) or not _choice(confirmation.get("status"), {"confirmed", "pending", "revoked"}):
            errors.append(f"{path}.confirmation: explicit confirmation status required")
        elif confirmation["status"] in {"confirmed", "revoked"}:
            required(confirmation, ("reviewer",), f"{path}.confirmation")
            confirmed_at = time_field(confirmation, "at", f"{path}.confirmation")
            meeting = _lookup(indexes["meetings"], feedback.get("meeting_id"))
            try:
                if confirmed_at and meeting and confirmed_at < _dt(meeting.get("at")):
                    errors.append(f"{path}.confirmation.at: confirmation cannot precede the meeting")
            except ValueError:
                pass

    for i, financial in enumerate(indexes["financials"].values()):
        path = f"financials[{i}]"
        required(financial, DEFINITIONS, path)
        refs = references(financial, "excerpt_ids", "excerpts", path, True)
        company_evidence(financial, refs, path)
        if _has_permission(financial):
            permission(financial, path)
        if not _choice(financial.get("kind"), {"actual", "consensus"}):
            errors.append(f"{path}.kind: actual or consensus required")
        try:
            _decimal(financial.get("value"))
        except ValueError as exc:
            errors.append(f"{path}.value: {exc}")
        if financial.get("kind") == "actual":
            time_field(financial, "released_at", path)
        else:
            time_field(financial, "snapshot_at", path)

    for i, event in enumerate(indexes["events"].values()):
        path = f"events[{i}]"
        when = time_field(event, "at", path)
        required(event, ("type", "target_id", "reviewer"), path)
        kind = event.get("type")
        if not _choice(kind, EVENT_TYPES):
            errors.append(f"{path}.type: unsupported event type")
            continue
        target = "sources" if kind.startswith("source_") else "feedback" if kind.startswith("feedback_") else "answers"
        if not isinstance(event.get("target_id"), str) or event["target_id"] not in indexes[target]:
            errors.append(f"{path}.target_id: unresolved reference")
        if kind == "answer_review":
            required(event, ("scope", "digest", "version"), path)
            if event.get("version") != _lookup(indexes["answers"], event.get("target_id")).get("version"):
                errors.append(f"{path}.version: review must bind the current answer version")
            time_field(event, "valid_until", path, True)
        if when and target == "feedback":
            feedback = _lookup(indexes["feedback"], event.get("target_id"))
            meeting = _lookup(indexes["meetings"], feedback.get("meeting_id"))
            try:
                if meeting and when < _dt(meeting.get("at")):
                    errors.append(f"{path}.at: feedback event cannot precede the meeting")
            except ValueError:
                pass
    return errors, warnings


def _effective_workspace(data, as_of):
    result = copy.deepcopy(data)
    indexes = {name: _index(result, name) for name in COLLECTIONS}
    for source in result.get("sources", []):
        if source["status"] != "active" and _dt(source["invalidated_at"]) > as_of:
            source["status"] = "active"
            source.pop("invalidated_at", None)
    for feedback in result.get("feedback", []):
        confirmation = feedback["confirmation"]
        if confirmation["status"] != "pending" and _dt(confirmation["at"]) > as_of:
            feedback["confirmation"] = {"status": "pending"}
    for answer in result.get("answers", []):
        review = answer.get("review", {})
        if review.get("status") == "reviewed" and _dt(review["at"]) > as_of:
            answer["review"] = {"status": "pending", "unavailable_future_review": True}
    for event in sorted(result.get("events", []), key=lambda e: (_dt(e["at"]), e["id"])):
        if _dt(event["at"]) > as_of:
            continue
        kind = event["type"]
        if kind.startswith("source_"):
            source = indexes["sources"][event["target_id"]]
            source["status"] = "retracted" if kind == "source_retract" else "superseded"
            source["invalidated_at"] = event["at"]
        elif kind.startswith("feedback_"):
            feedback = indexes["feedback"][event["target_id"]]
            current = feedback["confirmation"]
            if current.get("at") and _dt(current["at"]) > _dt(event["at"]):
                continue
            if current.get("at") == event["at"] and current["status"] == "revoked" and kind == "feedback_confirm":
                continue
            feedback["confirmation"] = {
                "status": "confirmed" if kind == "feedback_confirm" else "revoked",
                "reviewer": event["reviewer"], "at": event["at"]}
        elif kind == "answer_review":
            answer = indexes["answers"][event["target_id"]]
            current = answer.get("review", {})
            if current.get("at") and _dt(current["at"]) > _dt(event["at"]):
                continue
            answer["review"] = {
                "status": "reviewed", "reviewer": event["reviewer"], "at": event["at"],
                "scope": event["scope"], "digest": event["digest"],
                **({"valid_until": event["valid_until"]} if event.get("valid_until") else {})}
    return result


def _answer_digest(answer, data):
    claims, excerpts, sources = (_index(data, name) for name in ("claims", "excerpts", "sources"))
    question = _index(data, "questions")[answer["question_id"]]
    claim_ids = sorted({ref for s in answer.get("statements", []) for ref in s.get("claim_ids", [])}
                       | set(question.get("trigger_claim_ids", [])))
    dependencies = []
    for ident in claim_ids:
        claim = claims[ident]
        evidence = []
        for ref in claim["excerpt_ids"]:
            ex = excerpts[ref]
            src = sources[ex["source_id"]]
            evidence.append({"excerpt": {k: ex.get(k) for k in ("id", "source_id", "locator", "text")},
                             "source": {k: src.get(k) for k in
                                        ("id", "material_id", "company", "version", "version_at", "available_at", "published_at",
                                         "content_sha256", "status", "invalidated_at", "authorized",
                                         "visibility", "audiences", "independence_key")}})
        dependencies.append({"claim": {k: claim.get(k) for k in
                                        ("id", "company", "text", "period", "definition", "status",
                                        "valid_from", "valid_until", "excerpt_ids", "support_groups",
                                        "authorized", "visibility", "audiences")},
                             "evidence": evidence})
    body = {k: answer.get(k) for k in ("id", "question_id", "version", "statements", "valid_from",
                                      "valid_until", "authorized", "visibility", "audiences")}
    question_body = {k: question.get(k) for k in ("id", "topic_id", "text", "origin", "trigger_claim_ids",
                                                "follow_ups", "authorized", "visibility", "audiences")}
    return _digest({"answer": body, "question": question_body, "dependencies": dependencies})


def answer_review_digest(answer, data, as_of=None):
    """Fingerprint the exact answer version and its full evidence dependencies."""
    errors, _ = validate_workspace(data)
    if errors:
        raise ValueError("Invalid workspace: " + "; ".join(errors))
    when = _dt(as_of or data["metadata"]["as_of"])
    effective = _effective_workspace(data, when)
    return _answer_digest(_index(effective, "answers").get(answer["id"], answer), effective)


def build_report(data, previous=None, mode="radar", audience=None, as_of=None):
    """Build a permission- and time-filtered report; never return the workspace."""
    errors, warnings = validate_workspace(data)
    if errors:
        raise ValueError("Invalid workspace: " + "; ".join(errors))
    if mode not in {"radar", "earnings", "meeting"}:
        raise ValueError("mode must be radar, earnings or meeting")
    meta = data["metadata"]
    target = audience or meta["audience"]
    if target not in AUDIENCES:
        raise ValueError("audience must be public or internal")
    cutoff_text = as_of or meta["as_of"]
    cutoff = _dt(cutoff_text)
    work = _effective_workspace(data, cutoff)
    indexes = {name: _index(work, name) for name in COLLECTIONS}
    allowed = set(meta["allowed_visibility"])
    permitted_sources = {ident: src for ident, src in indexes["sources"].items()
                         if _permission(src, target, allowed)}
    latest = {}
    for ident, src in permitted_sources.items():
        if not _source_known(src):
            continue
        if any(_dt(src[field]) > cutoff for field in ("published_at", "available_at", "version_at")):
            continue
        material = src.get("material_id", ident)
        key = (_dt(src["version_at"]), _dt(src["available_at"]), src["version"], ident)
        if material not in latest or key > latest[material][0]:
            latest[material] = (key, ident)

    source_states = {}
    for ident, src in permitted_sources.items():
        if not _source_known(src):
            state = "unknown_time"
        elif any(_dt(src[field]) > cutoff for field in ("published_at", "available_at", "version_at")):
            state = "after_as_of"
        elif latest.get(src.get("material_id", ident), (None, None))[1] != ident:
            state = "stale_version"
        elif src["status"] != "active" and _dt(src["invalidated_at"]) <= cutoff:
            state = src["status"]
        else:
            state = "active"
        source_states[ident] = state

    def excerpt_state(ident):
        return source_states.get(indexes["excerpts"][ident]["source_id"], "restricted")

    def citation(ident):
        ex = indexes["excerpts"][ident]
        src = indexes["sources"][ex["source_id"]]
        return {"excerpt_id": ident, "source_id": src["id"], "locator": ex["locator"],
                "text": ex["text"], "version": src["version"],
                "content_sha256": _text_digest(ex["text"])}

    claim_states, claim_evidence = {}, {}
    for ident, claim in indexes["claims"].items():
        groups = _groups(claim)
        eligible = [g for g in groups if all(excerpt_state(ref) == "active" for ref in g)]
        restricted = ((_has_permission(claim) and not _permission(claim, target, allowed))
                      or all(any(excerpt_state(ref) == "restricted" for ref in g) for g in groups))
        outside = ((claim.get("valid_from") and _dt(claim["valid_from"]) > cutoff)
                   or (claim.get("valid_until") and _dt(claim["valid_until"]) < cutoff))
        state = "restricted" if restricted else "outside_period" if outside else "pending" if claim["status"] != "confirmed" else "confirmed" if eligible else "unavailable"
        claim_states[ident] = state
        claim_evidence[ident] = sorted({ref for group in eligible for ref in group}) if state == "confirmed" else []

    def deps_ok(refs):
        return bool(refs) and all(claim_states.get(ref) == "confirmed" for ref in refs)

    def deps_public(refs):
        return all(claim_states.get(ref) != "restricted" for ref in refs)

    def node_permission(node):
        return _permission(node, target, allowed)

    def child_permission(node):
        return not _has_permission(node) or node_permission(node)

    feedback_groups = {}
    for feedback in work.get("feedback", []):
        question = indexes["questions"][feedback["question_id"]]
        meeting = indexes["meetings"][feedback["meeting_id"]]
        if not node_permission(question) or not node_permission(meeting):
            continue
        if _dt(meeting["at"]) > cutoff or excerpt_state(feedback["excerpt_id"]) != "active":
            continue
        if feedback["kind"] not in {"actual", "paraphrase"} or feedback["kind"] != question["origin"]:
            continue
        confirmation = feedback["confirmation"]
        if confirmation["status"] == "pending" or _dt(confirmation["at"]) > cutoff:
            continue
        key = (feedback["meeting_id"], feedback["kind"], " ".join(question["text"].split()).casefold())
        value = (confirmation["at"], feedback["id"], feedback)
        def feedback_order(item):
            return (_dt(item[0]), item[2]["confirmation"]["status"] == "revoked", item[1])
        if key not in feedback_groups or feedback_order(value) > feedback_order(feedback_groups[key]):
            feedback_groups[key] = value
    confirmed_origin_feedback = [v[2] for v in feedback_groups.values()
                                 if v[2]["confirmation"]["status"] == "confirmed"]
    confirmed_feedback = [feedback for feedback in confirmed_origin_feedback if feedback["kind"] == "actual"]
    confirmed_by_question = {}
    for feedback in confirmed_origin_feedback:
        confirmed_by_question.setdefault(feedback["question_id"], []).append(feedback)
    actual_by_question = {}
    for feedback in confirmed_feedback:
        actual_by_question.setdefault(feedback["question_id"], []).append(feedback)

    old_topics = {}
    previous_ok = (isinstance(previous, dict) and isinstance(previous.get("metadata"), dict)
                   and previous["metadata"].get("audience") == target
                   and previous["metadata"].get("subject_company") == meta["subject_company"]
                   and previous["metadata"].get("schema_version") == SCHEMA_VERSION)
    if previous is not None and not previous_ok:
        raise ValueError("previous report must have the same schema, audience and subject company")
    if previous_ok:
        if _dt(previous["metadata"]["as_of"]) > cutoff:
            raise ValueError("previous report cannot be later than current as_of")
        old_topics = {topic["id"]: topic for topic in previous.get("topics", [])}

    used_sources, topics = set(), []
    for topic in work.get("topics", []):
        if not node_permission(topic):
            continue
        facts, analysis, questions, answers, gaps = [], [], [], [], []
        for ref in topic.get("claim_ids", []):
            claim = indexes["claims"][ref]
            state = claim_states[ref]
            if state == "restricted":
                continue
            fact = {"id": ref, "company": claim["company"], "period": claim["period"],
                    "definition": claim["definition"], "status": state}
            if state == "confirmed":
                cites = [citation(ex) for ex in claim_evidence[ref]]
                fact.update(text=claim["text"], citations=cites,
                            evidence_digest=_digest({"claim": {k: claim[k] for k in
                                                               ("text", "company", "period", "definition", "status")},
                                                     "citations": cites}))
                used_sources.update(c["source_id"] for c in cites)
            else:
                fact["citations"] = []
                gaps.append("部分事实未满足截至时间、有效来源或人工核验要求。")
            facts.append(fact)
        for node in topic.get("analysis", []):
            if child_permission(node) and deps_ok(node["claim_ids"]):
                analysis.append({"id": node["id"], "text": node["text"], "type": node["type"],
                                 "claim_ids": node["claim_ids"]})
        topic_questions = [q for q in work.get("questions", []) if q["topic_id"] == topic["id"]]
        for question in topic_questions:
            refs = question.get("trigger_claim_ids", [])
            if not node_permission(question) or not deps_public(refs):
                continue
            actual = actual_by_question.get(question["id"], [])
            origin_records = confirmed_by_question.get(question["id"], [])
            # Anticipated wording is generated from evidence. Actual/paraphrased
            # wording is learned from an original record, so trigger claims alone
            # cannot establish that its text was known and cleared at the cutoff.
            eligible = deps_ok(refs) if question["origin"] == "anticipated" else bool(origin_records)
            item = {"id": question["id"], "origin": question["origin"],
                    "label": {"anticipated": "AI预拟", "actual": "真实问题（已确认）" if actual else "真实问题（待确认）", "paraphrase": "转述"}[question["origin"]],
                    "status": "ready" if eligible else "NeedsEvidence", "actual_question_count": len(actual),
                    "trigger_claim_ids": refs, "follow_ups": question.get("follow_ups", []) if eligible else [],
                    "citations": [citation(f["excerpt_id"]) for f in origin_records]}
            if eligible:
                item["text"] = question["text"]
            used_sources.update(c["source_id"] for c in item["citations"])
            questions.append(item)
            for answer in [a for a in work.get("answers", []) if a["question_id"] == question["id"]]:
                if not node_permission(answer):
                    continue
                if any(not child_permission(statement) for statement in answer["statements"]):
                    continue
                answer_refs = [ref for s in answer["statements"] for ref in s["claim_ids"]]
                if not deps_public(answer_refs):
                    continue
                valid_time = ((not answer.get("valid_from") or _dt(answer["valid_from"]) <= cutoff)
                              and (not answer.get("valid_until") or _dt(answer["valid_until"]) >= cutoff))
                supported = eligible and valid_time and deps_ok(answer_refs)
                review = answer.get("review", {})
                reviewed = (supported and review.get("status") == "reviewed"
                            and _dt(review["at"]) <= cutoff and review.get("digest") == _answer_digest(answer, work)
                            and (not review.get("valid_until") or _dt(review["valid_until"]) >= cutoff))
                status = "Reviewed" if reviewed else "NeedsReview" if review.get("status") == "reviewed" or review.get("unavailable_future_review") or not supported else "Draft"
                statements = []
                if supported:
                    for j, statement in enumerate(answer["statements"]):
                        cites = [citation(ex) for ref in statement["claim_ids"] for ex in claim_evidence[ref]]
                        used_sources.update(c["source_id"] for c in cites)
                        statements.append({"id": statement.get("id", f"{answer['id']}.s{j + 1}"),
                                           "text": statement["text"], "kind": statement.get("kind", "fact"),
                                           "company": statement.get("company"), "claim_ids": statement["claim_ids"],
                                           "citations": cites})
                answers.append({"id": answer["id"], "question_id": question["id"], "version": answer["version"],
                                "status": status, "statements": statements,
                                "review": {k: review[k] for k in ("reviewer", "at", "scope") if reviewed and k in review},
                                "gaps": [] if supported else ["答复支持或适用时间不足，需要复核。"]})
        def safe_items(field):
            result = []
            for node in topic.get(field, []):
                if isinstance(node, str):
                    result.append(node)
                elif child_permission(node) and deps_ok(node["claim_ids"]):
                    result.append({"id": node["id"], "text": node["text"], "claim_ids": node["claim_ids"]})
            return result
        gaps.extend(safe_items("gaps"))
        actual_count = sum(q["actual_question_count"] for q in questions)
        current = {f["id"]: f.get("evidence_digest", f["status"]) for f in facts}
        old = old_topics.get(topic["id"])
        before = {f["id"]: f.get("evidence_digest", f.get("status")) for f in old.get("facts", [])} if old else {}
        added, removed = sorted(set(current) - set(before)), sorted(set(before) - set(current))
        changed = sorted(ref for ref in current.keys() & before.keys() if current[ref] != before[ref])
        # Removed IDs from a previous report can become restricted; do not echo them.
        removed = [ref for ref in removed if claim_states.get(ref) != "restricted"]
        def changed_nodes(field, nodes):
            prior = {node["id"]: _digest(node) for node in old.get(field, [])} if old else {}
            return sorted(node["id"] for node in nodes if node["id"] not in prior or _digest(node) != prior[node["id"]])
        question_changes = changed_nodes("questions", questions)
        answer_changes = changed_nodes("answers", answers)
        change = {"status": "initial_baseline" if previous is None else "new_topic" if not old else "changed" if added or removed or changed or question_changes or answer_changes or actual_count != old.get("actual_question_count", 0) else "unchanged",
                  "baseline_as_of": previous["metadata"]["as_of"] if previous_ok else None,
                  "added_claim_ids": added, "removed_claim_ids": removed, "changed_claim_ids": changed,
                  "changed_question_ids": question_changes, "changed_answer_ids": answer_changes}
        reasons = ["人工设定基础优先级"]
        if actual_count:
            reasons.append("已确认真实问题")
        if previous is not None and (added or changed):
            reasons.append("相对上期有证据变化")
        score = min(10, topic.get("base_priority", 0) + min(actual_count, 3) + (1 if previous is not None and (added or changed) else 0))
        topics.append({"id": topic["id"], "title": topic["title"], "change": change, "facts": facts,
                       "analysis": analysis, "questions": questions, "answers": answers,
                       "actions": safe_items("actions"), "gaps": gaps,
                       "priority": {"score": score, "reasons": reasons, "meaning": "准备优先级；不是提问或股价变化概率"},
                       "actual_question_count": actual_count})

    financials = []
    for row in work.get("financials", []):
        if not child_permission(row):
            continue
        if not all(excerpt_state(ref) == "active" for ref in row["excerpt_ids"]):
            continue
        when = row["released_at"] if row["kind"] == "actual" else row["snapshot_at"]
        if _dt(when) > cutoff:
            continue
        financials.append(row)
    comparisons, earnings_gaps = [], []
    for actual in [row for row in financials if row["kind"] == "actual"]:
        candidates = [row for row in financials if row["kind"] == "consensus"
                      and all(row[field] == actual[field] for field in ("company", "metric", "period"))]
        before_release = [row for row in candidates if _dt(row["snapshot_at"]) < _dt(actual["released_at"])
                          and all(_dt(indexes["sources"][indexes["excerpts"][ref]["source_id"]][field]) <= _dt(row["snapshot_at"])
                                  for ref in row["excerpt_ids"] for field in ("available_at", "version_at"))]
        comparison = {field: actual[field] for field in DEFINITIONS}
        comparison.update(id=actual["id"], actual_id=actual["id"], actual=format(_decimal(actual["value"]), "f"),
                          consensus_id=None, consensus=None, difference=None, percentage_difference=None,
                          status="missing_consensus", citations=[citation(ref) for ref in actual["excerpt_ids"]])
        compatible = [row for row in before_release if all(row[field] == actual[field] for field in DEFINITIONS)]
        chosen = max(compatible or before_release, key=lambda row: (_dt(row["snapshot_at"]), row["id"]), default=None)
        if chosen:
            comparison.update(consensus_id=chosen["id"], consensus=format(_decimal(chosen["value"]), "f"), snapshot_at=chosen["snapshot_at"])
            comparison["consensus_definition"] = {field: chosen[field] for field in DEFINITIONS}
            comparison["citations"].extend(citation(ref) for ref in chosen["excerpt_ids"])
            if chosen not in compatible:
                comparison["status"] = "incomparable"
                comparison["mismatched_fields"] = [field for field in DEFINITIONS if chosen[field] != actual[field]]
            else:
                a, c = _decimal(actual["value"]), _decimal(chosen["value"])
                with localcontext() as ctx:
                    ctx.prec = 40
                    comparison["difference"] = format(a - c, "f")
                    if c == 0:
                        comparison["status"] = "zero_base"
                    elif c < 0:
                        comparison["status"] = "negative_base"
                    else:
                        comparison["status"] = "comparable"
                        comparison["percentage_difference"] = format((a - c) / c * Decimal(100), "f")
        elif candidates:
            comparison["status"] = "late_consensus"
        if comparison["status"] != "comparable":
            earnings_gaps.append({"id": actual["id"], "status": comparison["status"],
                                  "text": "预期快照、口径或分母条件不满足，百分比差异不可用。"})
        used_sources.update(c["source_id"] for c in comparison["citations"])
        comparisons.append(comparison)

    meetings = []
    for meeting in work.get("meetings", []):
        if not node_permission(meeting) or _dt(meeting["at"]) > cutoff:
            continue
        requested = set(meeting.get("question_ids", []))
        qs = [q for topic in topics for q in topic["questions"] if q["id"] in requested]
        ans = [a for topic in topics for a in topic["answers"] if a["question_id"] in requested]
        counts = sum(f["meeting_id"] == meeting["id"] for f in confirmed_feedback)
        meetings.append({"id": meeting["id"], "title": meeting["title"], "at": meeting["at"],
                         "questions": qs, "answers": ans, "actual_question_count": counts})

    source_rows = []
    for ident in sorted(used_sources):
        src = permitted_sources[ident]
        source_rows.append({k: src[k] for k in ("id", "company", "title", "kind", "url", "version",
                                               "published_at", "available_at", "version_at", "retrieved_at", "content_sha256")})
        source_rows[-1]["status"] = source_states[ident]
        for field in ("published_date_raw", "time_precision", "time_note", "fingerprint_scope"):
            if field in src:
                source_rows[-1][field] = src[field]
    data_gaps = [{"topic_id": t["id"], "text": "议题存在待补证或待复核项。"} for t in topics if t["gaps"]]
    data_gaps.extend(earnings_gaps)
    if not source_rows:
        data_gaps.append({"text": "暂无满足授权、受众、截至时间及证据条件的材料。"})
    if any(state == "unknown_time" for state in source_states.values()):
        data_gaps.append({"text": "部分材料无法证明发布时间、首次可用时间或版本时间，已排除。"})
    if mode == "earnings" and not comparisons:
        data_gaps.append({"text": "数据不足：需要获准来源的实际业绩及财报前一致预期快照。"})
    if mode == "meeting" and not meetings:
        data_gaps.append({"text": "暂无获准且可定位原始记录的会议材料。"})
    topics.sort(key=lambda topic: (-topic["priority"]["score"], topic["id"]))
    return {"metadata": {"schema_version": SCHEMA_VERSION, "id": meta["id"], "status": "Example" if meta["status"] == "Example" else "Draft",
                         "subject_company": meta["subject_company"], "as_of": cutoff_text,
                         "timezone": meta["timezone"], "audience": target, "mode": mode,
                         "semantic_review_required": True, "evidence_fingerprint": _digest(source_rows),
                         "previous_as_of": previous["metadata"]["as_of"] if previous_ok else None},
            "topics": topics, "sources": source_rows,
            "earnings": {"comparisons": comparisons, "gaps": earnings_gaps},
            "meeting_brief": {"meetings": meetings}, "data_gaps": data_gaps}


def _load(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_new_json(path, data):
    """Exclusive creation prevents overwriting reports, inputs, or history."""
    encoded = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with Path(path).open("x", encoding="utf-8") as handle:
        handle.write(encoded)


def snapshot_workspace(data):
    errors, _ = validate_workspace(data)
    if errors:
        raise ValueError("Invalid workspace: " + "; ".join(errors))
    result = copy.deepcopy(data)
    result["metadata"]["snapshot_parent_sha256"] = _digest(data)
    result["metadata"]["snapshot_created_at"] = datetime.now(timezone.utc).isoformat()
    return result


def append_event(data, event):
    """Append a validated event; originals remain unchanged and replayable."""
    result = copy.deepcopy(data)
    result.setdefault("events", []).append(copy.deepcopy(event))
    errors, _ = validate_workspace(result)
    if errors:
        raise ValueError("Invalid workspace event: " + "; ".join(errors))
    # A review records a human decision bound to the exact evidence at that time.
    if event["type"] == "answer_review":
        at = _dt(event["at"])
        effective = _effective_workspace(data, at)
        answer = _index(effective, "answers")[event["target_id"]]
        if event["digest"] != _answer_digest(answer, effective):
            raise ValueError("answer_review digest does not match the answer and evidence at event time")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate a local workspace")
    validate.add_argument("workspace")
    report = sub.add_parser("report", help="write a filtered report to a new file")
    report.add_argument("workspace")
    report.add_argument("output")
    report.add_argument("--previous")
    report.add_argument("--mode", choices=("radar", "earnings", "meeting"), default="radar")
    report.add_argument("--audience", choices=sorted(AUDIENCES))
    report.add_argument("--as-of")
    snapshot = sub.add_parser("snapshot", help="write a new historical workspace snapshot")
    snapshot.add_argument("workspace")
    snapshot.add_argument("output")
    event = sub.add_parser("event", help="append an event into a new workspace file")
    event.add_argument("workspace")
    event.add_argument("event_json")
    event.add_argument("output")
    args = parser.parse_args(argv)
    try:
        data = _load(args.workspace)
        if args.command == "validate":
            errors, warnings = validate_workspace(data)
            print(json.dumps({"valid": not errors, "errors": errors, "warnings": warnings}, ensure_ascii=False))
            return 1 if errors else 0
        if args.command == "report":
            output = build_report(data, _load(args.previous) if args.previous else None,
                                  args.mode, args.audience, args.as_of)
        elif args.command == "snapshot":
            output = snapshot_workspace(data)
        else:
            output = append_event(data, _load(args.event_json))
        write_new_json(args.output, output)
        print(json.dumps({"written": str(Path(args.output)), "command": args.command}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Errors contain field paths or static messages, never input document text.
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
