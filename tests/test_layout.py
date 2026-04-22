"""Tests for PM Dawn workspace layout helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pm_dawn_core.layout import (
    SlicePaths,
    epic_root,
    epics_root,
    ops_root,
    packet_markdown_path,
    pm_dawn_root,
    project_profile_path,
    run_artifact_path,
    run_metadata_path,
    slice_archive_root,
    slice_artifact_targets,
    slice_paths,
    slice_plan_path,
)


class TestPmDawnRoot(unittest.TestCase):
    def test_pm_dawn_root_points_to_dot_pm_dawn(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            pm_root = pm_dawn_root(root)
            expected = (root / ".pm-dawn").resolve()
            # Use resolve() to handle tempfile path variations
            self.assertEqual(expected, pm_root.resolve())
            # Verify the path is relative to root (using string comparison)
            self.assertTrue(str(pm_root).startswith(str(root)))


class TestEpicsRoot(unittest.TestCase):
    def test_epics_root_inside_pm_dawn(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            epics = epics_root(root)
            self.assertEqual((root / ".pm-dawn" / "epics").resolve(), epics.resolve())


class TestEpicRoot(unittest.TestCase):
    def test_epic_root_points_to_named_epic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            epic = epic_root(root, "RPVINF-123")
            expected = root / ".pm-dawn" / "epics" / "RPVINF-123"
            self.assertEqual(expected.resolve(), epic.resolve())


class TestOpsRoot(unittest.TestCase):
    def test_ops_root_points_to_ops_inside_epic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            ops = ops_root(root, "RPVINF-123")
            expected = root / ".pm-dawn" / "epics" / "RPVINF-123" / "ops"
            self.assertEqual(expected.resolve(), ops.resolve())


class TestProjectProfilePath(unittest.TestCase):
    def test_project_profile_path_points_to_profile_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile = project_profile_path(root)
            expected = root / ".pm-dawn" / "project-profile.toml"
            self.assertEqual(expected.resolve(), profile.resolve())


class TestSlicePaths(unittest.TestCase):
    def test_slice_paths_dataclass_has_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            epic_key = "RPVINF-123"
            group_id = "consumer_enablement_2"
            paths = slice_paths(root, epic_key, group_id)
            self.assertIsInstance(paths, SlicePaths)
            self.assertIsNotNone(paths.root)
            self.assertIsNotNone(paths.epic_root)
            self.assertIsNotNone(paths.index_md)
            self.assertIsNotNone(paths.slice_md)
            self.assertIsNotNone(paths.ops_dir)
            self.assertIsNotNone(paths.plans_dir)
            self.assertIsNotNone(paths.packets_dir)
            self.assertIsNotNone(paths.handoffs_dir)
            self.assertIsNotNone(paths.artifacts_dir)

    def test_slice_paths_structure_for_epic(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            epic_key = "RPVINF-123"
            group_id = "consumer_enablement_2"
            paths = slice_paths(root, epic_key, group_id)
            expected_epic_root = root / ".pm-dawn" / "epics" / epic_key
            expected_slice_md = expected_epic_root / "slices" / f"{group_id}.md"
            expected_ops_dir = expected_epic_root / "ops"
            expected_plans_dir = expected_epic_root / "plans"
            expected_packets_dir = expected_epic_root / "packets"
            expected_handoffs_dir = expected_ops_dir / "handoffs"
            expected_artifacts_dir = expected_ops_dir / "artifacts"
            self.assertEqual(expected_epic_root.resolve(), paths.epic_root.resolve())
            self.assertEqual(expected_slice_md.resolve(), paths.slice_md.resolve())
            self.assertEqual(expected_ops_dir.resolve(), paths.ops_dir.resolve())
            self.assertEqual(expected_plans_dir.resolve(), paths.plans_dir.resolve())
            self.assertEqual(expected_packets_dir.resolve(), paths.packets_dir.resolve())
            self.assertEqual(expected_handoffs_dir.resolve(), paths.handoffs_dir.resolve())
            self.assertEqual(expected_artifacts_dir.resolve(), paths.artifacts_dir.resolve())


class TestSlicePathsFunction(unittest.TestCase):
    def test_slice_paths_returns_correct_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            epic_key = "RPVINF-124"
            group_id = "consumer_enablement_2"
            paths = slice_paths(root, epic_key, group_id)
            self.assertTrue(paths.root.is_absolute())
            self.assertIn(".pm-dawn", str(paths.epic_root))
            self.assertIn("epics", str(paths.epic_root))
            self.assertIn(epic_key, str(paths.epic_root))


class TestLifecycleLayoutHelpers(unittest.TestCase):
    def test_slice_archive_root_points_to_slice_archive_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            archive = slice_archive_root(root, "RPVINF-124", "consumer_enablement_3")
            expected = root / ".pm-dawn" / "archive" / "RPVINF-124" / "consumer_enablement_3"
            self.assertEqual(expected.resolve(), archive.resolve())

    def test_run_paths_point_to_slice_run_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            metadata = run_metadata_path(root, "RPVINF-124", "consumer_enablement_3")
            plan_path = slice_plan_path(root, "RPVINF-124", "consumer_enablement_3")
            plan_artifact = run_artifact_path(root, "RPVINF-124", "consumer_enablement_3", "plan")
            result_artifact = run_artifact_path(root, "RPVINF-124", "consumer_enablement_3", "result")
            self.assertEqual(
                (root / ".pm-dawn" / "epics" / "RPVINF-124" / "plans" / "consumer_enablement_3.plan.md").resolve(),
                plan_path.resolve(),
            )
            self.assertEqual(
                (root / ".pm-dawn" / "epics" / "RPVINF-124" / "ops" / "runs" / "consumer_enablement_3.json").resolve(),
                metadata.resolve(),
            )
            self.assertEqual(
                (root / ".pm-dawn" / "epics" / "RPVINF-124" / "ops" / "runs" / "consumer_enablement_3.plan.md").resolve(),
                plan_artifact.resolve(),
            )
            self.assertEqual(
                (root / ".pm-dawn" / "epics" / "RPVINF-124" / "ops" / "runs" / "consumer_enablement_3.result.md").resolve(),
                result_artifact.resolve(),
            )

    def test_slice_artifact_targets_collect_exact_and_globbed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            epic_root_path = root / ".pm-dawn" / "epics" / "RPVINF-124"
            for relative in (
                "slices/consumer_enablement_3.md",
                "plans/consumer_enablement_3.plan.md",
                "ops/runs/consumer_enablement_3.json",
                "ops/runs/consumer_enablement_3.plan.md",
                "ops/runs/consumer_enablement_3.result.md",
                "ops/pr/consumer_enablement_3.title.txt",
                "ops/pr/consumer_enablement_3.body.md",
                "ops/pr/consumer_enablement_3.verify.json",
                "packets/consumer_enablement_3__01_contract.md",
                "ops/handoffs/consumer_enablement_3__01_contract.json",
                "ops/pr/consumer_enablement_3__01_contract.title.txt",
                "ops/pr/consumer_enablement_3__01_contract.body.md",
                "ops/pr/consumer_enablement_3__01_contract.verify.json",
                "ops/artifacts/consumer_enablement_3__01_contract.implementation-plan.md",
            ):
                path = epic_root_path / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")

            targets = slice_artifact_targets(root, "RPVINF-124", "consumer_enablement_3")

            self.assertEqual(14, len(targets))
            self.assertEqual(sorted(targets), targets)
            self.assertEqual(len(targets), len(set(targets)))
            self.assertIn((epic_root_path / "slices" / "consumer_enablement_3.md").resolve(), targets)
            self.assertIn(
                (epic_root_path / "ops" / "artifacts" / "consumer_enablement_3__01_contract.implementation-plan.md").resolve(),
                targets,
            )
            self.assertNotIn(
                (epic_root_path / "ops" / "handoffs" / "other_slice__01_contract.json").resolve(),
                targets,
            )
class TestPacketMarkdownPath(unittest.TestCase):
    def test_packet_markdown_path_returns_correct_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            epic_key = "RPVINF-124"
            packet_id_value = "consumer_enablement_2__01_contract"
            path = packet_markdown_path(root, epic_key, packet_id_value)
            expected = root / ".pm-dawn" / "epics" / epic_key / "packets" / f"{packet_id_value}.md"
            self.assertEqual(expected.resolve(), path.resolve())

    def test_packet_markdown_path_with_different_packet_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            epic_key = "RPVINF-124"
            group_id = "consumer_enablement_2"
            packet_id_value = f"{group_id}__03_tests"
            path = packet_markdown_path(root, epic_key, packet_id_value)
            expected = root / ".pm-dawn" / "epics" / epic_key / "packets" / f"{packet_id_value}.md"
            self.assertEqual(expected.resolve(), path.resolve())


if __name__ == "__main__":
    unittest.main()
