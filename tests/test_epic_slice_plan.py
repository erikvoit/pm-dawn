"""Tests for epic-slice-plan packetization and validation seams."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = REPO_ROOT / "epic-slice-plan" / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import build_execution_packets  # type: ignore[import-not-found]
import common  # type: ignore[import-not-found]
import generate_slice_plan_artifacts  # type: ignore[import-not-found]


VALIDATE_SCRIPT = SCRIPT_ROOT / "validate_slice_plan.py"


class TestPacketizationHeuristics(unittest.TestCase):
    def test_build_packets_adds_tests_packet_for_refactor_slice(self) -> None:
        handoff = {
            "epic_key": "RPVINF-124",
            "group_id": "consumer_enablement_4",
            "primary_issue": "RPVINF-128",
            "secondary_issues": [],
            "goal": "Implement a downstream consumer or follow-on slice once upstream seams are ready.",
            "branch_name": "feature/RPVINF-128-consumer-enablement",
            "implementation_steps": [
                "Implement the slice represented by RPVINF-128.",
                "Refactor epic-slice-implement onto shared core and harness boundary",
            ],
        }
        plan = {
            "files_to_change": [
                "pm_dawn_core/implement.py",
                "epic-slice-implement/scripts/load_handoff.py",
            ],
            "files_not_to_change": [],
            "validation_strategy": [
                "Run focused tests for the slice.",
                "Validate upstream and downstream integration points.",
                "Run make check before PR review.",
            ],
            "open_questions": [],
        }

        packets = build_execution_packets.build_packets(plan, handoff, common.DEFAULT_PROJECT_PROFILE)

        self.assertEqual(["contract", "wiring", "tests"], [packet["packet_type"] for packet in packets])
        self.assertEqual(["tests/"], packets[-1]["files_to_change"])


class TestPlanArtifactGuards(unittest.TestCase):
    def test_ensure_plan_is_actionable_rejects_missing_files(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "unable to infer files likely to change"):
            generate_slice_plan_artifacts.ensure_plan_is_actionable({"files_to_change": []})

    def test_ensure_packets_are_actionable_rejects_empty_packet_set(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "unable to packetize slice plan"):
            generate_slice_plan_artifacts.ensure_packets_are_actionable([])


class TestValidateSlicePlanCli(unittest.TestCase):
    def write_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def test_validate_slice_plan_rejects_empty_files_to_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_file(
                root / ".pm-dawn" / "epics" / "RPVINF-124" / "plans" / "consumer_enablement_4.plan.md",
                textwrap.dedent(
                    """\
                    # RPVINF-124 / consumer_enablement_4 / Slice Plan

                    Slice Identity:
                    - Group ID: consumer_enablement_4

                    Goal:
                    - Refactor epic-slice-implement onto shared core and harness boundary.

                    Approved Implementation Approach:
                    - Use packet-sized implementation units.

                    Files Likely to Change:
                    - None

                    Files Explicitly Not to Change:
                    - None

                    Validation Strategy:
                    - Run focused tests.

                    Risks and Constraints:
                    - Keep scope narrow.

                    Open Questions:
                    - None

                    Packet Breakdown:
                    - consumer_enablement_4__01_contract: Land the smallest shared contract changes required by the slice.

                    Packet Ordering:
                    - consumer_enablement_4__01_contract

                    Source Context:
                    - Slice Markdown: /tmp/consumer_enablement_4.md
                    - Inspect payload: None
                    """
                ),
            )
            self.write_file(
                root / ".pm-dawn" / "epics" / "RPVINF-124" / "packets" / "consumer_enablement_4__01_contract.md",
                textwrap.dedent(
                    """\
                    # RPVINF-124 / consumer_enablement_4__01_contract

                    Packet ID:
                    - consumer_enablement_4__01_contract

                    Goal:
                    - Land the smallest shared contract changes required by the slice.

                    Why This Packet Is Isolated:
                    - Packet type: contract
                    - This packet is intentionally narrow and should not re-decide architecture.

                    Depends On:
                    - None

                    Files to Read:
                    - pm_dawn_core/implement.py

                    Files to Change:
                    - pm_dawn_core/implement.py

                    Implementation Steps:
                    - Extract the shared implement contract.

                    Validation Steps:
                    - Run focused tests.

                    Acceptance Checks:
                    - Contract packet changes are limited to the declared files.
                    - All packet validation steps pass.

                    Constraints:
                    - Do not widen scope beyond the approved slice plan.

                    Open Questions:
                    - None

                    Execution Routing:
                    - Risk Class: architectural
                    - Recommended Executor: direct_or_strong_model
                    - Small-model improvisation here is likely to create cross-seam drift.

                    Branch Recommendation:
                    - feature/RPVINF-128-consumer-enablement

                    Commit Scope Guidance:
                    - Use a commit focused on the contract packet and reference RPVINF-128.

                    Jira Traceability:
                    - Primary: RPVINF-128
                    - Additional: None
                    """
                ),
            )

            proc = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATE_SCRIPT),
                    "RPVINF-124",
                    "consumer_enablement_4",
                    "--repo-root",
                    str(root),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(1, proc.returncode)
            payload = json.loads(proc.stdout)
            self.assertIn("plan Markdown has no Files Likely to Change entries", payload["errors"])


if __name__ == "__main__":
    unittest.main()
