from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from ir_workflow import build_report
from render_workflow import render_html, render_markdown


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.json_text = ""
        self.in_data = False

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == "script" and dict(attrs).get("id") == "report-data":
            self.in_data = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_data = False

    def handle_data(self, data):
        if self.in_data:
            self.json_text += data


class WorkflowRenderingTests(unittest.TestCase):
    def setUp(self):
        self.workspace = json.loads((ROOT / "examples/ir-workspace.example.json").read_text(encoding="utf-8"))
        self.report = build_report(self.workspace)

    def test_embedded_data_is_exact_projected_report_not_workspace(self):
        parser = Tags()
        parser.feed(render_html(self.report))
        self.assertEqual(json.loads(parser.json_text), self.report)
        self.assertNotIn("events", json.loads(parser.json_text))
        self.assertNotIn("feedback", json.loads(parser.json_text))

    def test_external_text_cannot_close_data_script_or_create_markup(self):
        report = copy.deepcopy(self.report)
        marker = '</script><img src=x onerror="alert(1)"><script>alert(2)</script>'
        report["topics"][0]["title"] = marker
        parser = Tags()
        parser.feed(render_html(report))
        self.assertEqual(len([t for t, _ in parser.tags if t == "script"]), 2)
        self.assertFalse(any(t == "img" for t, _ in parser.tags))
        self.assertEqual(json.loads(parser.json_text)["topics"][0]["title"], marker)

    def test_unsafe_source_scheme_is_never_a_clickable_link(self):
        self.report["sources"][0]["url"] = "javascript:alert(1)"
        parser = Tags()
        parser.feed(render_html(self.report))
        self.assertFalse(any(a.get("href", "").startswith("javascript:") for t, a in parser.tags if t == "a"))

    def test_raw_workspace_metadata_is_not_exported(self):
        self.workspace["metadata"]["private_notes"] = "INTERNAL_UNIQUE_RENDER_9482"
        report = build_report(self.workspace)
        self.assertNotIn("INTERNAL_UNIQUE_RENDER_9482", render_html(report))
        self.assertNotIn("INTERNAL_UNIQUE_RENDER_9482", render_markdown(report))

    def test_markdown_preserves_answer_source_locators_and_status(self):
        text = render_markdown(self.report)
        for topic in self.report["topics"]:
            for answer in topic["answers"]:
                self.assertIn(answer["status"], text)
                for statement in answer["statements"]:
                    for citation in statement["citations"]:
                        self.assertIn(citation["source_id"], text)
                        self.assertIn(citation["locator"], text)

    def test_cli_refuses_existing_output_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "report.html"
            output.write_bytes(b"protected prior report")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/render_workflow.py"),
                 str(ROOT / "examples/ir-workspace.example.json"), str(output)],
                capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), b"protected prior report")

    def test_date_precision_and_fingerprint_scope_are_visible_not_only_embedded(self):
        source = self.report["sources"][0]
        source.update(published_date_raw="2026-02-25", time_precision="date",
                      time_note="保守边界，不代表首发分钟", fingerprint_scope="仅摘要集合")
        html_text = render_html(self.report).split('<script id="report-data"')[0]
        markdown = render_markdown(self.report)
        for value in ("2026-02-25", "保守边界，不代表首发分钟", "仅摘要集合"):
            self.assertIn(value, html_text)
            self.assertIn(value, markdown)


if __name__ == "__main__":
    unittest.main()
