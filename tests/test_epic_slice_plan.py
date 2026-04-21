"""Tests for epic-slice-plan smoke paths."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EPIC_KEY = "RPVINF-124"
GROUP_ID = "consumer_enablement_2"
PACKET_ID = "consumer_enablement_2__01_contract"

SLICE_MARKDOWN = f"""# {EPIC_KEY} / {GROUP_ID}

Group ID: {GROUP_ID}
Primary Jira Key: RPVINF-126
Secondary Jira Keys: None

Goal:
- Refactor `epic-slice-plan` onto the shared core so planning artifacts and repo interpretation stop living in a tool-local seam.

Branch Recommendation:
- feature/RPVINF-126-consumer-enablement

PR Traceability:
- Primary: RPVINF-126
- Additional: None

Entry Criteria:
- Required upstream blockers are resolved and the owning seam is stable.

Exit Criteria:
- The grouped stories are implemented and verified in one focused PR-sized slice.

Repo Surfaces:
- None

Implementation Steps:
- Refactor epic-slice-plan onto the shared core.

Validation Steps:
- Run focused tests for the slice.

Risks and Constraints:
- Keep artifact formats stable.

Open Questions:
- None

Source Review Context:
- Derived from epic review of RPVINF-124 on 2026-04-20.
- This story is best handled as an individual PR-sized unit after its blockers land.
"""

PLAN_MARKDOWN = f"""# {EPIC_KEY} / {GROUP_ID} / Slice Plan

Slice Identity:
- Group ID: {GROUP_ID}
- Primary Jira Key: RPVINF-126
- Secondary Jira Keys: None

Goal:
- Refactor `epic-slice-plan` onto the shared core so planning artifacts and repo interpretation stop living in a tool-local seam.

Approved Implementation Approach:
- Start from the existing slice handoff and current repo seams.

Files Likely to Change:
- pm_dawn_core/markdown.py

Files Explicitly Not to Change:
- None

Validation Strategy:
- Run focused tests for the slice.

Risks and Constraints:
- Keep artifact formats stable.

Open Questions:
- None

Packet Breakdown:
- {PACKET_ID}: Extract the shared plan-artifact and path helper contract needed by `epic-slice-plan`.

Packet Ordering:
- {PACKET_ID}

Source Context:
- Slice Markdown: fixture
- Inspect payload: None
"""

PACKET_MARKDOWN = f"""# {EPIC_KEY} / {PACKET_ID}

Packet ID:
- {PACKET_ID}

Goal:
- Extract the shared plan-artifact and path helper contract needed by `epic-slice-plan`.

Why This Packet Is Isolated:
- Packet type: contract
- This packet is intentionally narrow and should not re-decide architecture.

Depends On:
- None

Files to Read:
- AGENTS.md

Files to Change:
- pm_dawn_core/markdown.py

Implementation Steps:
- Extract parsing helpers.

Validation Steps:
- Run unit tests.

Acceptance Checks:
- Contract packet changes are limited to the declared files.

Constraints:
- Do not widen scope beyond the approved slice plan.

Open Questions:
- None

Execution Routing:
- Risk Class: architectural
- Recommended Executor: direct_or_strong_model
- Preserve current artifact semantics.

Branch Recommendation:
- feature/RPVINF-126-consumer-enablement

Commit Scope Guidance:
- Use a commit focused on the contract packet and reference RPVINF-126.

