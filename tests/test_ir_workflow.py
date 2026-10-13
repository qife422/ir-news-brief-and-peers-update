from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from ir_workflow import answer_review_digest, build_report, validate_workspace  # noqa: E402


EXAMPLE = ROOT / "examples" / "ir-workspace.example.json"
CUTOFF = "2025-02-10T00:00:00Z"
BEFORE = "2025-01-01T00:00:00Z"
AFTER = "2025-03-01T00:00:00Z"
PUBLIC = {"authorized": True, "visibility": "public", "audiences": ["public", "internal"]}


def source(source_id: str, text: str, **updates: object) -> dict:
    value = {
        "id": source_id, "company": "Trip.com Group", "title": "Example disclosure",
        "kind": "example", "url": "https://example.com/" + source_id,
        "version": "1", "published_at": BEFORE, "available_at": BEFORE,
        "version_at": BEFORE, "retrieved_at": BEFORE,
        "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "status": "active", "independence_key": source_id, **copy.deepcopy(PUBLIC),
    }
    value.update(updates)
    return value


def excerpt(excerpt_id: str, source_id: str, text: str) -> dict:
    return {
        "id": excerpt_id, "source_id": source_id, "locator": "Example paragraph 1",
        "text": text, "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def workspace() -> dict:
    """A small declared Example, not a factual claim about either company."""
    quote = "Example: the company disclosed an AI booking feature."
    return {
        "metadata": {
            "schema_version": "1.0", "id": "example-workspace", "label": "Example",
            "status": "Example", "subject_company": "Trip.com Group", "as_of": CUTOFF,
            "timezone": "UTC", "audience": "public", "allowed_visibility": ["public"],
        },
        "sources": [source("s-public", quote)],
        "excerpts": [excerpt("e-public", "s-public", quote)],
        "claims": [{
            "id": "c-public", "company": "Trip.com Group", "text": quote,
            "period": "2024Q4", "definition": "Product feature disclosure",
            "excerpt_ids": ["e-public"], "status": "confirmed",
        }],
        "topics": [{
            "id": "t-ai", "title": "AI distribution", "claim_ids": ["c-public"],
            "analysis": [{"id": "h-ai", "text": "Could distribution costs change?",
                          "type": "hypothesis", "claim_ids": ["c-public"]}],
            "actions": ["Prepare disclosed cost indicators"], "gaps": ["Cost impact unavailable"],
            "base_priority": 2, **copy.deepcopy(PUBLIC),
        }],
        "questions": [{
            "id": "q-ai", "topic_id": "t-ai", "text": "How could AI affect acquisition costs?",
            "origin": "anticipated", "trigger_claim_ids": ["c-public"],
            "follow_ups": ["Which disclosed indicators can verify the effect?"],
            **copy.deepcopy(PUBLIC),
        }],
        "answers": [{
            "id": "a-ai", "question_id": "q-ai", "version": "1",
            "statements": [{"text": quote, "claim_ids": ["c-public"],
                            "kind": "fact", "company": "Trip.com Group"}],
            "valid_from": BEFORE, "valid_until": "2025-04-01T00:00:00Z",
            "review": {"status": "pending"}, **copy.deepcopy(PUBLIC),
        }],
        "feedback": [], "financials": [], "meetings": [], "events": [],
    }


def add_evidence(data: dict, evidence_id: str, text: str, **source_updates: object) -> str:
    source_id, excerpt_id, claim_id = (prefix + "-" + evidence_id for prefix in ("s", "e", "c"))
    data["sources"].append(source(source_id, text, **source_updates))
    data["excerpts"].append(excerpt(excerpt_id, source_id, text))
    data["claims"].append({
        "id": claim_id, "company": "Trip.com Group", "text": text,
        "period": "2024Q4", "definition": "Example evidence", "excerpt_ids": [excerpt_id],
        "status": "confirmed",
    })
    return claim_id


def serialized(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


class WorkflowValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = workspace()

    def assert_invalid(self, data: dict) -> None:
        errors, _ = validate_workspace(data)
        self.assertTrue(errors, "Malformed workspace was accepted")

    def test_minimum_example_is_valid(self) -> None:
        errors, _ = validate_workspace(self.data)
        self.assertEqual(errors, [])

    def test_shipped_example_is_valid(self) -> None:
        errors, _ = validate_workspace(json.loads(EXAMPLE.read_text(encoding="utf-8")))
        self.assertEqual(errors, [])

    def test_unknown_excerpt_cannot_support_a_claim(self) -> None:
        self.data["claims"][0]["excerpt_ids"] = ["e-missing"]
        self.assert_invalid(self.data)

    def test_unknown_claim_cannot_support_an_analysis(self) -> None:
        self.data["topics"][0]["analysis"][0]["claim_ids"] = ["c-missing"]
        self.assert_invalid(self.data)

    def test_unknown_claim_cannot_support_a_question(self) -> None:
        self.data["questions"][0]["trigger_claim_ids"] = ["c-missing"]
        self.assert_invalid(self.data)

    def test_unknown_claim_cannot_support_an_answer(self) -> None:
        self.data["answers"][0]["statements"][0]["claim_ids"] = ["c-missing"]
        self.assert_invalid(self.data)

    def test_duplicate_stable_ids_are_rejected(self) -> None:
        self.data["claims"].append(copy.deepcopy(self.data["claims"][0]))
        self.assert_invalid(self.data)

    def test_excerpt_fingerprint_mismatch_is_rejected(self) -> None:
        self.data["excerpts"][0]["text"] = "Changed evidence without updating its fingerprint"
        self.assert_invalid(self.data)

    def test_invalid_timezone_is_rejected(self) -> None:
        self.data["metadata"]["timezone"] = "Mars/Olympus"
        self.assert_invalid(self.data)

    def test_naive_as_of_is_rejected(self) -> None:
        self.data["metadata"]["as_of"] = "2025-02-10T00:00:00"
        self.assert_invalid(self.data)

    def test_unknown_event_target_is_rejected(self) -> None:
        self.data["events"] = [{"id": "ev-1", "at": BEFORE, "type": "source_retract",
                                 "target_id": "s-missing", "reviewer": "Example reviewer"}]
        self.assert_invalid(self.data)

    def test_peer_fact_cannot_be_relabelled_as_subject_company_position(self) -> None:
        self.data["claims"][0]["company"] = "Booking Holdings"
        self.data["answers"][0]["statements"][0]["kind"] = "company_position"
        self.assert_invalid(self.data)

    def test_duplicate_provenance_is_not_independent_support(self) -> None:
        self.data["sources"].append(source("s-copy", "Repeated release", independence_key="s-public"))
        self.data["excerpts"].append(excerpt("e-copy", "s-copy", "Repeated release"))
        self.data["claims"][0]["excerpt_ids"].append("e-copy")
        self.data["claims"][0]["support_groups"] = [["e-public"], ["e-copy"]]
        self.assert_invalid(self.data)


class WorkflowOutputBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = workspace()

    def report(self, **options: object) -> dict:
        return build_report(self.data, **options)

    def add_dependent_content(self, claim_id: str, marker: str) -> None:
        self.data["topics"][0]["claim_ids"].append(claim_id)
        self.data["topics"][0]["analysis"].append({
            "id": "h-secret", "text": marker + " derived analysis", "type": "analysis",
            "claim_ids": [claim_id],
        })
        self.data["topics"][0]["actions"].append({
            "id": "action-secret", "text": marker + " derived action", "claim_ids": [claim_id],
        })
        self.data["questions"].append({
            "id": "q-secret", "topic_id": "t-ai", "text": marker + " derived question",
            "origin": "anticipated", "trigger_claim_ids": [claim_id],
            "follow_ups": [marker + " follow-up"], **copy.deepcopy(PUBLIC),
        })
        self.data["answers"].append({
            "id": "a-secret", "question_id": "q-secret", "version": "1",
            "statements": [{"text": marker + " derived answer", "claim_ids": [claim_id],
                            "kind": "fact", "company": "Trip.com Group"}],
            "valid_from": BEFORE, "valid_until": AFTER, "review": {"status": "pending"},
            **copy.deepcopy(PUBLIC),
        })

    def assert_marker_absent(self, report: dict, marker: str) -> None:
        self.assertNotIn(marker, serialized(report), "Restricted evidence or a declared derivative leaked")

    def test_future_source_and_declared_derivatives_are_excluded(self) -> None:
        marker = "POST_RELEASE_UNIQUE_92731"
        claim_id = add_evidence(self.data, "future", marker, published_at=AFTER,
                                available_at=AFTER, version_at=AFTER, retrieved_at=AFTER)
        self.add_dependent_content(claim_id, marker)
        self.assert_marker_absent(self.report(), marker)

    def test_unknown_available_time_is_excluded_and_reported_as_gap(self) -> None:
        marker = "UNKNOWN_TIME_UNIQUE_73615"
        claim_id = add_evidence(self.data, "unknown", marker, available_at=None, version_at=None)
        self.add_dependent_content(claim_id, marker)
        report = self.report()
        self.assert_marker_absent(report, marker)
        self.assertTrue(report["data_gaps"], "Unknown availability was silently discarded")

    def test_old_url_uses_only_version_available_at_historical_cutoff(self) -> None:
        self.data["sources"][0]["material_id"] = "material-ai"
        marker = "LATER_BODY_UNIQUE_51327"
        claim_id = add_evidence(self.data, "v2", marker, material_id="material-ai", version="2",
                                url=self.data["sources"][0]["url"], published_at=BEFORE,
                                available_at=AFTER, version_at=AFTER, retrieved_at=AFTER)
        self.add_dependent_content(claim_id, marker)
        historical = self.report()
        self.assert_marker_absent(historical, marker)
        facts = {fact["id"] for topic in historical["topics"] for fact in topic["facts"]}
        self.assertIn("c-public", facts)
        current = self.report(as_of="2025-03-02T00:00:00Z")
        facts = {fact["id"] for topic in current["topics"] for fact in topic["facts"]
                 if fact["status"] == "confirmed"}
        self.assertNotIn("c-public", facts, "Superseded material version remained current evidence")
        self.assertIn(claim_id, facts)

    def test_unauthorized_public_input_and_derivatives_are_excluded(self) -> None:
        marker = "UNAUTHORIZED_UNIQUE_86235"
        claim_id = add_evidence(self.data, "unauthorized", marker, authorized=False)
        self.add_dependent_content(claim_id, marker)
        self.assert_marker_absent(self.report(), marker)

    def test_internal_input_and_derivatives_are_absent_from_full_public_json(self) -> None:
        marker = "INTERNAL_UNIQUE_99375_VALUE_314159"
        claim_id = add_evidence(self.data, "internal", marker, visibility="internal", audiences=["internal"])
        self.data["metadata"]["allowed_visibility"] = ["public", "internal"]
        self.add_dependent_content(claim_id, marker)
        self.assert_marker_absent(self.report(audience="public"), marker)
        self.assertIn(marker, serialized(self.report(audience="internal")))

    def test_licensed_content_obeys_explicit_output_audience(self) -> None:
        marker = "LICENSED_UNIQUE_18524"
        claim_id = add_evidence(self.data, "licensed", marker, visibility="licensed", audiences=["internal"])
        self.data["metadata"]["allowed_visibility"] = ["public", "licensed"]
        self.add_dependent_content(claim_id, marker)
        self.assert_marker_absent(self.report(audience="public"), marker)
        self.assertIn(marker, serialized(self.report(audience="internal")))

    def test_free_text_node_requires_its_own_authorization(self) -> None:
        marker = "PRIVATE_ANSWER_UNIQUE_19375"
        answer = self.data["answers"][0]
        answer["statements"][0]["text"] = marker
        answer["authorized"] = False
        self.assert_marker_absent(self.report(), marker)

    def test_internal_topic_free_text_is_not_exported_with_public_facts(self) -> None:
        marker = "PRIVATE_TOPIC_ACTION_UNIQUE_19953"
        topic = self.data["topics"][0]
        topic.update(visibility="internal", audiences=["internal"])
        topic["actions"] = [marker]
        self.data["metadata"]["allowed_visibility"] = ["public", "internal"]
        self.assert_marker_absent(self.report(audience="public"), marker)

    def test_output_generation_preserves_input_records(self) -> None:
        original = copy.deepcopy(self.data)
        self.report()
        self.assertEqual(self.data, original)

    def test_identical_frozen_input_produces_identical_report(self) -> None:
        self.assertEqual(self.report(), self.report())


class WorkflowFeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = workspace()
        question = copy.deepcopy(self.data["questions"][0])
        question.update(id="q-actual", origin="actual")
        self.data["questions"].append(question)
        add_evidence(self.data, "record", question["text"])
        self.data["meetings"] = [{
            "id": "m-1", "title": "Example meeting", "at": BEFORE,
            "question_ids": ["q-actual"], **copy.deepcopy(PUBLIC),
        }]
        self.data["feedback"] = [{
            "id": "f-1", "question_id": "q-actual", "meeting_id": "m-1",
            "kind": "actual", "excerpt_id": "e-record",
            "confirmation": {"status": "confirmed", "reviewer": "Example reviewer", "at": BEFORE},
        }]

    def count(self, **options: object) -> int:
        report = build_report(self.data, **options)
        topic = next(item for item in report["topics"] if item["id"] == "t-ai")
        return topic["actual_question_count"]

    def test_only_confirmed_actual_question_with_record_is_counted(self) -> None:
        self.assertEqual(self.count(), 1)
        for origin in ("anticipated", "paraphrase"):
            with self.subTest(origin=origin):
                self.data["questions"][1]["origin"] = origin
                self.assertEqual(self.count(), 0)

    def test_unconfirmed_question_does_not_affect_priority(self) -> None:
        self.data["feedback"][0]["confirmation"]["status"] = "pending"
        with_feedback = build_report(self.data)
        self.data["feedback"] = []
        without_feedback = build_report(self.data)
        self.assertEqual(with_feedback["topics"][0]["actual_question_count"], 0)
        self.assertEqual(with_feedback["topics"][0]["priority"], without_feedback["topics"][0]["priority"])

    def test_reimport_of_same_meeting_question_is_deduplicated(self) -> None:
        duplicate = copy.deepcopy(self.data["questions"][1])
        duplicate.update(id="q-actual-copy", text="  HOW could AI affect acquisition costs?  ")
        self.data["questions"].append(duplicate)
        self.data["meetings"][0]["question_ids"].append(duplicate["id"])
        feedback = copy.deepcopy(self.data["feedback"][0])
        feedback.update(id="f-copy", question_id=duplicate["id"])
        self.data["feedback"].append(feedback)
        self.assertEqual(self.count(), 1)

    def test_later_revocation_cancels_all_duplicates_of_natural_key(self) -> None:
        duplicate = copy.deepcopy(self.data["feedback"][0])
        duplicate.update(id="f-copy")
        self.data["feedback"].append(duplicate)
        revoke = copy.deepcopy(self.data["feedback"][0])
        revoke.update(id="f-revoked", confirmation={
            "status": "revoked", "reviewer": "Example reviewer", "at": "2025-02-01T00:00:00Z",
        })
        self.data["feedback"].append(revoke)
        self.assertEqual(self.count(), 0)

    def test_future_revocation_does_not_change_historical_count(self) -> None:
        self.data["events"] = [{"id": "ev-revoke", "at": AFTER, "type": "feedback_revoke",
                                 "target_id": "f-1", "reviewer": "Example reviewer"}]
        self.assertEqual(self.count(), 1)
        self.assertEqual(self.count(as_of="2025-03-02T00:00:00Z"), 0)

    def test_same_timestamp_revocation_wins_over_confirmed_duplicate(self) -> None:
        confirmed = self.data["feedback"][0]
        confirmed["id"] = "f-zzz-confirmed"
        confirmed["confirmation"]["at"] = "2025-01-15T00:00:00Z"
        revoked = copy.deepcopy(confirmed)
        revoked.update(id="f-aaa-revoked", confirmation={
            "status": "revoked", "reviewer": "Example reviewer", "at": "2025-01-15T00:00:00Z",
        })
        self.data["feedback"].append(revoked)
        self.assertEqual(self.count(), 0)

    def test_confirmation_cannot_precede_the_original_meeting(self) -> None:
        self.data["meetings"][0]["at"] = "2025-01-10T00:00:00Z"
        errors, _ = validate_workspace(self.data)
        self.assertTrue(errors)

    def test_actual_question_citation_resolves_to_original_meeting_excerpt(self) -> None:
        report = build_report(self.data, mode="meeting")
        question = next(item for item in report["topics"][0]["questions"] if item["id"] == "q-actual")
        self.assertEqual(question["actual_question_count"], 1)
        self.assertEqual(len(question["citations"]), 1)
        citation = question["citations"][0]
        original = next(item for item in self.data["excerpts"] if item["id"] == "e-record")
        self.assertEqual(citation["excerpt_id"], original["id"])
        self.assertEqual(citation["text"], original["text"])
        self.assertEqual(citation["locator"], original["locator"])
        self.assertIn(citation["source_id"], {item["id"] for item in report["sources"]})

    def test_confirmed_internal_record_is_not_public_feedback(self) -> None:
        record = next(item for item in self.data["sources"] if item["id"] == "s-record")
        record.update(visibility="internal", audiences=["internal"])
        self.data["metadata"]["allowed_visibility"] = ["public", "internal"]
        self.assertEqual(self.count(audience="public"), 0)
        self.assertEqual(self.count(audience="internal"), 1)

    def test_confirmation_event_increases_count_and_revoke_restores_priority(self) -> None:
        self.data["feedback"][0]["confirmation"]["status"] = "pending"
        baseline = build_report(self.data)
        self.data["events"] = [{"id": "ev-confirm", "at": "2025-01-10T00:00:00Z",
                                 "type": "feedback_confirm", "target_id": "f-1",
                                 "reviewer": "Example reviewer"}]
        confirmed = build_report(self.data)
        self.assertEqual(confirmed["topics"][0]["actual_question_count"], 1)
        self.assertGreater(confirmed["topics"][0]["priority"]["score"],
                           baseline["topics"][0]["priority"]["score"])
        self.data["events"].append({"id": "ev-revoke", "at": "2025-01-20T00:00:00Z",
                                     "type": "feedback_revoke", "target_id": "f-1",
                                     "reviewer": "Example reviewer"})
        revoked = build_report(self.data)
        self.assertEqual(revoked["topics"][0]["actual_question_count"], 0)
        self.assertEqual(revoked["topics"][0]["priority"], baseline["topics"][0]["priority"])


class WorkflowReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = workspace()

    def review(self, at: str = BEFORE) -> None:
        answer = self.data["answers"][0]
        answer["review"] = {
            "status": "reviewed", "reviewer": "Example reviewer", "at": at, "scope": "public",
            "digest": answer_review_digest(answer, self.data, as_of=at),
        }

    def answer(self, report: dict) -> dict | None:
        return next((answer for topic in report["topics"] for answer in topic["answers"]
                     if answer["id"] == "a-ai"), None)

    def test_valid_review_is_recognized(self) -> None:
        self.review()
        answer = self.answer(build_report(self.data))
        self.assertIsNotNone(answer)
        self.assertEqual(answer["status"], "Reviewed")

    def test_answer_edit_invalidates_old_review_digest(self) -> None:
        self.review()
        self.data["answers"][0]["statements"][0]["text"] = "Revised answer wording"
        answer = self.answer(build_report(self.data))
        self.assertIsNotNone(answer)
        self.assertEqual(answer["status"], "NeedsReview")

    def test_future_review_does_not_approve_historical_answer(self) -> None:
        self.review(at=AFTER)
        answer = self.answer(build_report(self.data))
        self.assertIsNotNone(answer)
        self.assertNotEqual(answer["status"], "Reviewed")

    def test_expired_review_requires_new_review(self) -> None:
        self.review()
        self.data["answers"][0]["review"]["valid_until"] = "2025-02-01T00:00:00Z"
        answer = self.answer(build_report(self.data))
        self.assertIsNotNone(answer)
        self.assertEqual(answer["status"], "NeedsReview")

    def test_retracted_only_support_cannot_keep_reviewed_answer(self) -> None:
        self.review()
        self.data["events"] = [{"id": "ev-retract", "at": "2025-01-15T00:00:00Z",
                                 "type": "source_retract", "target_id": "s-public",
                                 "reviewer": "Example reviewer"}]
        report = build_report(self.data)
        answer = self.answer(report)
        self.assertTrue(answer is None or answer["status"] != "Reviewed")
        self.assertTrue(report["data_gaps"], "Withdrawn sole support was not surfaced")
        facts = {fact["id"] for topic in report["topics"] for fact in topic["facts"]
                 if fact["status"] == "confirmed"}
        self.assertNotIn("c-public", facts)

    def test_independent_complete_support_preserves_fact_but_expires_old_review(self) -> None:
        add_evidence(self.data, "independent", "Example independent complete disclosure")
        claim = self.data["claims"][0]
        claim["excerpt_ids"].append("e-independent")
        claim["support_groups"] = [["e-public"], ["e-independent"]]
        self.review()
        self.data["events"] = [{"id": "ev-retract", "at": "2025-01-15T00:00:00Z",
                                 "type": "source_retract", "target_id": "s-public",
                                 "reviewer": "Example reviewer"}]
        report = build_report(self.data)
        facts = {fact["id"] for topic in report["topics"] for fact in topic["facts"]
                 if fact["status"] == "confirmed"}
        self.assertIn("c-public", facts)
        answer = self.answer(report)
        self.assertIsNotNone(answer)
        self.assertEqual(answer["status"], "NeedsReview")
        self.assertNotEqual(answer_review_digest(self.data["answers"][0], self.data),
                            self.data["answers"][0]["review"]["digest"])

    def test_future_retraction_does_not_invalidate_past_review(self) -> None:
        self.review()
        self.data["events"] = [{"id": "ev-retract", "at": AFTER, "type": "source_retract",
                                 "target_id": "s-public", "reviewer": "Example reviewer"}]
        answer = self.answer(build_report(self.data))
        self.assertIsNotNone(answer)
        self.assertEqual(answer["status"], "Reviewed")

    def test_base_retracted_source_can_be_replayed_before_its_invalidation(self) -> None:
        self.data["sources"][0].update(status="retracted", invalidated_at=AFTER)
        self.review()
        historical = build_report(self.data)
        answer = self.answer(historical)
        self.assertIsNotNone(answer)
        self.assertEqual(answer["status"], "Reviewed")
        current = build_report(self.data, as_of="2025-03-02T00:00:00Z")
        answer = self.answer(current)
        self.assertTrue(answer is None or answer["status"] != "Reviewed")


class WorkflowFinancialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = workspace()
        add_evidence(self.data, "actual", "Example actual revenue is 120 million USD")
        add_evidence(self.data, "consensus", "Example pre-release revenue consensus is 100 million USD")
        definition = {
            "company": "Trip.com Group", "metric": "revenue", "period": "2024Q4",
            "currency": "USD", "unit": "million", "accounting_basis": "GAAP",
            "share_basis": "not_applicable", "definition_id": "net_revenue",
        }
        self.data["financials"] = [
            {"id": "fin-actual", "kind": "actual", "value": "120", "excerpt_ids": ["e-actual"],
             "released_at": "2025-02-01T00:00:00Z", **definition},
            {"id": "fin-consensus", "kind": "consensus", "value": "100",
             "excerpt_ids": ["e-consensus"], "snapshot_at": "2025-01-15T00:00:00Z", **definition},
        ]

    def comparison(self) -> dict:
        report = build_report(self.data, mode="earnings")
        rows = report["earnings"]["comparisons"]
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_comparable_values_have_exact_decimal_difference_and_percentage(self) -> None:
        comparison = self.comparison()
        self.assertEqual(comparison["status"], "comparable")
        self.assertEqual(Decimal(comparison["difference"]), Decimal("20"))
        self.assertEqual(Decimal(comparison["percentage_difference"]), Decimal("20"))
        self.assertEqual(comparison["actual"], "120")
        self.assertEqual(comparison["consensus"], "100")

    def test_decimal_arithmetic_does_not_introduce_binary_float_artifacts(self) -> None:
        self.data["financials"][0]["value"] = "0.3"
        self.data["financials"][1]["value"] = "0.1"
        comparison = self.comparison()
        self.assertEqual(comparison["difference"], "0.2")
        self.assertEqual(Decimal(comparison["percentage_difference"]), Decimal("200"))

    def test_incompatible_financial_definitions_never_produce_difference(self) -> None:
        for field, value in (
            ("accounting_basis", "adjusted"), ("currency", "CNY"), ("unit", "thousand"),
            ("share_basis", "ADS"), ("definition_id", "gross_bookings"),
        ):
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                data["financials"][1][field] = value
                comparison = build_report(data, mode="earnings")["earnings"]["comparisons"][0]
                self.assertEqual(comparison["status"], "incomparable")
                self.assertIsNone(comparison["difference"])
                self.assertIsNone(comparison["percentage_difference"])
                self.assertIn(field, comparison["mismatched_fields"])
                self.assertEqual(data["financials"][1][field], value)

    def test_revenue_and_bookings_are_distinct_metrics(self) -> None:
        self.data["financials"][1]["metric"] = "gross_bookings"
        comparison = self.comparison()
        self.assertEqual(comparison["status"], "missing_consensus")
        self.assertIsNone(comparison["difference"])
        self.assertIsNone(comparison["percentage_difference"])

    def test_different_period_is_not_used_as_consensus(self) -> None:
        self.data["financials"][1]["period"] = "2025Q1"
        comparison = self.comparison()
        self.assertEqual(comparison["status"], "missing_consensus")
        self.assertIsNone(comparison["difference"])

    def test_post_release_consensus_is_not_used_even_when_available_as_of(self) -> None:
        self.data["financials"][1]["snapshot_at"] = "2025-02-02T00:00:00Z"
        comparison = self.comparison()
        self.assertEqual(comparison["status"], "late_consensus")
        self.assertIsNone(comparison["consensus"])
        self.assertIsNone(comparison["difference"])
        self.assertIsNone(comparison["percentage_difference"])

    def test_consensus_at_release_timestamp_is_not_a_pre_release_snapshot(self) -> None:
        self.data["financials"][1]["snapshot_at"] = self.data["financials"][0]["released_at"]
        comparison = self.comparison()
        self.assertEqual(comparison["status"], "late_consensus")
        self.assertIsNone(comparison["difference"])

    def test_pre_release_snapshot_label_cannot_hide_post_release_material_version(self) -> None:
        consensus_source = next(item for item in self.data["sources"] if item["id"] == "s-consensus")
        after_release = "2025-02-02T00:00:00Z"
        consensus_source.update(available_at=after_release, version_at=after_release,
                                retrieved_at=after_release)
        comparison = self.comparison()
        self.assertEqual(comparison["status"], "late_consensus")
        self.assertIsNone(comparison["difference"])
        self.assertIsNone(comparison["percentage_difference"])

    def test_latest_pre_release_comparable_snapshot_is_selected(self) -> None:
        earlier = copy.deepcopy(self.data["financials"][1])
        earlier.update(id="fin-consensus-old", value="90", snapshot_at="2025-01-10T00:00:00Z")
        later = copy.deepcopy(self.data["financials"][1])
        later.update(id="fin-consensus-after-release", value="119", snapshot_at="2025-02-02T00:00:00Z")
        self.data["financials"].extend([earlier, later])
        comparison = self.comparison()
        self.assertEqual(comparison["consensus_id"], "fin-consensus")
        self.assertEqual(Decimal(comparison["difference"]), Decimal("20"))

    def test_zero_consensus_keeps_absolute_difference_and_explicit_zero_state(self) -> None:
        self.data["financials"][1]["value"] = "0"
        comparison = self.comparison()
        self.assertEqual(comparison["status"], "zero_base")
        self.assertEqual(Decimal(comparison["difference"]), Decimal("120"))
        self.assertIsNone(comparison["percentage_difference"])

    def test_negative_consensus_has_no_misleading_percentage(self) -> None:
        self.data["financials"][0]["value"] = "-80"
        self.data["financials"][1]["value"] = "-100"
        comparison = self.comparison()
        self.assertEqual(comparison["status"], "negative_base")
        self.assertEqual(Decimal(comparison["difference"]), Decimal("20"))
        self.assertIsNone(comparison["percentage_difference"])

    def test_nonfinite_financial_value_is_rejected(self) -> None:
        self.data["financials"][0]["value"] = "NaN"
        errors, _ = validate_workspace(self.data)
        self.assertTrue(errors)

    def test_financial_values_cite_both_exact_input_excerpts(self) -> None:
        report = build_report(self.data, mode="earnings")
        comparison = report["earnings"]["comparisons"][0]
        self.assertEqual({citation["excerpt_id"] for citation in comparison["citations"]},
                         {"e-actual", "e-consensus"})
        sources = {item["id"] for item in report["sources"]}
        excerpts = {item["id"]: item for item in self.data["excerpts"]}
        for citation in comparison["citations"]:
            self.assertIn(citation["source_id"], sources)
            original = excerpts[citation["excerpt_id"]]
            self.assertEqual(citation["text"], original["text"])
            self.assertEqual(citation["locator"], original["locator"])
            self.assertEqual(citation["content_sha256"], hashlib.sha256(original["text"].encode()).hexdigest())


class WorkflowHistoryAndCitationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = workspace()

    def test_first_run_is_explicit_initial_baseline(self) -> None:
        change = build_report(self.data)["topics"][0]["change"]
        self.assertEqual(change["status"], "initial_baseline")
        self.assertIsNone(change["baseline_as_of"])

    def test_same_frozen_evidence_has_unchanged_history(self) -> None:
        previous = build_report(self.data)
        report = build_report(self.data, previous=previous)
        change = report["topics"][0]["change"]
        self.assertEqual(change["status"], "unchanged")
        self.assertEqual(change["added_claim_ids"], [])
        self.assertEqual(change["removed_claim_ids"], [])
        self.assertEqual(change["changed_claim_ids"], [])

    def test_new_evidence_is_identified_relative_to_named_baseline(self) -> None:
        previous = build_report(self.data)
        claim_id = add_evidence(self.data, "new", "Example newly published disclosure")
        self.data["topics"][0]["claim_ids"].append(claim_id)
        change = build_report(self.data, previous=previous)["topics"][0]["change"]
        self.assertEqual(change["status"], "changed")
        self.assertEqual(change["baseline_as_of"], CUTOFF)
        self.assertEqual(change["added_claim_ids"], [claim_id])

    def test_claim_definition_change_is_not_misreported_as_unchanged(self) -> None:
        for field, value in (("definition", "Different metric definition requiring review"),
                             ("text", "Revised interpretation of the same excerpt"),
                             ("period", "2025Q1")):
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                previous = build_report(data)
                data["claims"][0][field] = value
                change = build_report(data, previous=previous)["topics"][0]["change"]
                self.assertEqual(change["status"], "changed")
                self.assertEqual(change["changed_claim_ids"], ["c-public"])

    def test_future_baseline_is_rejected(self) -> None:
        previous = build_report(self.data, as_of=AFTER)
        with self.assertRaises(ValueError):
            build_report(self.data, previous=previous)

    def test_internal_baseline_cannot_be_compared_into_public_output(self) -> None:
        previous = build_report(self.data, audience="internal")
        with self.assertRaises(ValueError):
            build_report(self.data, previous=previous, audience="public")

    def test_all_emitted_factual_citations_resolve_to_exact_approved_excerpt(self) -> None:
        report = build_report(self.data)
        sources = {record["id"]: record for record in report["sources"]}
        excerpts = {record["id"]: record for record in self.data["excerpts"]}
        emitted = []
        for topic in report["topics"]:
            emitted.extend(fact for fact in topic["facts"] if fact["status"] == "confirmed")
            for answer in topic["answers"]:
                emitted.extend(answer["statements"])
        self.assertTrue(emitted, "The fixture produced no factual statements")
        for item in emitted:
            with self.subTest(item=item["id"]):
                self.assertTrue(item["citations"])
                for citation in item["citations"]:
                    original = excerpts[citation["excerpt_id"]]
                    self.assertIn(citation["source_id"], sources)
                    self.assertEqual(citation["source_id"], original["source_id"])
                    self.assertEqual(citation["locator"], original["locator"])
                    self.assertEqual(citation["text"], original["text"])
                    self.assertEqual(citation["content_sha256"], hashlib.sha256(original["text"].encode()).hexdigest())
                    self.assertEqual(citation["version"], sources[citation["source_id"]]["version"])
                    self.assertEqual(sources[citation["source_id"]]["status"], "active")

    def test_hypothesis_remains_explicit_and_uses_declared_evidence(self) -> None:
        topic = build_report(self.data)["topics"][0]
        self.assertEqual(topic["analysis"][0]["type"], "hypothesis")
        fact_ids = {fact["id"] for fact in topic["facts"] if fact["status"] == "confirmed"}
        self.assertTrue(set(topic["analysis"][0]["claim_ids"]).issubset(fact_ids))
        self.assertEqual(topic["questions"][0]["origin"], "anticipated")
        self.assertEqual(topic["actual_question_count"], 0)


class WorkflowCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.input = self.directory / "workspace.json"
        self.input.write_text(serialized(workspace()), encoding="utf-8")
        self.original_bytes = self.input.read_bytes()

    def command(self, *arguments: object) -> subprocess.CompletedProcess:
        environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "ir_workflow.py"), *(str(arg) for arg in arguments)],
            check=False, capture_output=True, text=True, env=environment,
        )

    def test_report_refuses_existing_file_and_preserves_its_bytes(self) -> None:
        output = self.directory / "report.json"
        output.write_bytes(b"existing user output\n")
        result = self.command("report", self.input, output)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_bytes(), b"existing user output\n")
        self.assertEqual(self.input.read_bytes(), self.original_bytes)

    def test_report_cannot_replace_workspace_input(self) -> None:
        result = self.command("report", self.input, self.input)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.input.read_bytes(), self.original_bytes)

    def test_snapshot_refuses_existing_output(self) -> None:
        output = self.directory / "snapshot.json"
        output.write_bytes(b"existing frozen input\n")
        result = self.command("snapshot", self.input, output)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_bytes(), b"existing frozen input\n")

    def test_event_appends_history_without_rewriting_source_or_original(self) -> None:
        event_path = self.directory / "event.json"
        first_event = {"id": "ev-1", "at": "2025-01-15T00:00:00Z", "type": "source_retract",
                       "target_id": "s-public", "reviewer": "Example reviewer"}
        event_path.write_text(json.dumps(first_event), encoding="utf-8")
        output = self.directory / "updated.json"
        first = self.command("event", self.input, event_path, output)
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        updated = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(self.input.read_bytes(), self.original_bytes)
        self.assertEqual(updated["sources"], workspace()["sources"])
        self.assertEqual(updated["events"], [first_event])
        frozen_first_bytes = output.read_bytes()
        second_event = {"id": "ev-2", "at": "2025-01-16T00:00:00Z", "type": "source_retract",
                        "target_id": "s-public", "reviewer": "Example reviewer"}
        event_path.write_text(json.dumps(second_event), encoding="utf-8")
        second_output = self.directory / "updated-again.json"
        second = self.command("event", output, event_path, second_output)
        self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
        updated_again = json.loads(second_output.read_text(encoding="utf-8"))
        self.assertEqual(updated_again["events"], [first_event, second_event])
        self.assertEqual(updated_again["sources"], workspace()["sources"])
        self.assertEqual(output.read_bytes(), frozen_first_bytes)

    def test_event_refuses_existing_output_without_losing_history(self) -> None:
        event_path = self.directory / "event.json"
        event_path.write_text(json.dumps({"id": "ev-1", "at": BEFORE, "type": "source_retract",
                                          "target_id": "s-public", "reviewer": "Example reviewer"}),
                              encoding="utf-8")
        result = self.command("event", self.input, event_path, self.input)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.input.read_bytes(), self.original_bytes)

    def test_invalid_event_never_creates_candidate_output(self) -> None:
        event_path = self.directory / "event.json"
        event_path.write_text(json.dumps({"id": "ev-1", "at": BEFORE, "type": "source_retract",
                                          "target_id": "s-missing", "reviewer": "Example reviewer"}),
                              encoding="utf-8")
        output = self.directory / "invalid.json"
        result = self.command("event", self.input, event_path, output)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())
        self.assertEqual(self.input.read_bytes(), self.original_bytes)


if __name__ == "__main__":
    unittest.main()
