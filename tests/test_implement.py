"""Tests for shared implement helpers and epic-slice-implement CLI seams."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from pm_dawn_core.implement import (
    build_launch_prompt,
    build_steer_prompt,
    compile_packet_handoff,
    load_execution_input,
    resolve_agent_harness,
    resolve_harness_model,
    resolve_approved_plan_path,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
LOAD_HANDOFF_SCRIPT = REPO_ROOT / "epic-slice-implement" / "scripts" / "load_handoff.py"
BUILD_PROMPT_SCRIPT = REPO_ROOT / "epic-slice-implement" / "scripts" / "build_opencode_prompt.py"

SLICE_MARKDOWN = textwrap.dedent(
    """\
    # RPVINF-124 / consumer_enablement_4

    Group ID: consumer_enablement_4
    Primary Jira Key: RPVINF-128
    Secondary Jira Keys: None

    Goal:
    - Refactor `epic-slice-implement` launch/planning input and prompt assembly onto shared core.

    Branch Recommendation:
    - feature/RPVINF-128-consumer-enablement

    PR Traceability:
    - Primary: RPVINF-128
    - Additional: None

    Entry Criteria:
    - Upstream seams are stable.

    Exit Criteria:
    - Packetized implementation is complete.

    Repo Surfaces:
    - epic-slice-implement/scripts/

    Implementation Steps:
    - Extract shared execution-input helpers.
    - Rewire the entrypoints.

    Validation Steps:
    - Run focused tests.
    - Validate the prompt flow.

    Risks and Constraints:
    - Keep provider-specific process launch out of shared core.

    Open Questions:
    - None

    Source Review Context:
    - Derived from epic review of RPVINF-124 on 2026-04-20.
    - This story is best handled as an individual PR-sized unit after its blockers land.
    """
)

PACKET_JSON = {
    "schema_version": "v1",
    "epic_key": "RPVINF-124",
    "group_id": "consumer_enablement_4",
    "packet_id": "consumer_enablement_4__01_contract",
    "primary_issue": "RPVINF-128",
    "secondary_issues": [],
    "goal": "Extract the shared execution-input contract needed by epic-slice-implement.",
    "branch_name": "feature/RPVINF-128-consumer-enablement",
    "pr_traceability": {"primary_issue": "RPVINF-128", "additional_issues": []},
    "entry_criteria": ["Upstream seams are stable."],
    "exit_criteria": ["Packetized implementation is complete."],
    "repo_surfaces": ["epic-slice-implement/scripts/"],
    "implementation_steps": ["Extract shared execution-input helpers."],
    "validation_steps": ["Run focused tests."],
    "risks": ["Keep provider-specific process launch out of shared core."],
    "open_questions": [],
    "source_context": {
        "epic_review_date": "2026-04-20",
        "implementation_group_reason": "This story is best handled as an individual PR-sized unit after its blockers land.",
    },
    "packet_type": "contract",
    "risk_class": "architectural",
    "recommended_executor": "direct_or_strong_model",
    "routing_notes": ["Keep harness adapters provider-specific."],
}

PACKET_MARKDOWN = textwrap.dedent(
    """\
    # RPVINF-124 / consumer_enablement_4__01_contract

    Packet ID:
    - consumer_enablement_4__01_contract

    Goal:
    - Extract the shared execution-input contract needed by epic-slice-implement.

    Why This Packet Is Isolated:
    - Packet type: contract
    - This packet is intentionally narrow and should not re-decide architecture.

    Depends On:
    - None

    Files to Read:
    - pm_dawn_core/implement.py
    - epic-slice-implement/scripts/common.py

    Files to Change:
    - pm_dawn_core/implement.py
    - epic-slice-implement/scripts/common.py

    Implementation Steps:
    - Extract shared execution-input helpers.

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
    - Keep harness adapters provider-specific.

    Branch Recommendation:
    - feature/RPVINF-128-consumer-enablement

    Commit Scope Guidance:
    - Use a commit focused on the contract packet and reference RPVINF-128.

    Jira Traceability:
    - Primary: RPVINF-128
    - Additional: None
    """
)


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_repo_fixture(root: Path) -> None:
    write_file(
        root / ".pm-dawn" / "epics" / "RPVINF-124" / "slices" / "consumer_enablement_4.md",
        SLICE_MARKDOWN,
    )
    write_file(
        root / ".pm-dawn" / "epics" / "RPVINF-124" / "packets" / "consumer_enablement_4__01_contract.md",
        PACKET_MARKDOWN,
    )
    write_file(
        root / ".pm-dawn" / "epics" / "RPVINF-124" / "ops" / "artifacts" / "consumer_enablement_4__01_contract.implementation-plan.md",
        "# reviewed plan\n",
    )


class TestImplementHelpers(unittest.TestCase):
    def test_load_execution_input_reads_slice_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)

            handoff, path = load_execution_input(root, "RPVINF-124", "consumer_enablement_4")

            self.assertEqual("consumer_enablement_4", handoff["group_id"])
            self.assertEqual("RPVINF-128", handoff["primary_issue"])
            self.assertEqual([], handoff["open_questions"])
            self.assertTrue(str(path).endswith("consumer_enablement_4.md"))

    def test_load_execution_input_reads_packet_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)

            handoff, path = load_execution_input(
                root,
                "RPVINF-124",
                "consumer_enablement_4",
                "consumer_enablement_4__01_contract",
            )

            self.assertEqual("consumer_enablement_4__01_contract", handoff["packet_id"])
            self.assertEqual("contract", handoff["packet_type"])
            self.assertTrue(str(path).endswith("consumer_enablement_4__01_contract.json"))

    def test_compile_packet_handoff_builds_json_from_packet_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)

            handoff, path = compile_packet_handoff(
                root,
                "RPVINF-124",
                "consumer_enablement_4",
                "consumer_enablement_4__01_contract",
            )

            self.assertEqual(PACKET_JSON["primary_issue"], handoff["primary_issue"])
            self.assertEqual(
                PACKET_JSON["source_context"]["implementation_group_reason"],
                handoff["source_context"]["implementation_group_reason"],
            )
            self.assertTrue(path.exists())

    def test_resolve_agent_harness_and_model_use_project_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            write_file(
                root / ".pm-dawn" / "project-profile.toml",
                textwrap.dedent(
                    """\
                    [agent_harness]
                    default = "preferred"

                    [agent_harness.aliases]
                    preferred = "pi"

                    [agent_harness.phase]
                    planning = "preferred"

                    [pi]
                    default_model = "base-model"

                    [pi.phase_models]
                    planning = "planner-model"

                    [pi.packet_models]
                    contract = "contract-model"
                    """
                ),
            )

            harness = resolve_agent_harness(root, phase="planning")
            model = resolve_harness_model(
                root,
                harness=harness,
                phase="planning",
                packet_id="consumer_enablement_4__01_contract",
            )

            self.assertEqual("pi", harness)
            self.assertEqual("planner-model", model)

    def test_resolve_approved_plan_path_prefers_reviewed_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)

            plan_path = resolve_approved_plan_path(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
                None,
            )

            self.assertIsNotNone(plan_path)
            assert plan_path is not None
            self.assertTrue(plan_path.name.endswith(".implementation-plan.md"))

    def test_build_launch_prompt_includes_reviewed_plan_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            handoff, handoff_path = load_execution_input(root, "RPVINF-124", "consumer_enablement_4")
            approved_plan = (
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "artifacts"
                / "consumer_enablement_4__01_contract.implementation-plan.md"
            ).resolve()

            prompt = build_launch_prompt(
                handoff,
                handoff_path,
                root,
                approved_plan_path=approved_plan,
            )

            self.assertIn("approved plan", prompt)
            self.assertIn("reviewed and corrected implementation brief", prompt)
            self.assertIn("feature/RPVINF-128-consumer-enablement", prompt)
            self.assertIn('python3 "epic-slice-implement/scripts/mark_slice_pending_review.py"', prompt)
            self.assertIn("epic-slice-implement/scripts/mark_slice_pending_review.py", prompt)
            self.assertIn("--repo-root .", prompt)

    def test_build_steer_prompt_references_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            handoff, handoff_path = load_execution_input(root, "RPVINF-124", "consumer_enablement_4")

            prompt = build_steer_prompt(handoff, handoff_path, root, "Stay within packet scope.")

            self.assertIn("Stay within packet scope.", prompt)
            self.assertIn(".pm-dawn/epics/RPVINF-124/slices/consumer_enablement_4.md", prompt)


class TestImplementCliSmoke(unittest.TestCase):
    def run_script(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def test_load_handoff_cli_reads_shared_execution_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)

            result = self.run_script(
                LOAD_HANDOFF_SCRIPT,
                "RPVINF-124",
                "consumer_enablement_4",
                "--repo-root",
                str(root),
            )

            payload = json.loads(result.stdout)
            self.assertEqual("consumer_enablement_4", payload["handoff"]["group_id"])
            self.assertTrue(payload["handoff_path"].endswith("consumer_enablement_4.md"))

    def test_build_opencode_prompt_cli_uses_shared_prompt_builder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)

            result = self.run_script(
                BUILD_PROMPT_SCRIPT,
                "RPVINF-124",
                "consumer_enablement_4",
                "--repo-root",
                str(root),
                "--packet-id",
                "consumer_enablement_4__01_contract",
                "--approved-plan",
                str(
                    root
                    / ".pm-dawn"
                    / "epics"
                    / "RPVINF-124"
                    / "ops"
                    / "artifacts"
                    / "consumer_enablement_4__01_contract.implementation-plan.md"
                ),
            )

            self.assertIn("Primary Jira key: RPVINF-128", result.stdout)
            self.assertIn("Packet type: contract", result.stdout)
            self.assertIn("reviewed and corrected implementation brief", result.stdout)


if __name__ == "__main__":
    unittest.main()
