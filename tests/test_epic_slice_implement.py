"""CLI smoke tests for epic-slice-implement lifecycle entrypoints."""

from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = REPO_ROOT / "epic-slice-implement" / "scripts"
COMMON_SPEC = importlib.util.spec_from_file_location(
    "epic_slice_implement_common", SCRIPT_ROOT / "common.py"
)
assert COMMON_SPEC is not None and COMMON_SPEC.loader is not None
implement_common = importlib.util.module_from_spec(COMMON_SPEC)
COMMON_SPEC.loader.exec_module(implement_common)

PI_EMBEDDED_SPEC = importlib.util.spec_from_file_location(
    "epic_slice_implement_harness_pi_embedded",
    SCRIPT_ROOT / "harness_pi_embedded.py",
)
assert PI_EMBEDDED_SPEC is not None and PI_EMBEDDED_SPEC.loader is not None
harness_pi_embedded = importlib.util.module_from_spec(PI_EMBEDDED_SPEC)
sys.modules[PI_EMBEDDED_SPEC.name] = harness_pi_embedded
PI_EMBEDDED_SPEC.loader.exec_module(harness_pi_embedded)

SLICE_STATUS = REPO_ROOT / "epic-slice-implement" / "scripts" / "slice_status.py"
CLEANUP_SLICE_ARTIFACTS = (
    REPO_ROOT / "epic-slice-implement" / "scripts" / "cleanup_slice_artifacts.py"
)
CLEANUP_SLICE_BY_NAME = (
    REPO_ROOT / "epic-slice-implement" / "scripts" / "cleanup_slice_by_name.py"
)
GENERATE_PACKET_IMPLEMENTATION_PLAN = (
    REPO_ROOT
    / "epic-slice-implement"
    / "scripts"
    / "generate_packet_implementation_plan.py"
)
COORDINATE_PLAN_REVIEW = (
    REPO_ROOT / "epic-slice-implement" / "scripts" / "coordinate_plan_review.py"
)
STEER_SLICE = REPO_ROOT / "epic-slice-implement" / "scripts" / "steer_slice.py"
MIGRATE_PM_DAWN_LAYOUT = (
    REPO_ROOT / "epic-slice-implement" / "scripts" / "migrate_pm_dawn_layout.py"
)
LAUNCH_SLICE_SESSION = (
    REPO_ROOT / "epic-slice-implement" / "scripts" / "launch_slice_session.py"
)


def write_fixture(path: Path, content: str = "fixture\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_slice_fixture(
    root: Path, *, epic_key: str = "RPVINF-124", group_id: str = "consumer_enablement_3"
) -> None:
    epic_root = root / ".pm-dawn" / "epics" / epic_key
    fixture_files = {
        "slices": [f"{group_id}.md"],
        "plans": [f"{group_id}.plan.md"],
        "packets": [f"{group_id}__01_contract.md", f"{group_id}__02_wiring.md"],
        "ops/handoffs": [f"{group_id}__01_contract.json"],
        "ops/pr": [
            f"{group_id}.title.txt",
            f"{group_id}.body.md",
            f"{group_id}.verify.json",
            f"{group_id}__01_contract.title.txt",
            f"{group_id}__01_contract.body.md",
            f"{group_id}__01_contract.verify.json",
        ],
        "ops/artifacts": [
            f"{group_id}__01_contract.implementation-plan.md",
            f"{group_id}__01_contract.plan-proposal.md",
            f"{group_id}__01_contract.plan-review.json",
        ],
        "ops/runs": [
            f"{group_id}.json",
            f"{group_id}.plan.md",
            f"{group_id}.result.md",
        ],
    }
    for directory, filenames in fixture_files.items():
        for filename in filenames:
            write_fixture(epic_root / directory / filename)