Jira Traceability:
- Primary: RPVINF-126
- Additional: None
"""


def make_fixture_repo(root: Path) -> None:
    epic_root = root / ".pm-dawn" / "epics" / EPIC_KEY
    (epic_root / "slices").mkdir(parents=True)
    (epic_root / "plans").mkdir(parents=True)
    (epic_root / "packets").mkdir(parents=True)
    (epic_root / "ops" / "handoffs").mkdir(parents=True)
    (epic_root / "ops" / "artifacts").mkdir(parents=True)
    (epic_root / "slices" / f"{GROUP_ID}.md").write_text(SLICE_MARKDOWN, encoding="utf-8")
    (epic_root / "plans" / f"{GROUP_ID}.plan.md").write_text(PLAN_MARKDOWN, encoding="utf-8")
    (epic_root / "packets" / f"{PACKET_ID}.md").write_text(PACKET_MARKDOWN, encoding="utf-8")


class TestValidateSlicePlan(unittest.TestCase):
    def test_validate_slice_plan_smoke_test(self) -> None:
        """Test that validate_slice_plan.py runs successfully."""
        script_path = REPO_ROOT / "epic-slice-plan" / "scripts" / "validate_slice_plan.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_root = Path(tmpdir)
            make_fixture_repo(fixture_root)
            result = subprocess.run(
                [
                    "python",
                    str(script_path),
                    EPIC_KEY,
                    GROUP_ID,
                    "--repo-root",
                    str(fixture_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, msg=f"stderr: {result.stderr}\nstdout: {result.stdout}")
            payload = json.loads(result.stdout.strip())
            self.assertTrue(payload.get("ready", False))
            self.assertEqual(1, payload.get("packet_count"))

    def test_validate_slice_plan_with_invalid_epic_key(self) -> None:
        """Test that validate_slice_plan.py handles missing epic gracefully."""
        script_path = REPO_ROOT / "epic-slice-plan" / "scripts" / "validate_slice_plan.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_root = Path(tmpdir)
            make_fixture_repo(fixture_root)
            result = subprocess.run(
                [
                    "python",
                    str(script_path),
                    "NONEXISTENT-999",
                    GROUP_ID,
                    "--repo-root",
                    str(fixture_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, result.returncode)


class TestCompilePacketMarkdown(unittest.TestCase):
    def test_compile_packet_markdown_smoke_test(self) -> None:
        """Test that compile_packet_markdown.py runs successfully."""
        script_path = REPO_ROOT / "epic-slice-plan" / "scripts" / "compile_packet_markdown.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_root = Path(tmpdir)
            make_fixture_repo(fixture_root)
            result = subprocess.run(
                [
                    "python",
                    str(script_path),
                    EPIC_KEY,
                    GROUP_ID,
                    PACKET_ID,
                    "--repo-root",
                    str(fixture_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, msg=f"stderr: {result.stderr}\nstdout: {result.stdout}")
            payload = json.loads(result.stdout.strip())
            self.assertEqual(PACKET_ID, payload.get("packet_id"))
            self.assertEqual("contract", payload.get("packet_type"))
            self.assertEqual("RPVINF-126", payload.get("primary_issue"))

    def test_compile_packet_markdown_with_invalid_packet(self) -> None:
        """Test that compile_packet_markdown.py handles missing packet gracefully."""
        script_path = REPO_ROOT / "epic-slice-plan" / "scripts" / "compile_packet_markdown.py"
        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_root = Path(tmpdir)
            make_fixture_repo(fixture_root)
            result = subprocess.run(
                [
                    "python",
                    str(script_path),
                    EPIC_KEY,
                    GROUP_ID,
                    "nonexistent__99_tests",
                    "--repo-root",
                    str(fixture_root),
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, result.returncode)


class TestSmokePaths(unittest.TestCase):
    def test_scripts_are_invocable_with_plain_python(self) -> None:
        """Verify scripts can be invoked without external dependencies."""
        scripts = [
            "epic-slice-plan/scripts/validate_slice_plan.py",
            "epic-slice-plan/scripts/compile_packet_markdown.py",
        ]
        for script_rel in scripts:
            script_path = REPO_ROOT / script_rel
            self.assertTrue(script_path.exists(), f"Script {script_rel} should exist")

            # Check that script uses plain python shebang
            content = script_path.read_text(encoding="utf-8")
            self.assertIn("#!/usr/bin/env python3", content)

    def test_validate_slice_plan_exercises_shared_core(self) -> None:
        """Verify validate_slice_plan.py uses shared-core helpers."""
        script_path = REPO_ROOT / "epic-slice-plan" / "scripts" / "validate_slice_plan.py"
        content = script_path.read_text(encoding="utf-8")

        # Should import from shared core
        self.assertIn("from pm_dawn_core.layout import", content)
        self.assertIn("from pm_dawn_core.markdown import", content)
        # Should use slice_paths
        self.assertIn("slice_paths", content)
        # Should use parse functions
        self.assertIn("parse_packet_markdown", content)
        self.assertIn("parse_plan_markdown", content)

    def test_compile_packet_markdown_exercises_shared_core(self) -> None:
        """Verify compile_packet_markdown.py uses shared-core helpers."""
        script_path = REPO_ROOT / "epic-slice-plan" / "scripts" / "compile_packet_markdown.py"
        content = script_path.read_text(encoding="utf-8")

        # Should import from shared core
        self.assertIn("from pm_dawn_core.layout import", content)
        self.assertIn("from pm_dawn_core.markdown import", content)
        # Should use packet_markdown_path
        self.assertIn("packet_markdown_path", content)
        # Should use parse functions
        self.assertIn("parse_packet_markdown", content)


if __name__ == "__main__":
    unittest.main()
