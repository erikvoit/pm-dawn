"""CLI smoke tests for epic-slice-implement lifecycle entrypoints."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SLICE_STATUS = REPO_ROOT / "epic-slice-implement" / "scripts" / "slice_status.py"
CLEANUP_SLICE_ARTIFACTS = REPO_ROOT / "epic-slice-implement" / "scripts" / "cleanup_slice_artifacts.py"
CLEANUP_SLICE_BY_NAME = REPO_ROOT / "epic-slice-implement" / "scripts" / "cleanup_slice_by_name.py"


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
        "ops/artifacts": [f"{group_id}__01_contract.implementation-plan.md"],
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
            self.assertEqual(15, payload["target_count"])
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
            self.assertEqual(15, payload["target_count"])
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


if __name__ == "__main__":
    unittest.main()
