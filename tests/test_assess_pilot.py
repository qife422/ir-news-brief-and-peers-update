"""Synthetic behavior tests, not evidence of real IR business acceptance."""
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_ir_workflow import workspace, BEFORE, AFTER, CUTOFF, SCRIPTS
from assess_pilot import assess_pilot, freeze_candidate


def real_shaped_fixture():
    data = workspace()
    data["metadata"]["status"] = "Draft"
    data["sources"][0]["kind"] = "filing"
    return data


def protocol():
    return {
        "generation": {"prompt": "Synthetic test request", "config": {"mode": "radar"}},
        "required_coverage": [
            {"company": "Trip.com Group", "periods": ["2024Q4", "2025Q1"]},
            {"company": "Booking Holdings", "periods": ["2024Q4"]},
        ],
        "cases": [],
    }


class PilotAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.data = real_shaped_fixture()
        self.plan = protocol()

    def test_coverage_requires_supported_company_period_not_source_count(self):
        rows = assess_pilot(self.data, self.plan)["coverage"]
        states = {(r["company"], r["period"]): r["status"] for r in rows}
        self.assertEqual(states[("Trip.com Group", "2024Q4")], "covered")
        self.assertEqual(states[("Trip.com Group", "2025Q1")], "missing")
        self.assertEqual(states[("Booking Holdings", "2024Q4")], "missing")
        self.assertEqual(rows[0]["claim_ids"], ["c-public"])

    def test_example_workspace_never_counts_as_real_coverage(self):
        result = assess_pilot(workspace(), self.plan)
        self.assertTrue(all(row["status"] == "missing" for row in result["coverage"]))
        self.assertEqual(result["business_acceptance"], "pending_human_acceptance")

    def test_example_source_never_counts_as_real_coverage(self):
        self.data["sources"][0]["kind"] = "example"
        self.assertEqual(assess_pilot(self.data, self.plan)["coverage"][0]["status"], "missing")

    def test_future_material_cannot_fill_coverage(self):
        for key in ("published_at", "available_at", "version_at", "retrieved_at"):
            self.data["sources"][0][key] = AFTER
        self.assertEqual(assess_pilot(self.data, self.plan)["coverage"][0]["status"], "missing")

    def test_retracted_material_cannot_fill_coverage(self):
        self.data["sources"][0].update(status="retracted", invalidated_at=BEFORE)
        self.assertEqual(assess_pilot(self.data, self.plan)["coverage"][0]["status"], "missing")

    def test_private_facts_do_not_fill_or_leak_into_public_assessment(self):
        self.data["metadata"]["allowed_visibility"].append("internal")
        self.data["sources"][0].update(visibility="internal", audiences=["internal"])
        self.data["claims"][0]["text"] = "SENSITIVE_CANARY_981"
        result = assess_pilot(self.data, self.plan)
        self.assertNotIn("SENSITIVE_CANARY_981", json.dumps(result))
        self.assertEqual(result["coverage"][0]["status"], "missing")

    def test_pending_claims_do_not_fill_coverage(self):
        self.data["claims"][0]["status"] = "pending"
        self.assertEqual(assess_pilot(self.data, self.plan)["coverage"][0]["status"], "missing")

    def test_fact_not_selected_by_topic_does_not_fill_coverage(self):
        self.data["topics"][0]["claim_ids"] = []
        self.assertEqual(assess_pilot(self.data, self.plan)["coverage"][0]["status"], "missing")

    def test_freeze_matches_unchanged_candidate(self):
        freeze = freeze_candidate(self.data, self.plan["generation"])
        self.assertEqual(assess_pilot(self.data, self.plan, freeze)["freeze_status"], "matched")
        self.assertEqual(len(freeze["workspace_sha256"]), 64)
        self.assertEqual(len(freeze["candidate_sha256"]), 64)

    def test_any_raw_input_change_invalidates_frozen_identity(self):
        freeze = freeze_candidate(self.data, self.plan["generation"])
        self.data["metadata"]["non_projected_note"] = "changed after freeze"
        self.assertEqual(assess_pilot(self.data, self.plan, freeze)["freeze_status"], "mismatch")

    def test_prompt_change_invalidates_frozen_identity(self):
        freeze = freeze_candidate(self.data, self.plan["generation"])
        self.plan["generation"]["prompt"] = "Different authoring instruction"
        self.assertEqual(assess_pilot(self.data, self.plan, freeze)["freeze_status"], "mismatch")

    def test_config_change_invalidates_frozen_identity(self):
        freeze = freeze_candidate(self.data, self.plan["generation"])
        self.plan["generation"]["config"]["seed"] = 17
        self.assertEqual(assess_pilot(self.data, self.plan, freeze)["freeze_status"], "mismatch")

    def test_forged_candidate_hash_or_core_hash_does_not_match(self):
        original = freeze_candidate(self.data, self.plan["generation"])
        for key in ("candidate_sha256", "candidate_report_sha256", "core_sha256"):
            with self.subTest(key=key):
                frozen = copy.deepcopy(original)
                frozen[key] = "0" * 64
                self.assertEqual(assess_pilot(self.data, self.plan, frozen)["freeze_status"], "mismatch")

    def test_missing_cases_remain_pending_with_null_metrics(self):
        result = assess_pilot(self.data, self.plan)
        self.assertEqual({c["case_type"] for c in result["cases"]},
                         {"peer_update", "earnings_preparation", "meeting"})
        self.assertTrue(all(c["status"] == "pending_inputs" for c in result["cases"]))
        self.assertEqual(result["business_acceptance"], "pending_human_acceptance")

    def test_example_case_is_not_business_acceptance_even_with_reviewer(self):
        self.plan["cases"] = [{"case_type": "peer_update", "data_kind": "Example",
                               "permission_ref": "Synthetic permission",
                               "human_review": {"reviewer": "Synthetic reviewer", "at": CUTOFF,
                                                "scope": "Synthetic review"}, "metrics": None}]
        result = assess_pilot(self.data, self.plan)
        self.assertEqual(result["cases"][0]["status"], "pending_inputs")
        self.assertEqual(result["business_acceptance"], "pending_human_acceptance")

    def test_duplicate_case_type_is_rejected(self):
        self.plan["cases"] = [{"case_type": "meeting"}, {"case_type": "meeting"}]
        with self.assertRaises(ValueError):
            assess_pilot(self.data, self.plan)

    def test_invalid_workspace_fails_before_assessment(self):
        self.data["metadata"]["as_of"] = "no offset"
        with self.assertRaises(ValueError):
            assess_pilot(self.data, self.plan)

    def test_invalid_generation_is_rejected(self):
        for generation in ({}, {"prompt": "", "config": {}},
                           {"prompt": "test", "config": []}):
            with self.subTest(generation=generation), self.assertRaises(ValueError):
                freeze_candidate(self.data, generation)

    def test_assessment_does_not_mutate_workspace_or_plan(self):
        original_data, original_plan = copy.deepcopy(self.data), copy.deepcopy(self.plan)
        assess_pilot(self.data, self.plan)
        self.assertEqual(self.data, original_data)
        self.assertEqual(self.plan, original_plan)

    def case_and_freeze(self):
        frozen = freeze_candidate(self.data, self.plan["generation"])
        case = {"case_type": "peer_update", "data_kind": "public_real",
                "permission_ref": "Synthetic public fixture permission", "metrics": {},
                "human_review": None, "holdout": None}
        self.plan["cases"] = [case]
        return case, frozen

    def test_uncertain_facts_are_not_counted_as_correct(self):
        case, frozen = self.case_and_freeze()
        case["metrics"]["factual_accuracy"] = {"evidence_ref": "synthetic#facts", "checked": 4,
                                                "supported": 3, "contradicted": 0,
                                                "unsupported": 0, "uncertain": 1}
        values = assess_pilot(self.data, self.plan, frozen)["cases"][0]["metrics"]["factual_accuracy"]
        self.assertEqual(values["supported_fraction"], 0.75)

    def test_unreconciled_counts_are_rejected(self):
        case, frozen = self.case_and_freeze()
        case["metrics"]["question_value"] = {"evidence_ref": "synthetic#questions", "reviewed": 1,
                                             "accepted": 1, "accepted_after_edit": 1, "rejected": 0}
        with self.assertRaises(ValueError):
            assess_pilot(self.data, self.plan, frozen)

    def test_zero_time_baseline_does_not_generate_percentage(self):
        case, frozen = self.case_and_freeze()
        case["metrics"]["preparation_time"] = {"evidence_ref": "synthetic#time", "manual_minutes": 0,
                                               "assisted_minutes": 5, "comparable_scope": True}
        metric = assess_pilot(self.data, self.plan, frozen)["cases"][0]["metrics"]["preparation_time"]
        self.assertIsNone(metric["reduction_fraction"])

    def test_incomparable_timing_does_not_claim_efficiency(self):
        case, frozen = self.case_and_freeze()
        case["metrics"]["preparation_time"] = {"evidence_ref": "synthetic#time", "manual_minutes": 40,
                                               "assisted_minutes": 5, "comparable_scope": False}
        metric = assess_pilot(self.data, self.plan, frozen)["cases"][0]["metrics"]["preparation_time"]
        self.assertIsNone(metric["reduction_fraction"])
        self.assertIsNone(metric["minutes_saved"])

    def test_missing_measurement_evidence_produces_null_not_zero(self):
        case, frozen = self.case_and_freeze()
        case["metrics"]["preparation_time"] = {"manual_minutes": 40, "assisted_minutes": 5,
                                               "comparable_scope": True}
        self.assertIsNone(assess_pilot(self.data, self.plan, frozen)["cases"][0]["metrics"]["preparation_time"])

    def test_overflow_nonfinite_or_boolean_measurement_is_rejected(self):
        case, frozen = self.case_and_freeze()
        for bad in (10 ** 1000, float("inf"), float("nan"), True, -1):
            case["metrics"]["preparation_time"] = {"evidence_ref": "synthetic#time", "manual_minutes": bad,
                                                   "assisted_minutes": 5, "comparable_scope": True}
            with self.subTest(bad_type=type(bad).__name__), self.assertRaises(ValueError):
                assess_pilot(self.data, self.plan, frozen)

    def test_human_review_must_bind_exact_frozen_candidate(self):
        case, frozen = self.case_and_freeze()
        case["human_review"] = {"reviewer": "Synthetic human", "scope": "Synthetic scope",
                                "at": datetime.now(timezone.utc).isoformat(), "candidate_sha256": "0" * 64}
        row = assess_pilot(self.data, self.plan, frozen)["cases"][0]
        self.assertEqual(row["status"], "pending_business_review")
        self.assertTrue(any("human_review" in x for x in row["blockers"]))

    def test_future_review_does_not_approve_candidate(self):
        case, frozen = self.case_and_freeze()
        case["human_review"] = {"reviewer": "Synthetic human", "scope": "Synthetic scope",
                                "at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                                "candidate_sha256": frozen["candidate_sha256"]}
        row = assess_pilot(self.data, self.plan, frozen)["cases"][0]
        self.assertTrue(any("human_review" in x for x in row["blockers"]))

    def test_review_from_before_candidate_freeze_does_not_apply(self):
        case, frozen = self.case_and_freeze()
        case["human_review"] = {"reviewer": "Synthetic human", "scope": "Synthetic scope", "at": BEFORE,
                                "candidate_sha256": frozen["candidate_sha256"]}
        row = assess_pilot(self.data, self.plan, frozen)["cases"][0]
        self.assertTrue(any("human_review" in x for x in row["blockers"]))

    def test_future_freeze_is_not_matched(self):
        frozen = freeze_candidate(self.data, self.plan["generation"])
        frozen["frozen_at"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        self.assertEqual(assess_pilot(self.data, self.plan, frozen)["freeze_status"], "mismatch")

    def test_holdout_opened_early_or_contaminated_never_becomes_blind_pass(self):
        case, frozen = self.case_and_freeze()
        for holdout in ({"contaminated": True}, {"contaminated": False, "opened_at": BEFORE,
                                                 "frozen_candidate_sha256": frozen["candidate_sha256"]}):
            case["holdout"] = holdout
            row = assess_pilot(self.data, self.plan, frozen)["cases"][0]
            self.assertNotEqual(row["holdout_status"], "declared_uncontaminated")
            self.assertEqual(assess_pilot(self.data, self.plan, frozen)["business_acceptance"],
                             "pending_human_acceptance")

    def test_future_holdout_opening_is_not_a_completed_declaration(self):
        case, frozen = self.case_and_freeze()
        case["holdout"] = {"contaminated": False,
                           "opened_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
                           "frozen_candidate_sha256": frozen["candidate_sha256"]}
        row = assess_pilot(self.data, self.plan, frozen)["cases"][0]
        self.assertEqual(row["holdout_status"], "future_opening")

    def test_review_cannot_precede_evaluator_opening_holdout(self):
        case, frozen = self.case_and_freeze()
        case["human_review"] = {"reviewer": "Synthetic human", "scope": "Synthetic scope",
                                "at": frozen["frozen_at"], "candidate_sha256": frozen["candidate_sha256"]}
        case["holdout"] = {"contaminated": False, "opened_at": datetime.now(timezone.utc).isoformat(),
                           "frozen_candidate_sha256": frozen["candidate_sha256"]}
        row = assess_pilot(self.data, self.plan, frozen)["cases"][0]
        self.assertIn("review_before_holdout", row["blockers"])

    def test_complete_declarations_are_only_structural_not_business_acceptance(self):
        case, frozen = self.case_and_freeze()
        case["human_review"] = {"reviewer": "Synthetic human", "scope": "Synthetic scope",
                                "at": datetime.now(timezone.utc).isoformat(),
                                "candidate_sha256": frozen["candidate_sha256"]}
        case["holdout"] = {"contaminated": False, "opened_at": frozen["frozen_at"],
                           "frozen_candidate_sha256": frozen["candidate_sha256"]}
        case["metrics"] = {
            "preparation_time": {"evidence_ref": "synthetic#timing", "manual_minutes": 20,
                                 "assisted_minutes": 10, "comparable_scope": True},
            "factual_accuracy": {"evidence_ref": "synthetic#facts", "checked": 1, "supported": 1,
                                 "contradicted": 0, "unsupported": 0, "uncertain": 0},
            "question_value": {"evidence_ref": "synthetic#questions", "reviewed": 1,
                               "accepted": 1, "accepted_after_edit": 0, "rejected": 0},
            "feedback_reuse": {"evidence_ref": "synthetic#reuse", "eligible_items": 1, "used_items": 1},
        }
        result = assess_pilot(self.data, self.plan, frozen)
        self.assertEqual(result["cases"][0]["status"], "review_record_complete")
        self.assertEqual(result["cases"][0]["blockers"], [])
        self.assertEqual(result["business_acceptance"], "pending_human_acceptance")
        self.assertEqual(result["status"], "Draft")


class PilotCommandTests(unittest.TestCase):
    def test_freeze_cli_refuses_to_overwrite_generation_or_existing_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, generation = root / "workspace.json", root / "generation.json"
            data.write_text(json.dumps(real_shaped_fixture()), encoding="utf-8")
            generation.write_text(json.dumps(protocol()["generation"]), encoding="utf-8")
            original = generation.read_bytes()
            output = root / "freeze.json"
            command = [sys.executable, "-B", str(SCRIPTS / "assess_pilot.py"),
                       "freeze", str(data), str(generation), str(output)]
            first = subprocess.run(command, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            frozen = output.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), frozen)
            command[-1] = str(generation)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(generation.read_bytes(), original)

    def test_cli_uses_exclusive_output_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / "workspace.json"
            plan = root / "plan.json"
            data.write_text(json.dumps(real_shaped_fixture()), encoding="utf-8")
            plan.write_text(json.dumps(protocol()), encoding="utf-8")
            old_data = data.read_bytes()
            output = root / "result.json"
            command = [sys.executable, "-B", str(SCRIPTS / "assess_pilot.py"),
                       "assess", str(data), str(plan), str(output)]
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            first = subprocess.run(command, capture_output=True, text=True, env=env)
            self.assertEqual(first.returncode, 0, first.stderr)
            old_output = output.read_bytes()
            second = subprocess.run(command, capture_output=True, text=True, env=env)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(output.read_bytes(), old_output)
            self.assertEqual(data.read_bytes(), old_data)
            command[-1] = str(data)
            self.assertNotEqual(subprocess.run(command, capture_output=True, env=env).returncode, 0)
            self.assertEqual(data.read_bytes(), old_data)


if __name__ == "__main__":
    unittest.main()
