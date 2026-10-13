from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from render_html_brief import DEFAULT_TEMPLATE, render_report  # noqa: E402
from validate_ir_data import load_report, validate_report  # noqa: E402


EXAMPLE = ROOT / "examples" / "ir-brief-data.example.json"


class IRBriefValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = load_report(EXAMPLE)

    def test_example_passes_validation(self) -> None:
        errors, warnings = validate_report(self.data)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_unknown_source_is_rejected(self) -> None:
        data = copy.deepcopy(self.data)
        data["top_stories"][0]["source_ids"] = ["S999"]
        errors, _ = validate_report(data)
        self.assertTrue(any("unknown source ID S999" in error for error in errors))

    def test_image_requires_alt_and_source(self) -> None:
        data = copy.deepcopy(self.data)
        data["top_stories"][0]["image_url"] = "https://example.com/image.jpg"
        errors, _ = validate_report(data)
        self.assertTrue(any("image_alt" in error for error in errors))
        self.assertTrue(any("image_source" in error for error in errors))

    def test_final_requires_explicit_approval(self) -> None:
        data = copy.deepcopy(self.data)
        data["metadata"]["report_status"] = "Final"
        errors, _ = validate_report(data)
        self.assertTrue(any("final_approval" in error for error in errors))

    def test_renderer_embeds_data_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "brief.html"
            errors, warnings = render_report(EXAMPLE, output, DEFAULT_TEMPLATE)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])
            html = output.read_text(encoding="utf-8")
            self.assertNotIn("__REPORT_DATA_JSON__", html)
            self.assertIn("Trip.com Group IR Intelligence Brief", html)
            errors, _ = render_report(EXAMPLE, output, DEFAULT_TEMPLATE)
            self.assertTrue(any("output exists" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
