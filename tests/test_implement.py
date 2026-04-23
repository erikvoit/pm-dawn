"""Tests for shared implement helpers and epic-slice-implement CLI seams."""

from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from pm_dawn_core.implement import (
    IMPLEMENT_COMMAND_SURFACES,
    packet_plan_expected_artifact_path,
    packet_plan_monitor_state,
    packet_plan_requires_revision_run,
    packet_plan_review_state_snapshot,
    build_launch_prompt,
    build_steer_prompt,
    compile_packet_handoff,
    harness_monitoring_settings,
    implement_command_relative_script_path,
    initialize_packet_plan_review_state,
    load_execution_input,
    opencode_monitoring_settings,
    packet_plan_requires_acceptance,
    pi_implementation_artifact_grace_period_seconds,
    pi_initial_session_check_seconds,
    pi_planning_artifact_grace_period_seconds,
    render_implement_command,
    resolve_agent_harness,
    resolve_harness_model,
    resolve_approved_plan_path,
    resolve_implement_command,
    resolve_packet_plan_review_state,
)
from pm_dawn_core.layout import (
    implementation_plan_artifact_path,
    packet_plan_proposal_artifact_path,
    packet_plan_review_state_path,
)
from pm_dawn_core import runtime


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


epic_slice_plan_common = load_module(
    "epic_slice_plan_common",
    REPO_ROOT / "epic-slice-plan" / "scripts" / "common.py",
)
jira_pr_common = load_module(
    "jira_pr_common",
    REPO_ROOT / "jira-pr" / "scripts" / "common.py",
)
jira_epic_review_common = load_module(
    "jira_epic_review_common",
    REPO_ROOT / "jira-epic-review" / "scripts" / "common.py",
)

LOAD_HANDOFF_SCRIPT = REPO_ROOT / "epic-slice-implement" / "scripts" / "load_handoff.py"
BUILD_PROMPT_SCRIPT = (
    REPO_ROOT / "epic-slice-implement" / "scripts" / "build_opencode_prompt.py"
)

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
        root
        / ".pm-dawn"
        / "epics"
        / "RPVINF-124"
        / "slices"
        / "consumer_enablement_4.md",
        SLICE_MARKDOWN,
    )
    write_file(
        root
        / ".pm-dawn"
        / "epics"
        / "RPVINF-124"
        / "packets"
        / "consumer_enablement_4__01_contract.md",
        PACKET_MARKDOWN,
    )
    write_file(
        root
        / ".pm-dawn"
        / "epics"
        / "RPVINF-124"
        / "ops"
        / "artifacts"
        / "consumer_enablement_4__01_contract.implementation-plan.md",
        "# reviewed plan\n",
    )


