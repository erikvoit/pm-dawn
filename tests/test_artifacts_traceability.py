"""Tests for shared artifact IO and traceability helpers."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from pm_dawn_core.artifacts import (
    emit_json,
    list_lines,
    normalize_none_list,
    read_json,
    read_optional_text,
    read_text,
    write_json,
    write_text,
)
from pm_dawn_core.traceability import (
    issue_key_re,
    jira_keys_in_text,
    normalize_branch_candidates,
)


class TestArtifactHelpers(unittest.TestCase):
    def test_json_and_text_helpers_create_parent_dirs_and_normalize_newlines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            json_path = root / "nested" / "payload.json"
            text_path = root / "nested" / "note.md"

            write_json(json_path, {"b": 2, "a": 1})
            write_text(text_path, "hello")

            self.assertEqual({"a": 1, "b": 2}, read_json(json_path))
            self.assertEqual("hello\n", read_text(text_path))
            self.assertEqual("hello\n", read_optional_text(text_path))
            self.assertIsNone(read_optional_text(root / "missing.txt"))
            self.assertTrue(json_path.read_text(encoding="utf-8").endswith("\n"))

    def test_emit_json_uses_stable_pretty_output(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            emit_json({"b": 2, "a": 1})

        self.assertEqual({"a": 1, "b": 2}, json.loads(output.getvalue()))
        self.assertIn('\n  "a": 1,', output.getvalue())

    def test_list_normalizers_match_existing_script_contracts(self) -> None:
        self.assertEqual([], normalize_none_list(["None"]))
        self.assertEqual(["RPVINF-137"], normalize_none_list(["RPVINF-137"]))
        self.assertEqual("- None", list_lines([]))
        self.assertEqual("- one\n- two", list_lines(["one", "two"]))


class TestTraceabilityHelpers(unittest.TestCase):
    def test_jira_key_helpers_use_profile_pattern(self) -> None:
        profile = {"project": {"issue_key_pattern": r"\bRPVINF-\d+\b"}}

        self.assertEqual(["RPVINF-137"], issue_key_re(profile).findall("See RPVINF-137"))
        self.assertEqual(["RPVINF-136", "RPVINF-137"], jira_keys_in_text("RPVINF-137 RPVINF-136 RPVINF-137", profile))

    def test_branch_candidates_include_codex_prefix_when_allowed(self) -> None:
        profile = {"branches": {"allow_codex_prefix": True}}

        self.assertEqual(
            {"feature/RPVINF-137-thin-skill-scripts", "codex/feature/RPVINF-137-thin-skill-scripts"},
            normalize_branch_candidates("feature/RPVINF-137-thin-skill-scripts", profile),
        )
        self.assertEqual(
            {"feature/RPVINF-137-thin-skill-scripts", "codex/feature/RPVINF-137-thin-skill-scripts"},
            normalize_branch_candidates("codex/feature/RPVINF-137-thin-skill-scripts", profile),
        )

    def test_branch_candidates_respect_disabled_codex_prefix(self) -> None:
        profile = {"branches": {"allow_codex_prefix": False}}

        self.assertEqual(
            {"feature/RPVINF-137-thin-skill-scripts"},
            normalize_branch_candidates("feature/RPVINF-137-thin-skill-scripts", profile),
        )


if __name__ == "__main__":
    unittest.main()
