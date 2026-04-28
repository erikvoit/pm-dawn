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
    build_pr_source,
    canonical_body,
    collect_validation_lines,
    inspect_branch_traceability_from_history,
    issue_key_re,
    jira_keys_in_text,
    normalize_branch_candidates,
    pr_artifact_paths,
    pr_sections,
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

    def test_pr_source_body_and_artifact_paths_are_core_owned(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            epic_root = root / ".pm-dawn" / "epics" / "RPVINF-124"
            write_text(
                epic_root / "slices" / "consumer_enablement_11.md",
                """# RPVINF-124 / consumer_enablement_11

Group ID: consumer_enablement_11
Primary Jira Key: RPVINF-137
Secondary Jira Keys: None

Goal:
- Thin skill scripts around shared core workflow services.

Branch Recommendation:
- feature/RPVINF-137-thin-skill-scripts

PR Traceability:
- Primary: RPVINF-137
- Additional: None

Entry Criteria:
- Ready.

Exit Criteria:
- Done.

Repo Surfaces:
- pm_dawn_core/

Implementation Steps:
- Extract helpers.

Validation Steps:
- Run tests.

Risks and Constraints:
- Keep harness orchestration out of core.

Open Questions:
- None

Source Review Context:
- Derived from RPVINF-137.
""",
            )
            write_text(
                epic_root / "plans" / "consumer_enablement_11.plan.md",
                """# RPVINF-124 / consumer_enablement_11 / Slice Plan

Goal:
- Thin skill scripts around shared core workflow services.

Packet Breakdown:
- consumer_enablement_11__04_jira_pr_services: Rewire Jira and PR traceability services.

Files Likely to Change:
- pm_dawn_core/traceability.py
""",
            )

            source = build_pr_source(
                root,
                "RPVINF-124",
                "consumer_enablement_11",
                current_branch_name="feature/RPVINF-137-thin-skill-scripts",
            )
            title_path, body_path, verify_path = pr_artifact_paths(
                root,
                "RPVINF-124",
                "consumer_enablement_11",
            )
            body = canonical_body(source, ["python -m unittest discover -s tests"])

            self.assertEqual("plan", source["source_kind"])
            self.assertEqual(str(title_path), source["title_path"])
            self.assertEqual(str(body_path), source["body_path"])
            self.assertEqual(str(verify_path), source["verify_path"])
            self.assertIn("RPVINF-137", source["title"])
            self.assertIn("Jira\n- Primary: RPVINF-137", body)
            self.assertIn("Validation", pr_sections(body))

    def test_validation_and_branch_traceability_services_are_pure(self) -> None:
        profile = {
            "project": {"issue_key_pattern": r"\bRPVINF-\d+\b"},
            "branches": {"allow_codex_prefix": True},
        }
        source = {
            "primary_issue": "RPVINF-137",
            "secondary_issues": [],
            "branch_name": "feature/RPVINF-137-thin-skill-scripts",
        }

        branch = inspect_branch_traceability_from_history(
            branch="feature/RPVINF-137-thin-skill-scripts",
            base="origin/main",
            subjects=["refactor(core): centralize RPVINF-137 traceability services"],
            source=source,
            profile=profile,
        )
        validation_lines, validation_source = collect_validation_lines(
            Path("."),
            {"run_result_md": None},
            explicit_lines=["python -m unittest discover -s tests"],
        )

        self.assertEqual([], branch["blocking_errors"])
        self.assertEqual(["RPVINF-137"], branch["commit_keys"])
        self.assertEqual(["python -m unittest discover -s tests"], validation_lines)
        self.assertEqual("explicit_lines", validation_source)


if __name__ == "__main__":
    unittest.main()