class TestEpicSliceImplementLifecycleScripts(unittest.TestCase):
    def run_script(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    def write_minimal_slice(self, root: Path) -> Path:
        slice_path = (
            root
            / ".pm-dawn"
            / "epics"
            / "RPVINF-134"
            / "slices"
            / "embedded_pi_session_adapter.md"
        )
        write_fixture(
            slice_path,
            "\n".join(
                [
                    "# RPVINF-134 / embedded_pi_session_adapter",
                    "",
                    "Group ID: embedded_pi_session_adapter",
                    "Primary Jira Key: RPVINF-134",
                    "Secondary Jira Keys: None",
                    "",
                    "Goal:",
                    "- Evaluate an embedded Pi session adapter.",
                    "",
                    "Branch Recommendation:",
                    "- feature/RPVINF-134-embedded-pi-session-adapter",
                    "",
                    "PR Traceability:",
                    "- Primary: RPVINF-134",
                    "- Additional: None",
                    "",
                    "Entry Criteria:",
                    "- None",
                    "",
                    "Exit Criteria:",
                    "- None",
                    "",
                    "Repo Surfaces:",
                    "- epic-slice-implement/scripts/harness_pi_embedded.py",
                    "",
                    "Implementation Steps:",
                    "- Keep embedded Pi sessions optional.",
                    "",
                    "Validation Steps:",
                    "- Run make check.",
                    "",
                    "Risks and Constraints:",
                    "- Do not change PM Dawn core runtime dependencies.",
                    "",
                    "Open Questions:",
                    "- None",
                    "",
                    "Source Review Context:",
                    "- Derived from Jira story RPVINF-134 on 2026-04-26.",
                    "",
                ]
            ),
        )
        return slice_path

    def test_cleanup_slice_artifacts_dry_run_uses_shared_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_slice_fixture(root)

            result = self.run_script(
                CLEANUP_SLICE_ARTIFACTS,
                "RPVINF-124",
                "consumer_enablement_3",
                "--repo-root",
                str(root),
                "--mode",
                "archive",
                "--dry-run",
            )

            payload = json.loads(result.stdout)
            self.assertEqual("RPVINF-124", payload["epic_key"])
            self.assertEqual("consumer_enablement_3", payload["group_id"])
            self.assertTrue(payload["dry_run"])
            self.assertEqual(17, payload["target_count"])
            archived_paths = {str(Path(item).resolve()) for item in payload["archived"]}
            self.assertIn(
                str(
                    (
                        root
                        / ".pm-dawn"
                        / "archive"
                        / "RPVINF-124"
                        / "consumer_enablement_3"
                        / "ops"
                        / "artifacts"
                        / "consumer_enablement_3__01_contract.implementation-plan.md"
                    ).resolve()
                ),
                archived_paths,
            )
            self.assertTrue(
                (
                    root
                    / ".pm-dawn"
                    / "epics"
                    / "RPVINF-124"
                    / "slices"
                    / "consumer_enablement_3.md"
                ).exists()
            )

    def test_cleanup_slice_by_name_resolves_epic_and_reuses_cleanup_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_slice_fixture(root)

            result = self.run_script(
                CLEANUP_SLICE_BY_NAME,
                "consumer_enablement_3",
                "--repo-root",
                str(root),
                "--mode",
                "archive",
                "--dry-run",
            )

            payload = json.loads(result.stdout)
            self.assertEqual("RPVINF-124", payload["resolved_epic_key"])
            self.assertEqual(17, payload["target_count"])
            target_paths = {str(Path(item).resolve()) for item in payload["targets"]}
            self.assertIn(
                str(
                    (
                        root
                        / ".pm-dawn"
                        / "epics"
                        / "RPVINF-124"
                        / "packets"
                        / "consumer_enablement_3__02_wiring.md"
                    ).resolve()
                ),
                target_paths,
            )

    def test_slice_status_reports_pi_runtime_without_session_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_metadata = (
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "runs"
                / "consumer_enablement_3.json"
            )
            write_fixture(
                run_metadata,
                json.dumps(
                    {
                        "schema_version": "v1",
                        "epic_key": "RPVINF-124",
                        "group_id": "consumer_enablement_3",
                        "handoff_path": str(
                            root
                            / ".pm-dawn"
                            / "epics"
                            / "RPVINF-124"
                            / "ops"
                            / "handoffs"
                            / "consumer_enablement_3__02_wiring.json"
                        ),
                        "packet_id": "consumer_enablement_3__02_wiring",
                        "branch_name": "feature/RPVINF-127-consumer-enablement",
                        "harness": "pi",
                        "runtime_mode": "tmux-run",
                        "model": "qwen/qwen3-coder-next-q6k",
                        "status": "pending_review",
                        "phase": "implementing",
                        "completion_state": "in_progress",
                        "runtime": {
                            "server_url": None,
                            "session_id": None,
                            "tmux_session": "pi-RPVINF-124-consumer_enablement_3__02_wiring",
                            "server_tmux_session": None,
                            "session_dir": str(
                                root
                                / ".pm-dawn"
                                / "epics"
                                / "RPVINF-124"
                                / "ops"
                                / "runs"
                                / "pi-sessions"
                                / "consumer_enablement_3__02_wiring"
                                / "implementing"
                            ),
                        },
                        "last_action": "worker_marked_pending_review",
                        "attach_instructions": [
                            "tmux attach -t pi-RPVINF-124-consumer_enablement_3__02_wiring"
                        ],
                        "artifacts": {
                            "implementation_plan_md": str(
                                root
                                / ".pm-dawn"
                                / "epics"
                                / "RPVINF-124"
                                / "ops"
                                / "artifacts"
                                / "consumer_enablement_3__02_wiring.implementation-plan.md"
                            )
                        },
                        "worker": {"status": "pending_review"},
                    },
                    indent=2,
                )
                + "\n",
            )

            result = self.run_script(
                SLICE_STATUS,
                "RPVINF-124",
                "consumer_enablement_3",
                "--repo-root",
                str(root),
            )

            payload = json.loads(result.stdout)
            self.assertEqual("pi", payload["harness"])
            self.assertEqual("pending_review", payload["status"])
            self.assertEqual("in_progress", payload["completion_state"])
            self.assertEqual("pending_review", payload["implementation_monitor"]["status"])
            self.assertTrue(payload["implementation_monitor"]["review_ready"])
            self.assertEqual("review_result", payload["implementation_monitor"]["next_action"])
            self.assertEqual("pending_review", payload["status"])
            self.assertEqual("implementing", payload["phase"])
            self.assertEqual("in_progress", payload["completion_state"])
            self.assertEqual("tmux-run", payload["runtime_mode"])
            self.assertEqual(
                "pi-RPVINF-124-consumer_enablement_3__02_wiring",
                payload["tmux_session"],
            )
            self.assertEqual(
                ["tmux attach -t pi-RPVINF-124-consumer_enablement_3__02_wiring"],
                payload["attach_instructions"],
            )
            self.assertIsNone(payload["last_completed_at"])

    def test_generate_packet_implementation_plan_help_uses_shared_description(
        self,
    ) -> None:
        result = self.run_script(GENERATE_PACKET_IMPLEMENTATION_PLAN, "--help")
        self.assertIn(
            "Generate a worker-authored packet plan proposal artifact.",
            result.stdout,
        )

    def test_coordinate_plan_review_accept_copies_proposal_to_implementation_brief(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            proposal = (
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "artifacts"
                / "consumer_enablement_3__01_contract.plan-proposal.md"
            )
            write_fixture(proposal, "# accepted plan\n")

            result = self.run_script(
                COORDINATE_PLAN_REVIEW,
                "RPVINF-124",
                "consumer_enablement_3",
                "consumer_enablement_3__01_contract",
                "--repo-root",
                str(root),
                "--action",
                "accept",
            )

            payload = json.loads(result.stdout)
            self.assertEqual("accepted", payload["status"])
            implementation_brief = (
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "artifacts"
                / "consumer_enablement_3__01_contract.implementation-plan.md"
            )
            self.assertEqual(
                "# accepted plan\n", implementation_brief.read_text(encoding="utf-8")
            )
            state = json.loads(
                (
                    root
                    / ".pm-dawn"
                    / "epics"
                    / "RPVINF-124"
                    / "ops"
                    / "artifacts"
                    / "consumer_enablement_3__01_contract.plan-review.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual("accepted", state["status"])
            self.assertEqual(
                str(implementation_brief.resolve()),
                state["implementation_plan_artifact"],
            )

    def test_coordinate_plan_review_submit_review_requires_existing_custom_artifact(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()

            result = subprocess.run(
                [
                    sys.executable,
                    str(COORDINATE_PLAN_REVIEW),
                    "RPVINF-124",
                    "consumer_enablement_3",
                    "consumer_enablement_3__01_contract",
                    "--repo-root",
                    str(root),
                    "--action",
                    "submit-review",
                    "--artifact",
                    str(root / "missing-review.md"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn("plan review artifact not found", result.stderr)

    def test_generate_packet_implementation_plan_blocks_when_review_is_already_accepted(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_slice_fixture(root)
            state_path = (
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "artifacts"
                / "consumer_enablement_3__01_contract.plan-review.json"
            )
            state_path.write_text(
                json.dumps({"status": "accepted"}, indent=2) + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(GENERATE_PACKET_IMPLEMENTATION_PLAN),
                    "RPVINF-124",
                    "consumer_enablement_3",
                    "consumer_enablement_3__01_contract",
                    "--repo-root",
                    str(root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn("already accepted", result.stderr)

    def test_generate_packet_implementation_plan_blocks_when_response_already_submitted(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_slice_fixture(root)
            state_path = (
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "artifacts"
                / "consumer_enablement_3__01_contract.plan-review.json"
            )
            state_path.write_text(
                json.dumps({"status": "response_submitted"}, indent=2) + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(GENERATE_PACKET_IMPLEMENTATION_PLAN),
                    "RPVINF-124",
                    "consumer_enablement_3",
                    "consumer_enablement_3__01_contract",
                    "--repo-root",
                    str(root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(1, result.returncode)
            self.assertIn("response is already submitted", result.stderr)

    def test_slice_status_includes_plan_review_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            run_metadata = (
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "runs"
                / "consumer_enablement_3.json"
            )
            write_fixture(
                run_metadata,
                json.dumps(
                    {
                        "schema_version": "v1",
                        "epic_key": "RPVINF-124",
                        "group_id": "consumer_enablement_3",
                        "packet_id": "consumer_enablement_3__02_wiring",
                        "harness": "pi",
                        "runtime_mode": "tmux-run",
                        "status": "pending_review",
                        "phase": "implementing",
                        "completion_state": "in_progress",
                        "runtime": {},
                        "worker": {"status": "pending_review"},
                    },
                    indent=2,
                )
                + "\n",
            )
            write_fixture(
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "artifacts"
                / "consumer_enablement_3__02_wiring.plan-review.json",
                json.dumps({"status": "changes_requested"}, indent=2) + "\n",
            )

            result = self.run_script(
                SLICE_STATUS,
                "RPVINF-124",
                "consumer_enablement_3",
                "--repo-root",
                str(root),
            )

            payload = json.loads(result.stdout)
            self.assertEqual("changes_requested", payload["plan_review"]["status"])
            self.assertEqual("changes_requested", payload["plan_monitor"]["status"])
            self.assertTrue(payload["plan_monitor"]["requires_revision_run"])
            self.assertTrue(
                payload["plan_monitor"]["expected_artifact"].endswith(
                    "consumer_enablement_3__02_wiring.plan-response.md"
                )
            )

    def test_slice_status_surfaces_embedded_session_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            run_metadata = (
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-134"
                / "ops"
                / "runs"
                / "embedded_pi_session_adapter.json"
            )
            write_fixture(
                run_metadata,
                json.dumps(
                    {
                        "schema_version": "v1",
                        "epic_key": "RPVINF-134",
                        "group_id": "embedded_pi_session_adapter",
                        "harness": "pi",
                        "runtime_mode": "embedded",
                        "status": "running",
                        "phase": "planning",
                        "completion_state": "in_progress",
                        "runtime": {},
                        "embedded_session": {
                            "state": "unavailable",
                            "session_id": None,
                            "capabilities": {"available": False, "reason": "fallback"},
                            "events": [],
                            "fallback_reason": "fallback",
                        },
                    },
                    indent=2,
                )
                + "\n",
            )

            result = self.run_script(
                SLICE_STATUS,
                "RPVINF-134",
                "embedded_pi_session_adapter",
                "--repo-root",
                str(root),
            )

            payload = json.loads(result.stdout)
            self.assertEqual("embedded", payload["runtime_mode"])
            self.assertEqual("unavailable", payload["embedded_session"]["state"])

    def test_migrate_pm_dawn_layout_dry_run_reports_canonical_follow_up_commands(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            (root / ".git").mkdir()

            result = self.run_script(
                MIGRATE_PM_DAWN_LAYOUT,
                "--repo-root",
                str(root),
                "--dry-run",
            )

            payload = json.loads(result.stdout)
            self.assertEqual(
                "python epic-slice-implement/scripts/load_handoff.py "
                "'<epic-key>' '<group-id>' --repo-root .",
                payload["recommended_commands"]["load_handoff"],
            )
            self.assertEqual(
                "python epic-slice-implement/scripts/launch_slice_session.py "
                "'<epic-key>' '<group-id>' --repo-root .",
                payload["recommended_commands"]["launch"],
            )
            self.assertTrue(payload["ignore_pm_dawn"])
            self.assertEqual(
                "would_create_gitignore", payload["ignore_state"]["status"]
            )
            self.assertTrue(payload["ignore_state"]["path"].endswith(".gitignore"))

    def test_migrate_pm_dawn_layout_creates_gitignore_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            (root / ".git").mkdir()

            result = self.run_script(
                MIGRATE_PM_DAWN_LAYOUT,
                "--repo-root",
                str(root),
            )

            payload = json.loads(result.stdout)
            self.assertTrue(payload["ignore_pm_dawn"])
            self.assertEqual("created_gitignore", payload["ignore_state"]["status"])
            self.assertEqual(
                ".pm-dawn/\n", (root / ".gitignore").read_text(encoding="utf-8")
            )

    def test_migrate_pm_dawn_layout_skips_ignore_when_opted_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            (root / ".git").mkdir()

            result = self.run_script(
                MIGRATE_PM_DAWN_LAYOUT,
                "--repo-root",
                str(root),
                "--no-ignore-pm-dawn",
            )

            payload = json.loads(result.stdout)
            self.assertFalse(payload["ignore_pm_dawn"])
            self.assertIsNone(payload["ignore_state"])
            self.assertFalse((root / ".gitignore").exists())

    def test_launch_slice_session_dry_run_uses_harness_monitoring_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            build_slice_fixture(root)
            write_fixture(
                root / ".git" / "HEAD",
                "ref: refs/heads/main\n",
            )
            write_fixture(
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "slices"
                / "consumer_enablement_3.md",
                "\n".join(
                    [
                        "# RPVINF-124 / consumer_enablement_3",
                        "",
                        "Group ID: consumer_enablement_3",
                        "Primary Jira Key: RPVINF-127",
                        "Secondary Jira Keys: None",
                        "",
                        "Goal:",
                        "- Validate monitoring config flow for harness dry runs.",
                        "",
                        "Branch Recommendation:",
                        "- feature/RPVINF-133-unattended-negotiation",
                        "",
                        "PR Traceability:",
                        "- Primary: RPVINF-133",
                        "- Additional: None",
                        "",
                        "Entry Criteria:",
                        "- None",
                        "",
                        "Exit Criteria:",
                        "- None",
                        "",
                        "Repo Surfaces:",
                        "- epic-slice-implement/",
                        "",
                        "Implementation Steps:",
                        "- Keep the packet handoff loadable.",
                        "",
                        "Validation Steps:",
                        "- Run make check.",
                        "",
                        "Risks and Constraints:",
                        "- None",
                        "",
                        "Open Questions:",
                        "- None",
                        "",
                        "Source Review Context:",
                        "- Derived from epic review of RPVINF-124 on 2026-04-20.",
                        "- This story is best handled as an individual PR-sized unit after its blockers land.",
                        "",
                    ]
                ),
            )
            write_fixture(
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "packets"
                / "consumer_enablement_3__01_contract.md",
                "\n".join(
                    [
                        "# RPVINF-124 / consumer_enablement_3__01_contract",
                        "",
                        "Packet ID:",
                        "- consumer_enablement_3__01_contract",
                        "",
                        "Goal:",
                        "- Keep the packet handoff loadable for dry-run monitoring tests.",
                        "",
                        "Why This Packet Is Isolated:",
                        "- Packet type: contract",
                        "",
                        "Depends On:",
                        "- None",
                        "",
                        "Files to Read:",
                        "- epic-slice-implement/scripts/launch_slice_session.py",
                        "",
                        "Files to Change:",
                        "- epic-slice-implement/scripts/launch_slice_session.py",
                        "",
                        "Implementation Steps:",
                        "- Exercise dry-run monitoring payloads.",
                        "",
                        "Validation Steps:",
                        "- Run make check.",
                        "",
                        "Acceptance Checks:",
                        "- Dry-run payload resolves monitoring settings correctly.",
                        "",
                        "Constraints:",
                        "- None",
                        "",
                        "Open Questions:",
                        "- None",
                        "",
                        "Execution Routing:",
                        "- Risk Class: mechanical",
                        "- Recommended Executor: local_small_model",
                        "",
                        "Branch Recommendation:",
                        "- feature/RPVINF-133-unattended-negotiation",
                        "",
                        "Commit Scope Guidance:",
                        "- Keep the change narrow.",
                        "",
                        "Jira Traceability:",
                        "- Primary: RPVINF-133",
                        "- Additional: None",
                        "",
                    ]
                ),
            )
            write_fixture(
                root / ".pm-dawn" / "project-profile.toml",
                "\n".join(
                    [
                        "[monitoring.defaults]",
                        "initial_session_check_seconds = 5",
                        "planning_artifact_grace_period_seconds = 60",
                        "implementation_artifact_grace_period_seconds = 120",
                        "",
                        "[monitoring.opencode]",
                        "initial_session_check_seconds = 45",
                        "planning_artifact_grace_period_seconds = 95",
                    ]
                )
                + "\n",
            )
            review_state = (
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "artifacts"
                / "consumer_enablement_3__01_contract.plan-review.json"
            )
            review_state.write_text(
                json.dumps(
                    {
                        "status": "accepted",
                        "implementation_plan_artifact": str(
                            (
                                root
                                / ".pm-dawn"
                                / "epics"
                                / "RPVINF-124"
                                / "ops"
                                / "artifacts"
                                / "consumer_enablement_3__01_contract.implementation-plan.md"
                            ).resolve()
                        ),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            result = self.run_script(
                LAUNCH_SLICE_SESSION,
                "RPVINF-124",
                "consumer_enablement_3",
                "--packet-id",
                "consumer_enablement_3__01_contract",
                "--repo-root",
                str(root),
                "--harness",
                "opencode",
                "--phase",
                "implementing",
                "--dry-run",
            )

            payload = json.loads(result.stdout)
            self.assertEqual("opencode", payload["harness"])
            self.assertEqual(
                {
                    "initial_session_check_seconds": 45,
                    "planning_artifact_grace_period_seconds": 95,
                    "implementation_artifact_grace_period_seconds": 120,
                },
                payload["monitoring"],
            )
            self.assertEqual("in_progress", payload["implementation_monitor"]["completion_state"])
            self.assertFalse(payload["implementation_monitor"]["review_ready"])
            self.assertTrue(payload["implementation_monitor"]["waitable"])
            self.assertEqual("wait_for_worker", payload["implementation_monitor"]["next_action"])

    def test_launch_slice_session_pi_embedded_dry_run_reports_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            self.write_minimal_slice(root)

            result = self.run_script(
                LAUNCH_SLICE_SESSION,
                "RPVINF-134",
                "embedded_pi_session_adapter",
                "--repo-root",
                str(root),
                "--harness",
                "pi",
                "--runtime",
                "embedded",
                "--phase",
                "planning",
                "--dry-run",
            )

            payload = json.loads(result.stdout)
            self.assertEqual("pi", payload["harness"])
            self.assertEqual("embedded", payload["runtime_mode"])
            if payload["embedded_session"]["capabilities"]["available"]:
                self.assertEqual("idle", payload["embedded_session"]["state"])
                self.assertEqual("pi-rpc-jsonl", payload["embedded_session"]["protocol"])
            else:
                self.assertEqual("unavailable", payload["embedded_session"]["state"])
                self.assertIn("fall back", payload["embedded_session"]["fallback_reason"])

    def test_launch_slice_session_pi_embedded_available_uses_embedded_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            self.write_minimal_slice(root)
            embedded_snapshot = harness_pi_embedded.PiEmbeddedSessionSnapshot(
                session_id="pi-embedded-1",
                state="idle",
                capabilities=harness_pi_embedded.PiEmbeddedCapabilities(
                    available=True,
                    reason="fixture",
                    supports_events=True,
                    supports_steer=True,
                ),
                events=[{"kind": "SESSION_START"}],
                session_dir=str(root / ".pm-dawn" / "epics" / "RPVINF-134" / "ops" / "runs" / "pi-sessions" / "embedded_pi_session_adapter" / "planning"),
                protocol="pi-rpc-jsonl",
            )
            launch_spec = importlib.util.spec_from_file_location(
                "epic_slice_launch_embedded_available_test",
                LAUNCH_SLICE_SESSION,
            )
            assert launch_spec is not None and launch_spec.loader is not None
            launch_module = importlib.util.module_from_spec(launch_spec)
            original_common = sys.modules.pop("common", None)
            original_harness = sys.modules.pop("harness_pi_embedded", None)
            try:
                with mock.patch.object(sys, "path", [str(SCRIPT_ROOT), *sys.path]):
                    launch_spec.loader.exec_module(launch_module)
            finally:
                sys.modules.pop("common", None)
                sys.modules.pop("harness_pi_embedded", None)
                if original_common is not None:
                    sys.modules["common"] = original_common
                if original_harness is not None:
                    sys.modules["harness_pi_embedded"] = original_harness

            with mock.patch.object(
                launch_module,
                "parse_args",
                return_value=type(
                    "Args",
                    (),
                    {
                        "epic_key": "RPVINF-134",
                        "group_id": "embedded_pi_session_adapter",
                        "packet_id": None,
                        "repo_root": str(root),
                        "runtime": "embedded",
                        "phase": "planning",
                        "approved_plan": None,
                        "harness": "pi",
                        "model": "qwen/qwen3-coder-next-q6k",
                        "server_url": "http://127.0.0.1:4096",
                        "dry_run": False,
                    },
                )(),
            ), mock.patch.object(
                launch_module, "require_cli"
            ), mock.patch.object(
                launch_module.PiEmbeddedSessionAdapter,
                "submit",
                return_value=embedded_snapshot,
            ), mock.patch.object(
                launch_module, "launch_tmux_session_with_tail"
            ) as launch_tmux, mock.patch.object(
                launch_module, "record_run"
            ) as record_run, mock.patch.object(
                launch_module, "emit_json"
            ) as emit_json:
                launch_module.main()

            payload = emit_json.call_args.args[0]
            self.assertEqual("embedded", payload["runtime_mode"])
            self.assertTrue(payload["embedded_session"]["capabilities"]["available"])
            self.assertEqual("pi-embedded-1", payload["embedded_session"]["session_id"])
            launch_tmux.assert_not_called()
            record_payload = record_run.call_args.args[3]
            self.assertEqual("embedded", record_payload["runtime_mode"])
            self.assertEqual("pi-embedded-1", record_payload["embedded_session"]["session_id"])

    def test_sync_slice_session_state_non_opencode_includes_implementation_monitor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            run_metadata = (
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "runs"
                / "consumer_enablement_3.json"
            )
            write_fixture(
                run_metadata,
                json.dumps(
                    {
                        "schema_version": "v1",
                        "epic_key": "RPVINF-124",
                        "group_id": "consumer_enablement_3",
                        "packet_id": "consumer_enablement_3__02_wiring",
                        "harness": "pi",
                        "phase": "implementing",
                        "status": "pending_review",
                        "completion_state": "in_progress",
                        "last_action": "worker_marked_pending_review",
                        "worker": {"status": "pending_review"},
                        "runtime": {"session_dir": "/tmp/pi"},
                        "embedded_session": {
                            "state": "unavailable",
                            "session_id": None,
                            "capabilities": {"available": False, "reason": "fallback"},
                            "events": [],
                            "fallback_reason": "fallback",
                        },
                        "artifacts": {},
                    },
                    indent=2,
                )
                + "\n",
            )

            result = self.run_script(
                SCRIPT_ROOT / "sync_slice_session_state.py",
                "RPVINF-124",
                "consumer_enablement_3",
                "--repo-root",
                str(root),
            )

            payload = json.loads(result.stdout)
            self.assertEqual("pending_review", payload["status"])
            self.assertEqual("in_progress", payload["completion_state"])
            self.assertTrue(payload["implementation_monitor"]["review_ready"])
            self.assertEqual("review_result", payload["implementation_monitor"]["next_action"])
            self.assertEqual("unavailable", payload["embedded_session"]["state"])

    def test_sync_slice_session_state_does_not_write_result_without_flag_at_review_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            run_metadata = (
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "runs"
                / "consumer_enablement_3.json"
            )
            write_fixture(
                run_metadata,
                json.dumps(
                    {
                        "schema_version": "v1",
                        "epic_key": "RPVINF-124",
                        "group_id": "consumer_enablement_3",
                        "packet_id": "consumer_enablement_3__02_wiring",
                        "harness": "opencode",
                        "phase": "implementing",
                        "status": "running",
                        "completion_state": "in_progress",
                        "last_action": "worker_marked_pending_review",
                        "worker": {"status": "pending_review"},
                        "runtime": {"session_id": "ses_test"},
                        "artifacts": {},
                        "time": {"created": "2026-04-24T00:00:00Z"},
                    },
                    indent=2,
                )
                + "\n",
            )
            sync_spec = importlib.util.spec_from_file_location(
                "epic_slice_sync_state_test",
                SCRIPT_ROOT / "sync_slice_session_state.py",
            )
            assert sync_spec is not None and sync_spec.loader is not None
            sync_module = importlib.util.module_from_spec(sync_spec)
            session_export = {
                "info": {"id": "ses_test", "title": "test session"},
                "messages": [
                    {
                        "info": {
                            "role": "assistant",
                            "time": {"completed": "2026-04-24T00:00:05Z"},
                            "finish": "stop",
                        },
                        "parts": [{"type": "text", "text": "done"}],
                    }
                ],
            }

            original_common = sys.modules.pop("common", None)
            try:
                with mock.patch.object(sys, "path", [str(SCRIPT_ROOT), *sys.path]):
                    sync_spec.loader.exec_module(sync_module)
            finally:
                sys.modules.pop("common", None)
                if original_common is not None:
                    sys.modules["common"] = original_common

            with mock.patch.object(
                sync_module,
                "parse_args",
                return_value=type(
                    "Args",
                    (),
                    {
                        "epic_key": "RPVINF-124",
                        "group_id": "consumer_enablement_3",
                        "repo_root": str(root),
                        "phase": None,
                        "write_artifacts": False,
                        "overwrite_artifacts": False,
                    },
                )(),
            ), mock.patch.object(
                sync_module, "export_session_json", return_value=session_export
            ), mock.patch.object(sync_module, "emit_json"):
                sync_module.main()

            result_path = (
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "runs"
                / "consumer_enablement_3.result.md"
            )
            self.assertFalse(result_path.exists())
            updated = json.loads(run_metadata.read_text(encoding="utf-8"))
            self.assertEqual("pending_review", updated["status"])
            self.assertEqual("in_progress", updated["completion_state"])
            self.assertEqual({}, updated["artifacts"])
    def test_steer_slice_stops_at_pending_review_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            write_fixture(
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "slices"
                / "consumer_enablement_3.md",
                "\n".join(
                    [
                        "# RPVINF-124 / consumer_enablement_3",
                        "",
                        "Group ID: consumer_enablement_3",
                        "Primary Jira Key: RPVINF-127",
                        "Secondary Jira Keys: None",
                        "",
                        "Goal:",
                        "- Validate unattended implementation review coordination.",
                        "",
                        "Branch Recommendation:",
                        "- feature/RPVINF-135-implementation-review",
                        "",
                        "PR Traceability:",
                        "- Primary: RPVINF-135",
                        "- Additional: None",
                        "",
                        "Entry Criteria:",
                        "- None",
                        "",
                        "Exit Criteria:",
                        "- None",
                        "",
                        "Repo Surfaces:",
                        "- epic-slice-implement/",
                        "",
                        "Implementation Steps:",
                        "- Keep the slice handoff loadable.",
                        "",
                        "Validation Steps:",
                        "- Run make check.",
                        "",
                        "Risks and Constraints:",
                        "- None",
                        "",
                        "Open Questions:",
                        "- None",
                        "",
                        "Source Review Context:",
                        "- Derived from epic review of RPVINF-124 on 2026-04-23.",
                        "- This story is best handled as an individual PR-sized unit after its blockers land.",
                        "",
                    ]
                ),
            )
            write_fixture(
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "runs"
                / "consumer_enablement_3.json",
                json.dumps(
                    {
                        "schema_version": "v1",
                        "epic_key": "RPVINF-124",
                        "group_id": "consumer_enablement_3",
                        "packet_id": "consumer_enablement_3__02_wiring",
                        "handoff_path": str(
                            root
                            / ".pm-dawn"
                            / "epics"
                            / "RPVINF-124"
                            / "slices"
                            / "consumer_enablement_3.md"
                        ),
                        "branch_name": "feature/RPVINF-135-implementation-review",
                        "harness": "opencode",
                        "runtime_mode": "server",
                        "status": "pending_review",
                        "phase": "implementing",
                        "completion_state": "in_progress",
                        "last_action": "worker_marked_pending_review",
                        "attach_instructions": ["tmux attach -t opencode-session"],
                        "worker": {"status": "pending_review"},
                    },
                    indent=2,
                )
                + "\n",
            )

            result = self.run_script(
                STEER_SLICE,
                "RPVINF-124",
                "consumer_enablement_3",
                "Please keep going",
                "--repo-root",
                str(root),
            )

            payload = json.loads(result.stdout)
            self.assertEqual("review_boundary_reached", payload["status"])
            self.assertTrue(payload["implementation_monitor"]["review_ready"])
            self.assertEqual(["tmux attach -t opencode-session"], payload["attach_instructions"])

    def test_steer_slice_pi_embedded_reports_revision_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            slice_path = self.write_minimal_slice(root)
            write_fixture(
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-134"
                / "ops"
                / "runs"
                / "embedded_pi_session_adapter.json",
                json.dumps(
                    {
                        "schema_version": "v1",
                        "epic_key": "RPVINF-134",
                        "group_id": "embedded_pi_session_adapter",
                        "handoff_path": str(slice_path),
                        "branch_name": "feature/RPVINF-134-embedded-pi-session-adapter",
                        "harness": "pi",
                        "runtime_mode": "tmux-run",
                        "status": "running",
                        "phase": "implementing",
                        "completion_state": "in_progress",
                        "last_action": "launch",
                        "attach_instructions": ["tmux attach -t pi-RPVINF-134-embedded"],
                        "embedded_session": {
                            "state": "unavailable",
                            "session_id": None,
                            "capabilities": {"available": False, "reason": "fallback"},
                            "events": [],
                            "fallback_reason": "fallback",
                        },
                        "worker": {},
                    },
                    indent=2,
                )
                + "\n",
            )

            result = self.run_script(
                STEER_SLICE,
                "RPVINF-134",
                "embedded_pi_session_adapter",
                "Please revise the plan response",
                "--repo-root",
                str(root),
            )

            payload = json.loads(result.stdout)
            self.assertEqual("manual_followup_required", payload["status"])
            self.assertIn("artifact-driven revision relaunch", payload["reason"])
            self.assertEqual("unavailable", payload["embedded_session"]["state"])
            self.assertEqual(["tmux attach -t pi-RPVINF-134-embedded"], payload["attach_instructions"])


class TestEpicSliceImplementPortabilityHelpers(unittest.TestCase):
    def test_opencode_config_path_prefers_env_override(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"PM_DAWN_OPENCODE_CONFIG_PATH": "/tmp/opencode.json"},
            clear=False,
        ):
            self.assertEqual(
                Path("/tmp/opencode.json"), implement_common.opencode_config_path()
            )

    def test_opencode_config_path_uses_xdg_config_home(self) -> None:
        env = {"XDG_CONFIG_HOME": "/tmp/xdg-config"}
        with mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(
                Path("/tmp/xdg-config") / "opencode" / "opencode.json",
                implement_common.opencode_config_path(),
            )

    def test_pi_models_config_path_prefers_env_override(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"PM_DAWN_PI_MODELS_CONFIG_PATH": "/tmp/pi-models.json"},
            clear=False,
        ):
            self.assertEqual(
                Path("/tmp/pi-models.json"), implement_common.pi_models_config_path()
            )

    def test_pi_embedded_capabilities_default_to_unavailable(self) -> None:
        with mock.patch.object(harness_pi_embedded.shutil, "which", return_value=None):
            payload = harness_pi_embedded.detect_capabilities(Path("/tmp/repo")).to_payload()
        self.assertFalse(payload["available"])
        self.assertFalse(payload["supports_events"])
        self.assertFalse(payload["supports_steer"])
        self.assertFalse(payload["supports_follow_up"])
        self.assertIn("fall back", payload["reason"])

    def test_pi_embedded_detects_rpc_protocol(self) -> None:
        help_text = "\n".join(
            [
                "  --mode <mode>                  Output mode: text (default), json, or rpc",
                "  --continue, -c                 Continue previous session",
                "  --resume, -r                   Select a session to resume",
                "  --session <path>               Use specific session file",
                "  --session-dir <dir>            Directory for session storage and lookup",
            ]
        )
        completed = subprocess.CompletedProcess(["pi", "--help"], 0, help_text, "")
        with mock.patch.object(harness_pi_embedded.shutil, "which", return_value="/usr/local/bin/pi"):
            with mock.patch.object(harness_pi_embedded.subprocess, "run", return_value=completed):
                payload = harness_pi_embedded.detect_capabilities(Path("/tmp/repo")).to_payload()

        self.assertTrue(payload["available"])
        self.assertEqual("pi-rpc-jsonl", payload["protocol"])
        self.assertEqual("/usr/local/bin/pi", payload["cli_path"])
        self.assertTrue(payload["cli_supports_rpc"])
        self.assertTrue(payload["supports_events"])
        self.assertTrue(payload["supports_steer"])
        self.assertTrue(payload["supports_follow_up"])
        self.assertTrue(payload["supports_persistent_session"])
        self.assertTrue(payload["supports_session_switch"])
        self.assertTrue(payload["supports_session_stats"])
        self.assertIn("available", payload["reason"])

    def test_pi_embedded_adapter_reports_fallback_snapshot(self) -> None:
        with mock.patch.object(harness_pi_embedded.shutil, "which", return_value=None):
            adapter = harness_pi_embedded.PiEmbeddedSessionAdapter(root=Path("/tmp/repo"))
            payload = adapter.create().to_payload()
        self.assertEqual("unavailable", payload["state"])
        self.assertIsNone(payload["session_id"])
        self.assertEqual([], payload["events"])
        self.assertIn("CLI/tmux", payload["fallback_reason"])

    def test_pi_embedded_submit_queues_prompt_and_records_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            session_dir = root / ".pm-dawn" / "pi-session"
            capabilities = harness_pi_embedded.PiEmbeddedCapabilities(
                available=True,
                reason="fixture",
                protocol="pi-rpc-jsonl",
                cli_path="/usr/local/bin/pi",
                cli_supports_rpc=True,
                supports_events=True,
                supports_steer=True,
                supports_follow_up=True,
                supports_persistent_session=True,
            )
            process = type("Process", (), {"pid": 12345})()

            with mock.patch.object(
                harness_pi_embedded,
                "detect_capabilities",
                return_value=capabilities,
            ), mock.patch.object(
                harness_pi_embedded,
                "_start_runner",
                return_value=process,
            ), mock.patch.object(
                harness_pi_embedded,
                "_process_alive",
                return_value=True,
            ):
                adapter = harness_pi_embedded.PiEmbeddedSessionAdapter(
                    root=root,
                    session_dir=session_dir,
                )
                payload = adapter.submit("Plan the packet").to_payload()

            self.assertEqual("processing", payload["state"])
            self.assertEqual("pi-rpc-jsonl", payload["protocol"])
            control_lines = (session_dir / "embedded-control.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(1, len(control_lines))
            command = json.loads(control_lines[0])
            self.assertEqual("prompt", command["type"])
            self.assertEqual("Plan the packet", command["message"])

    def test_pi_embedded_create_clears_stale_control_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            session_dir = root / ".pm-dawn" / "pi-session"
            session_dir.mkdir(parents=True)
            (session_dir / "embedded-control.jsonl").write_text(
                json.dumps({"type": "prompt", "message": "stale"}) + "\n",
                encoding="utf-8",
            )
            capabilities = harness_pi_embedded.PiEmbeddedCapabilities(
                available=True,
                reason="fixture",
                protocol="pi-rpc-jsonl",
                cli_path="/usr/local/bin/pi",
                cli_supports_rpc=True,
            )
            process = type("Process", (), {"pid": 12345})()

            with mock.patch.object(
                harness_pi_embedded,
                "detect_capabilities",
                return_value=capabilities,
            ), mock.patch.object(
                harness_pi_embedded,
                "_start_runner",
                return_value=process,
            ), mock.patch.object(
                harness_pi_embedded,
                "_process_alive",
                return_value=False,
            ):
                adapter = harness_pi_embedded.PiEmbeddedSessionAdapter(root=root, session_dir=session_dir)
                payload = adapter.create().to_payload()

            self.assertEqual("idle", payload["state"])
            self.assertFalse((session_dir / "embedded-control.jsonl").exists())

    def test_pi_embedded_observe_marks_dead_idle_runner_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            session_dir = root / ".pm-dawn" / "pi-session"
            capabilities = harness_pi_embedded.PiEmbeddedCapabilities(
                available=True,
                reason="fixture",
                protocol="pi-rpc-jsonl",
                cli_path="/usr/local/bin/pi",
                cli_supports_rpc=True,
            )
            harness_pi_embedded._write_snapshot(
                session_dir,
                harness_pi_embedded.PiEmbeddedSessionSnapshot(
                    session_id="pi-session-1",
                    state="idle",
                    capabilities=capabilities,
                    events=[],
                    session_dir=str(session_dir),
                    protocol="pi-rpc-jsonl",
                    process_id=12345,
                ),
            )

            with mock.patch.object(
                harness_pi_embedded,
                "detect_capabilities",
                return_value=capabilities,
            ), mock.patch.object(
                harness_pi_embedded,
                "_process_alive",
                return_value=False,
            ):
                adapter = harness_pi_embedded.PiEmbeddedSessionAdapter(root=root, session_dir=session_dir)
                payload = adapter.observe().to_payload()

            self.assertEqual("failed", payload["state"])
            self.assertIn("no longer running", payload["fallback_reason"])

    def test_pi_embedded_steer_starts_runner_before_queueing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            session_dir = root / ".pm-dawn" / "pi-session"
            capabilities = harness_pi_embedded.PiEmbeddedCapabilities(
                available=True,
                reason="fixture",
                protocol="pi-rpc-jsonl",
                cli_path="/usr/local/bin/pi",
                cli_supports_rpc=True,
                supports_steer=True,
            )
            process = type("Process", (), {"pid": 12345})()

            with mock.patch.object(
                harness_pi_embedded,
                "detect_capabilities",
                return_value=capabilities,
            ), mock.patch.object(
                harness_pi_embedded,
                "_start_runner",
                return_value=process,
            ), mock.patch.object(
                harness_pi_embedded,
                "_process_alive",
                return_value=False,
            ):
                adapter = harness_pi_embedded.PiEmbeddedSessionAdapter(root=root, session_dir=session_dir)
                payload = adapter.steer("continue").to_payload()

            self.assertEqual("processing", payload["state"])
            commands = [
                json.loads(line)["type"]
                for line in (session_dir / "embedded-control.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(["steer"], commands)

    def test_pi_embedded_steer_follow_up_and_close_queue_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            session_dir = root / ".pm-dawn" / "pi-session"
            capabilities = harness_pi_embedded.PiEmbeddedCapabilities(
                available=True,
                reason="fixture",
                protocol="pi-rpc-jsonl",
                cli_path="/usr/local/bin/pi",
                cli_supports_rpc=True,
                supports_events=True,
                supports_steer=True,
                supports_follow_up=True,
                supports_persistent_session=True,
            )
            snapshot = harness_pi_embedded.PiEmbeddedSessionSnapshot(
                session_id="pi-session-1",
                state="idle",
                capabilities=capabilities,
                events=[],
                session_dir=str(session_dir),
                protocol="pi-rpc-jsonl",
                process_id=12345,
            )
            harness_pi_embedded._write_snapshot(session_dir, snapshot)

            with mock.patch.object(
                harness_pi_embedded,
                "detect_capabilities",
                return_value=capabilities,
            ), mock.patch.object(
                harness_pi_embedded,
                "_process_alive",
                return_value=True,
            ), mock.patch.object(
                harness_pi_embedded.os,
                "kill",
            ):
                adapter = harness_pi_embedded.PiEmbeddedSessionAdapter(root=root, session_dir=session_dir)
                steer_payload = adapter.steer("Change direction").to_payload()
                follow_payload = adapter.follow_up("Then summarize").to_payload()
                close_payload = adapter.close().to_payload()

            self.assertEqual("processing", steer_payload["state"])
            self.assertEqual("awaiting_input", follow_payload["state"])
            self.assertEqual("closed", close_payload["state"])
            commands = [
                json.loads(line)["type"]
                for line in (session_dir / "embedded-control.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(["steer", "follow_up", "close"], commands)

    def test_pi_embedded_write_rpc_command_handles_broken_pipe(self) -> None:
        class BrokenStdin:
            def write(self, _value: str) -> None:
                raise BrokenPipeError("closed")

            def flush(self) -> None:
                raise AssertionError("flush should not run after failed write")

        process = type("Process", (), {"stdin": BrokenStdin()})()

        self.assertFalse(harness_pi_embedded._write_rpc_command(process, {"type": "get_state"}))

    def test_pi_embedded_runner_records_pi_start_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            session_dir = root / ".pm-dawn" / "pi-session"
            capabilities = harness_pi_embedded.PiEmbeddedCapabilities(
                available=True,
                reason="fixture",
                protocol="pi-rpc-jsonl",
                cli_path="/usr/local/bin/pi",
                cli_supports_rpc=True,
            )

            with mock.patch.object(
                harness_pi_embedded,
                "_runner_args",
                return_value=type(
                    "Args",
                    (),
                    {
                        "root": str(root),
                        "session_dir": str(session_dir),
                        "model": None,
                        "title": None,
                    },
                )(),
            ), mock.patch.object(
                harness_pi_embedded,
                "detect_capabilities",
                return_value=capabilities,
            ), mock.patch.object(
                harness_pi_embedded.subprocess,
                "Popen",
                side_effect=OSError("permission denied"),
            ):
                harness_pi_embedded._runner_main()

            payload = json.loads((session_dir / "embedded-state.json").read_text(encoding="utf-8"))
            self.assertEqual("failed", payload["state"])
            self.assertIn("permission denied", payload["fallback_reason"])
            self.assertEqual("pi_start_failed", payload["events"][0]["type"])

    def test_pi_embedded_snapshot_payload_copies_events(self) -> None:
        snapshot = harness_pi_embedded.PiEmbeddedSessionSnapshot(
            session_id="pi-session-1",
            state="processing",
            capabilities=harness_pi_embedded.PiEmbeddedCapabilities(
                available=True,
                reason="fixture",
                supports_events=True,
            ),
            events=[{"kind": "TOOL_CALL_END", "output": "full output"}],
        )

        payload = snapshot.to_payload()
        payload["events"][0]["output"] = "mutated"

        self.assertEqual("full output", snapshot.events[0]["output"])
        self.assertTrue(payload["capabilities"]["supports_events"])

    def test_tmux_has_session_returns_false_when_tmux_missing(self) -> None:
        with mock.patch.object(
            implement_common, "command_available", return_value=False
        ):
            self.assertFalse(implement_common.tmux_has_session("missing-session"))

    def test_ensure_pm_dawn_ignored_handles_non_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = implement_common.ensure_pm_dawn_ignored(root)
            self.assertEqual("not_git_repo", payload["status"])
            self.assertIsNone(payload["path"])

    def test_ensure_pm_dawn_ignored_can_create_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".git").mkdir()
            payload = implement_common.ensure_pm_dawn_ignored(
                root, create_gitignore=True
            )
            self.assertEqual("created_gitignore", payload["status"])
            self.assertEqual(
                ".pm-dawn/\n", (root / ".gitignore").read_text(encoding="utf-8")
            )

    def test_ensure_pm_dawn_ignored_does_not_create_gitignore_outside_git_repo(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = implement_common.ensure_pm_dawn_ignored(
                root, create_gitignore=True
            )
            self.assertEqual("not_git_repo", payload["status"])
            self.assertFalse((root / ".gitignore").exists())

    def test_resolved_shell_executable_uses_override(self) -> None:
        with mock.patch.dict("os.environ", {"PM_DAWN_SHELL": "/bin/sh"}, clear=False):
            self.assertEqual("/bin/sh", implement_common.resolved_shell_executable())

    def test_provider_timeout_seconds_falls_back_on_invalid_env(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"PM_DAWN_PROVIDER_TIMEOUT_SECONDS": "not-a-number"},
            clear=False,
        ):
            self.assertEqual(2.0, implement_common.provider_timeout_seconds())

    def test_pi_runner_script_uses_resolved_shell_for_keepalive(self) -> None:
        with mock.patch.object(
            implement_common, "resolved_shell_executable", return_value="/bin/sh"
        ):
            script = implement_common.pi_runner_script(
                root=Path("/tmp/repo"),
                session_dir=Path("/tmp/repo/.pm-dawn/pi"),
                command="pi --print 'prompt'",
            )
        self.assertIn("runner_exit=${?:-0};", script)
        self.assertIn("exec /bin/sh -i", script)

    def test_pi_runner_script_uses_zsh_pipeline_status_when_shell_is_zsh(self) -> None:
        with mock.patch.object(
            implement_common, "resolved_shell_executable", return_value="/bin/zsh"
        ):
            script = implement_common.pi_runner_script(
                root=Path("/tmp/repo"),
                session_dir=Path("/tmp/repo/.pm-dawn/pi"),
                command="pi --print 'prompt'",
            )
        self.assertIn("runner_exit=${pipestatus[1]:-0};", script)

    def test_pi_runner_script_uses_bash_pipeline_status_when_shell_is_bash(
        self,
    ) -> None:
        with mock.patch.object(
            implement_common, "resolved_shell_executable", return_value="/bin/bash"
        ):
            script = implement_common.pi_runner_script(
                root=Path("/tmp/repo"),
                session_dir=Path("/tmp/repo/.pm-dawn/pi"),
                command="pi --print 'prompt'",
            )
        self.assertIn("runner_exit=${PIPESTATUS[0]:-0};", script)

    def test_require_cli_failure_in_epic_slice_implement_common_raises_with_clear_message(
        self,
    ) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            implement_common.require_cli("nonexistent-cli-xyz")
        self.assertIn(
            "required CLI 'nonexistent-cli-xyz' not found", str(ctx.exception)
        )

    def test_run_cmd_failure_in_epic_slice_implement_common_raises_for_missing_command(
        self,
    ) -> None:
        with self.assertRaises(RuntimeError) as ctx:
            implement_common.run_cmd(["nonexistent-cmd-xyz"])
        self.assertIn(
            "required CLI 'nonexistent-cmd-xyz' not found", str(ctx.exception)
        )

    def test_resolved_shell_executable_falls_back_when_pm_dawn_shell_invalid(
        self,
    ) -> None:
        with mock.patch.dict(
            "os.environ", {"PM_DAWN_SHELL": "/bin/nonexistent"}, clear=False
        ):
            shell = implement_common.resolved_shell_executable()
            self.assertIn("/", shell)
            self.assertNotEqual("/bin/nonexistent", shell)

    def test_pi_runner_script_uses_generic_pipeline_status_for_non_bash_non_zsh_shell(
        self,
    ) -> None:
        with mock.patch.object(
            implement_common,
            "resolved_shell_executable",
            return_value="/usr/local/bin/dash",
        ):
            script = implement_common.pi_runner_script(
                root=Path("/tmp/repo"),
                session_dir=Path("/tmp/repo/.pm-dawn/pi"),
                command="pi --print 'prompt'",
            )
        self.assertIn("runner_exit=${?:-0};", script)
        self.assertIn("/usr/local/bin/dash", script)


if __name__ == "__main__":
    unittest.main()
