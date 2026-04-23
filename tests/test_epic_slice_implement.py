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
COMMON_SPEC = importlib.util.spec_from_file_location("epic_slice_implement_common", SCRIPT_ROOT / "common.py")
assert COMMON_SPEC is not None and COMMON_SPEC.loader is not None
implement_common = importlib.util.module_from_spec(COMMON_SPEC)
COMMON_SPEC.loader.exec_module(implement_common)

SLICE_STATUS = REPO_ROOT / "epic-slice-implement" / "scripts" / "slice_status.py"
CLEANUP_SLICE_ARTIFACTS = REPO_ROOT / "epic-slice-implement" / "scripts" / "cleanup_slice_artifacts.py"
CLEANUP_SLICE_BY_NAME = REPO_ROOT / "epic-slice-implement" / "scripts" / "cleanup_slice_by_name.py"
GENERATE_PACKET_IMPLEMENTATION_PLAN = (
    REPO_ROOT / "epic-slice-implement" / "scripts" / "generate_packet_implementation_plan.py"
)
COORDINATE_PLAN_REVIEW = REPO_ROOT / "epic-slice-implement" / "scripts" / "coordinate_plan_review.py"
MIGRATE_PM_DAWN_LAYOUT = REPO_ROOT / "epic-slice-implement" / "scripts" / "migrate_pm_dawn_layout.py"


def write_fixture(path: Path, content: str = "fixture\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_slice_fixture(root: Path, *, epic_key: str = "RPVINF-124", group_id: str = "consumer_enablement_3") -> None:
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
        "ops/runs": [f"{group_id}.json", f"{group_id}.plan.md", f"{group_id}.result.md"],
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
            self.assertTrue((root / ".pm-dawn" / "epics" / "RPVINF-124" / "slices" / "consumer_enablement_3.md").exists())

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
                str((root / ".pm-dawn" / "epics" / "RPVINF-124" / "packets" / "consumer_enablement_3__02_wiring.md").resolve()),
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
                        "attach_instructions": ["tmux attach -t pi-RPVINF-124-consumer_enablement_3__02_wiring"],
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

    def test_generate_packet_implementation_plan_help_uses_shared_description(self) -> None:
        result = self.run_script(GENERATE_PACKET_IMPLEMENTATION_PLAN, "--help")
        self.assertIn(
            "Generate a worker-authored packet plan proposal artifact.",
            result.stdout,
        )

    def test_coordinate_plan_review_accept_copies_proposal_to_implementation_brief(self) -> None:
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
            self.assertEqual("# accepted plan\n", implementation_brief.read_text(encoding="utf-8"))
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
            self.assertEqual(str(implementation_brief.resolve()), state["implementation_plan_artifact"])

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

    def test_migrate_pm_dawn_layout_dry_run_reports_canonical_follow_up_commands(self) -> None:
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
            self.assertEqual("would_create_gitignore", payload["ignore_state"]["status"])
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
            self.assertEqual(".pm-dawn/\n", (root / ".gitignore").read_text(encoding="utf-8"))

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


class TestEpicSliceImplementPortabilityHelpers(unittest.TestCase):
    def test_opencode_config_path_prefers_env_override(self) -> None:
        with mock.patch.dict("os.environ", {"PM_DAWN_OPENCODE_CONFIG_PATH": "/tmp/opencode.json"}, clear=False):
            self.assertEqual(Path("/tmp/opencode.json"), implement_common.opencode_config_path())

    def test_opencode_config_path_uses_xdg_config_home(self) -> None:
        env = {"XDG_CONFIG_HOME": "/tmp/xdg-config"}
        with mock.patch.dict("os.environ", env, clear=True):
            self.assertEqual(
                Path("/tmp/xdg-config") / "opencode" / "opencode.json",
                implement_common.opencode_config_path(),
            )

    def test_pi_models_config_path_prefers_env_override(self) -> None:
        with mock.patch.dict("os.environ", {"PM_DAWN_PI_MODELS_CONFIG_PATH": "/tmp/pi-models.json"}, clear=False):
            self.assertEqual(Path("/tmp/pi-models.json"), implement_common.pi_models_config_path())

    def test_tmux_has_session_returns_false_when_tmux_missing(self) -> None:
        with mock.patch.object(implement_common, "command_available", return_value=False):
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
            payload = implement_common.ensure_pm_dawn_ignored(root, create_gitignore=True)
            self.assertEqual("created_gitignore", payload["status"])
            self.assertEqual(".pm-dawn/\n", (root / ".gitignore").read_text(encoding="utf-8"))

    def test_ensure_pm_dawn_ignored_does_not_create_gitignore_outside_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = implement_common.ensure_pm_dawn_ignored(root, create_gitignore=True)
            self.assertEqual("not_git_repo", payload["status"])
            self.assertFalse((root / ".gitignore").exists())

    def test_resolved_shell_executable_uses_override(self) -> None:
        with mock.patch.dict("os.environ", {"PM_DAWN_SHELL": "/bin/sh"}, clear=False):
            self.assertEqual("/bin/sh", implement_common.resolved_shell_executable())

    def test_provider_timeout_seconds_falls_back_on_invalid_env(self) -> None:
        with mock.patch.dict("os.environ", {"PM_DAWN_PROVIDER_TIMEOUT_SECONDS": "not-a-number"}, clear=False):
            self.assertEqual(2.0, implement_common.provider_timeout_seconds())

    def test_pi_runner_script_uses_resolved_shell_for_keepalive(self) -> None:
        with mock.patch.object(implement_common, "resolved_shell_executable", return_value="/bin/sh"):
            script = implement_common.pi_runner_script(
                root=Path("/tmp/repo"),
                session_dir=Path("/tmp/repo/.pm-dawn/pi"),
                command="pi --print 'prompt'",
            )
        self.assertIn("runner_exit=${?:-0};", script)
        self.assertIn("exec /bin/sh -i", script)

    def test_pi_runner_script_uses_zsh_pipeline_status_when_shell_is_zsh(self) -> None:
        with mock.patch.object(implement_common, "resolved_shell_executable", return_value="/bin/zsh"):
            script = implement_common.pi_runner_script(
                root=Path("/tmp/repo"),
                session_dir=Path("/tmp/repo/.pm-dawn/pi"),
                command="pi --print 'prompt'",
            )
        self.assertIn("runner_exit=${pipestatus[1]:-0};", script)

    def test_pi_runner_script_uses_bash_pipeline_status_when_shell_is_bash(self) -> None:
        with mock.patch.object(implement_common, "resolved_shell_executable", return_value="/bin/bash"):
            script = implement_common.pi_runner_script(
                root=Path("/tmp/repo"),
                session_dir=Path("/tmp/repo/.pm-dawn/pi"),
                command="pi --print 'prompt'",
            )
        self.assertIn("runner_exit=${PIPESTATUS[0]:-0};", script)


if __name__ == "__main__":
    unittest.main()