class TestImplementHelpers(unittest.TestCase):
    def test_resolve_implement_command_supports_canonical_ids_and_aliases(self) -> None:
        pending_review = resolve_implement_command("pending-review")
        self.assertEqual("mark_slice_pending_review.py", pending_review.script_name)
        self.assertEqual(
            pending_review,
            resolve_implement_command("mark_slice_pending_review"),
        )
        self.assertEqual(
            "coordinate_plan_review.py",
            resolve_implement_command("review-plan").script_name,
        )

    def test_implement_command_surface_registry_stays_unique(self) -> None:
        command_ids = [surface.command_id for surface in IMPLEMENT_COMMAND_SURFACES]
        script_names = [surface.script_name for surface in IMPLEMENT_COMMAND_SURFACES]
        self.assertEqual(len(command_ids), len(set(command_ids)))
        self.assertEqual(len(script_names), len(set(script_names)))

    def test_render_implement_command_uses_repo_relative_script_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            command = render_implement_command(
                root,
                "pending-review",
                "RPVINF-124",
                "consumer_enablement_5",
                "--repo-root",
                ".",
                python_executable="python3",
            )

            self.assertEqual(
                "python3 epic-slice-implement/scripts/mark_slice_pending_review.py "
                "RPVINF-124 consumer_enablement_5 --repo-root .",
                command,
            )
            self.assertEqual(
                Path("epic-slice-implement/scripts/mark_slice_pending_review.py"),
                implement_command_relative_script_path("pending-review"),
            )

    def test_render_implement_command_quotes_arguments_with_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            command = render_implement_command(
                root,
                "plan",
                "RPVINF-124",
                "consumer_enablement_5",
                "consumer_enablement_5__02_wiring",
                "--title",
                "packet plan with spaces",
            )

            self.assertEqual(
                "python epic-slice-implement/scripts/generate_packet_implementation_plan.py "
                "RPVINF-124 consumer_enablement_5 consumer_enablement_5__02_wiring "
                "--title 'packet plan with spaces'",
                command,
            )

    def test_load_execution_input_reads_slice_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)

            handoff, path = load_execution_input(
                root, "RPVINF-124", "consumer_enablement_4"
            )

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
            self.assertTrue(
                str(path).endswith("consumer_enablement_4__01_contract.json")
            )

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

    def test_harness_monitoring_settings_use_project_profile_and_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            write_file(
                root / ".pm-dawn" / "project-profile.toml",
                textwrap.dedent(
                    """\
                    [monitoring.defaults]
                    initial_session_check_seconds = 6
                    planning_artifact_grace_period_seconds = 70
                    implementation_artifact_grace_period_seconds = 140

                    [monitoring.pi]
                    initial_session_check_seconds = 7
                    planning_artifact_grace_period_seconds = 75
                    implementation_artifact_grace_period_seconds = 150

                    [monitoring.opencode]
                    planning_artifact_grace_period_seconds = 90
                    """
                ),
            )

            self.assertEqual(
                {
                    "initial_session_check_seconds": 7,
                    "planning_artifact_grace_period_seconds": 75,
                    "implementation_artifact_grace_period_seconds": 150,
                },
                harness_monitoring_settings(root, "pi"),
            )
            self.assertEqual(
                {
                    "initial_session_check_seconds": 6,
                    "planning_artifact_grace_period_seconds": 90,
                    "implementation_artifact_grace_period_seconds": 140,
                },
                harness_monitoring_settings(root, "opencode"),
            )
            self.assertEqual(7, pi_initial_session_check_seconds(root))
            self.assertEqual(75, pi_planning_artifact_grace_period_seconds(root))
            self.assertEqual(150, pi_implementation_artifact_grace_period_seconds(root))
            self.assertEqual(
                {
                    "initial_session_check_seconds": 6,
                    "planning_artifact_grace_period_seconds": 90,
                    "implementation_artifact_grace_period_seconds": 140,
                },
                opencode_monitoring_settings(root),
            )

    def test_harness_monitoring_settings_fall_back_on_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            write_file(
                root / ".pm-dawn" / "project-profile.toml",
                textwrap.dedent(
                    """\
                    [monitoring.defaults]
                    initial_session_check_seconds = -1
                    planning_artifact_grace_period_seconds = "oops"
                    implementation_artifact_grace_period_seconds = 0
                    """
                ),
            )

            self.assertEqual(
                {
                    "initial_session_check_seconds": 5,
                    "planning_artifact_grace_period_seconds": 60,
                    "implementation_artifact_grace_period_seconds": 120,
                },
                harness_monitoring_settings(root, "pi"),
            )

    def test_harness_monitoring_settings_support_legacy_pi_monitoring_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            write_file(
                root / ".pm-dawn" / "project-profile.toml",
                textwrap.dedent(
                    """\
                    [pi.monitoring]
                    initial_session_check_seconds = 9
                    planning_artifact_grace_period_seconds = 99
                    implementation_artifact_grace_period_seconds = 199
                    """
                ),
            )

            self.assertEqual(
                {
                    "initial_session_check_seconds": 9,
                    "planning_artifact_grace_period_seconds": 99,
                    "implementation_artifact_grace_period_seconds": 199,
                },
                harness_monitoring_settings(root, "pi"),
            )

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

    def test_initialize_packet_plan_review_state_writes_proposal_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            proposal = packet_plan_proposal_artifact_path(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
            )
            proposal.write_text("# proposal\n", encoding="utf-8")

            state_path = initialize_packet_plan_review_state(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual("proposal_submitted", state["status"])
            self.assertEqual(str(proposal.resolve()), state["proposal_artifact"])
            self.assertEqual(str(proposal.resolve()), state["current_artifact"])

    def test_resolve_approved_plan_path_requires_accepted_state_when_present(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            proposal = packet_plan_proposal_artifact_path(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
            )
            proposal.write_text("# proposal\n", encoding="utf-8")
            initialize_packet_plan_review_state(
                root, "RPVINF-124", "consumer_enablement_4__01_contract"
            )

            self.assertTrue(
                packet_plan_requires_acceptance(
                    root,
                    "RPVINF-124",
                    "consumer_enablement_4__01_contract",
                )
            )
            self.assertIsNone(
                resolve_approved_plan_path(
                    root,
                    "RPVINF-124",
                    "consumer_enablement_4__01_contract",
                    None,
                )
            )

            accepted = implementation_plan_artifact_path(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
            )
            accepted.write_text("# accepted\n", encoding="utf-8")
            state_path = packet_plan_review_state_path(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
            )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["status"] = "accepted"
            state["implementation_plan_artifact"] = str(accepted.resolve())
            state_path.write_text(
                json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )

            resolved = resolve_approved_plan_path(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
                None,
            )
            self.assertEqual(accepted.resolve(), resolved)

    def test_resolve_packet_plan_review_state_reads_state_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            proposal = packet_plan_proposal_artifact_path(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
            )
            proposal.write_text("# proposal\n", encoding="utf-8")
            initialize_packet_plan_review_state(
                root, "RPVINF-124", "consumer_enablement_4__01_contract"
            )

            state = resolve_packet_plan_review_state(
                root, "RPVINF-124", "consumer_enablement_4__01_contract"
            )

            self.assertIsNotNone(state)
            assert state is not None
            self.assertEqual("proposal_submitted", state["status"])

    def test_packet_plan_monitor_state_reports_revision_response_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            state_path = packet_plan_review_state_path(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
            )
            state_path.write_text(
                json.dumps({"status": "changes_requested"}, indent=2) + "\n",
                encoding="utf-8",
            )

            monitor = packet_plan_monitor_state(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
            )

            self.assertEqual("changes_requested", monitor["status"])
            self.assertTrue(monitor["waitable"])
            self.assertTrue(monitor["requires_revision_run"])
            self.assertTrue(
                str(monitor["expected_artifact"]).endswith(
                    "consumer_enablement_4__01_contract.plan-response.md"
                )
            )

    def test_packet_plan_review_state_snapshot_marks_accepted_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            accepted = implementation_plan_artifact_path(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
            )
            accepted.write_text("# accepted\n", encoding="utf-8")
            state_path = packet_plan_review_state_path(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
            )
            state_path.write_text(
                json.dumps(
                    {
                        "status": "accepted",
                        "implementation_plan_artifact": str(accepted.resolve()),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            snapshot = packet_plan_review_state_snapshot(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
            )

            self.assertTrue(snapshot.accepted)
            self.assertFalse(snapshot.requires_revision_run)
            self.assertEqual(accepted.resolve(), snapshot.expected_artifact.resolve())

    def test_packet_plan_requires_revision_run_true_for_changes_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            state_path = packet_plan_review_state_path(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
            )
            state_path.write_text(
                json.dumps({"status": "changes_requested"}, indent=2) + "\n",
                encoding="utf-8",
            )

            self.assertTrue(
                packet_plan_requires_revision_run(
                    root,
                    "RPVINF-124",
                    "consumer_enablement_4__01_contract",
                )
            )
            expected = packet_plan_expected_artifact_path(
                root,
                "RPVINF-124",
                "consumer_enablement_4__01_contract",
            )
            assert expected is not None
            self.assertTrue(
                expected.name.endswith("consumer_enablement_4__01_contract.plan-response.md")
            )

    def test_build_launch_prompt_includes_reviewed_plan_rules(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            handoff, handoff_path = load_execution_input(
                root, "RPVINF-124", "consumer_enablement_4"
            )
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
            self.assertIn("reviewer-accepted implementation brief", prompt)
            self.assertIn("feature/RPVINF-128-consumer-enablement", prompt)
            self.assertIn(
                "python3 epic-slice-implement/scripts/mark_slice_pending_review.py",
                prompt,
            )
            self.assertIn(
                "epic-slice-implement/scripts/mark_slice_pending_review.py", prompt
            )
            self.assertIn("--repo-root .", prompt)

    def test_build_steer_prompt_references_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_repo_fixture(root)
            handoff, handoff_path = load_execution_input(
                root, "RPVINF-124", "consumer_enablement_4"
            )

            prompt = build_steer_prompt(
                handoff, handoff_path, root, "Stay within packet scope."
            )

            self.assertIn("Stay within packet scope.", prompt)
            self.assertIn(
                ".pm-dawn/epics/RPVINF-124/slices/consumer_enablement_4.md", prompt
            )


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
            self.assertTrue(
                payload["handoff_path"].endswith("consumer_enablement_4.md")
            )

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
            self.assertIn("reviewer-accepted implementation brief", result.stdout)

    def test_build_opencode_prompt_help_uses_shared_command_description(self) -> None:
        result = self.run_script(BUILD_PROMPT_SCRIPT, "--help")
        self.assertIn(
            "Build the exact launch or steer prompt for an implementation run.",
            result.stdout,
        )


class TestRuntimeHelpers(unittest.TestCase):
    def test_runtime_home_prefers_pm_dawn_home_env(self) -> None:
        with mock.patch.dict(
            "os.environ", {"PM_DAWN_HOME": "/custom/pm-dawn"}, clear=False
        ):
            self.assertEqual(Path("/custom/pm-dawn"), runtime.runtime_home())

    def test_runtime_home_uses_home_when_pm_dawn_home_missing(self) -> None:
        env = {"HOME": "/custom/home"}
        with mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(Path("/custom/home"), runtime.runtime_home())

    def test_runtime_home_returns_none_when_no_home_available(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            with mock.patch(
                "pathlib.Path.home", side_effect=RuntimeError("No home dir")
            ):
                self.assertIsNone(runtime.runtime_home())

    def test_provider_timeout_seconds_uses_env_value(self) -> None:
        with mock.patch.dict(
            "os.environ", {"PM_DAWN_PROVIDER_TIMEOUT_SECONDS": "5.5"}, clear=False
        ):
            self.assertEqual(5.5, runtime.provider_timeout_seconds())

    def test_provider_timeout_seconds_falls_back_to_default(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"PM_DAWN_PROVIDER_TIMEOUT_SECONDS": "not-a-number"},
            clear=False,
        ):
            self.assertEqual(2.0, runtime.provider_timeout_seconds())

    def test_opencode_config_path_prefers_env_override(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"PM_DAWN_OPENCODE_CONFIG_PATH": "/tmp/opencode.json"},
            clear=False,
        ):
            self.assertEqual(Path("/tmp/opencode.json"), runtime.opencode_config_path())

    def test_opencode_config_path_uses_xdg_config_home(self) -> None:
        env = {"XDG_CONFIG_HOME": "/tmp/xdg-config", "HOME": "/tmp/home"}
        with mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(
                Path("/tmp/xdg-config") / "opencode" / "opencode.json",
                runtime.opencode_config_path(),
            )

    def test_opencode_config_path_uses_home_config(self) -> None:
        env = {"HOME": "/tmp/home"}
        with mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(
                Path("/tmp/home") / ".config" / "opencode" / "opencode.json",
                runtime.opencode_config_path(),
            )

    def test_pi_models_config_path_prefers_env_override(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"PM_DAWN_PI_MODELS_CONFIG_PATH": "/tmp/pi-models.json"},
            clear=False,
        ):
            self.assertEqual(
                Path("/tmp/pi-models.json"), runtime.pi_models_config_path()
            )

    def test_pi_models_config_path_uses_home(self) -> None:
        env = {"HOME": "/tmp/home"}
        with mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(
                Path("/tmp/home") / ".pi" / "agent" / "models.json",
                runtime.pi_models_config_path(),
            )

    def test_command_available_returns_true_for_existing_command(self) -> None:
        self.assertTrue(runtime.command_available("python"))

    def test_command_available_returns_false_for_missing_command(self) -> None:
        self.assertFalse(runtime.command_available("nonexistent-command-xyz"))

    def test_require_cli_raises_for_missing_command(self) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            runtime.require_cli("nonexistent-command-xyz")
        self.assertIn(
            "required CLI 'nonexistent-command-xyz' not found", str(ctx.exception)
        )

    def test_tmux_has_session_returns_false_when_tmux_missing(self) -> None:
        with mock.patch.object(runtime, "command_available", return_value=False):
            self.assertFalse(runtime.tmux_has_session("nonexistent"))

    def test_tmux_has_session_returns_false_for_nonexistent_session(self) -> None:
        with mock.patch.object(runtime, "command_available", return_value=True):
            result = runtime.tmux_has_session("nonexistent-session-name-xyz")
            self.assertFalse(result)

    def test_resolved_shell_executable_uses_pm_dawn_shell_override(self) -> None:
        with mock.patch.dict("os.environ", {"PM_DAWN_SHELL": "/bin/sh"}, clear=False):
            self.assertEqual("/bin/sh", runtime.resolved_shell_executable())

    def test_resolved_shell_executable_falls_back_to_shell_detection(self) -> None:
        with mock.patch.dict("os.environ", {"PM_DAWN_SHELL": ""}, clear=False):
            shell = runtime.resolved_shell_executable()
            self.assertIn("/", shell)

    def test_resolved_shell_executable_skips_non_executable_match(self) -> None:
        with mock.patch.dict(
            "os.environ", {"PM_DAWN_SHELL": "/tmp/not-executable", "SHELL": ""},
            clear=True
        ):
            with mock.patch("shutil.which", side_effect=["/tmp/not-executable", "/bin/sh"]):
                with mock.patch("os.access", side_effect=[False, True]):
                    self.assertEqual("/bin/sh", runtime.resolved_shell_executable())

    def test_resolved_shell_executable_raises_when_no_shell_available(self) -> None:
        with mock.patch.dict(
            "os.environ", {"PM_DAWN_SHELL": "", "SHELL": ""}, clear=True
        ):
            with mock.patch("shutil.which", return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    runtime.resolved_shell_executable()
                self.assertIn("no usable shell found", str(ctx.exception))

    def test_run_cmd_includes_exit_code_when_process_has_no_output(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["example", "arg with spaces"],
            returncode=7,
            stdout="",
            stderr="",
        )
        with mock.patch("subprocess.run", return_value=completed):
            with self.assertRaises(RuntimeError) as ctx:
                runtime.run_cmd(["example", "arg with spaces"])
        self.assertIn("exit code 7", str(ctx.exception))
        self.assertIn("arg with spaces", str(ctx.exception))

    def test_epic_slice_plan_tracked_files_uses_shared_run_cmd(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["rg", "--files", "."],
            returncode=0,
            stdout="alpha.py\nbeta.py\n",
            stderr="",
        )
        with mock.patch.object(
            epic_slice_plan_common, "run_cmd", return_value=completed
        ) as run_cmd_mock:
            result = epic_slice_plan_common.tracked_files(Path("/tmp/repo"), ".")

        self.assertEqual(["alpha.py", "beta.py"], result)
        run_cmd_mock.assert_called_once_with(["rg", "--files", "."], cwd=Path("/tmp/repo"))

    def test_jira_pr_current_branch_uses_shared_run_cmd(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["git", "branch", "--show-current"],
            returncode=0,
            stdout="feature/runtime-tests\n",
            stderr="",
        )
        with mock.patch.object(
            jira_pr_common, "run_cmd", return_value=completed
        ) as run_cmd_mock:
            branch = jira_pr_common.current_branch(Path("/tmp/repo"))

        self.assertEqual("feature/runtime-tests", branch)
        run_cmd_mock.assert_called_once_with(
            ["git", "branch", "--show-current"], cwd=Path("/tmp/repo")
        )

    def test_jira_epic_review_run_acli_uses_shared_runtime_helpers(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["acli", "jira", "auth", "status"],
            returncode=0,
            stdout='{"ok":true}\n',
            stderr="",
        )
        with mock.patch.object(
            jira_epic_review_common, "require_cli"
        ) as require_cli_mock, mock.patch.object(
            jira_epic_review_common, "run_cmd", return_value=completed
        ) as run_cmd_mock:
            output = jira_epic_review_common.run_acli(["jira", "auth", "status"])

        self.assertEqual('{"ok":true}\n', output)
        require_cli_mock.assert_called_once_with("acli")
        run_cmd_mock.assert_called_once_with(
            ["acli", "jira", "auth", "status"], check=False
        )


if __name__ == "__main__":
    unittest.main()
