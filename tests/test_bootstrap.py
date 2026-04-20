"""Tests for workspace bootstrap and project profile generation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pm_dawn_core.bootstrap import (
    bootstrap_workspace,
    starter_project_profile,
)
from pm_dawn_core.profile import load_project_profile


class TestStarterProjectProfile(unittest.TestCase):
    def test_starter_project_profile_returns_toml(self) -> None:
        payload = starter_project_profile()
        self.assertIsInstance(payload, str)
        self.assertIn("[project]", payload)
        self.assertIn("[branches]", payload)
        self.assertIn("[validation]", payload)
        self.assertIn("PM Dawn Project", payload)
        self.assertIn("issue_key_pattern", payload)
        self.assertIn("make check", payload)


class TestBootstrapWorkspace(unittest.TestCase):
    def test_bootstrap_creates_required_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            created = bootstrap_workspace(root)
            pm_root = root / ".pm-dawn"
            self.assertTrue((pm_root / "epics").exists())
            self.assertTrue((pm_root / "archive").exists())
            self.assertTrue((pm_root / "tmp").exists())
            # Created items should be the three directories
            self.assertEqual(3, len(created))

    def test_bootstrap_does_not_overwrite_existing_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pm_root = root / ".pm-dawn"
            pm_root.mkdir()
            (pm_root / "epics").mkdir()
            (pm_root / "archive").mkdir()
            (pm_root / "tmp").mkdir()
            created = bootstrap_workspace(root)
            # Should not report any new creations since dirs exist
            self.assertEqual(0, len(created))

    def test_bootstrap_with_create_profile_creates_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            created = bootstrap_workspace(root, create_profile=True)
            profile_path = root / ".pm-dawn" / "project-profile.toml"
            self.assertTrue(profile_path.exists())
            # Check that profile path is in created (handles absolute path variations)
            profile_str = str(profile_path)
            created_paths = [str(Path(p)) for p in created]
            self.assertTrue(
                any(Path(p).resolve() == profile_path.resolve() for p in created_paths),
                f"Profile {profile_str} not found in created: {created_paths}",
            )

    def test_bootstrap_with_existing_profile_does_not_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pm_dir = root / ".pm-dawn"
            pm_dir.mkdir()
            profile_path = pm_dir / "project-profile.toml"
            original_content = "[project]\nname = \"Original\"\n"
            profile_path.write_text(original_content, encoding="utf-8")
            created = bootstrap_workspace(root, create_profile=True)
            # Profile should not be in created list
            self.assertNotIn(str(profile_path), created)
            # Content should be unchanged
            self.assertEqual(original_content, profile_path.read_text(encoding="utf-8"))


class TestBootstrapWithLoadProfile(unittest.TestCase):
    def test_bootstrap_creates_loadable_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            bootstrap_workspace(root, create_profile=True)
            profile = load_project_profile(root)
            self.assertEqual("PM Dawn Project", profile["project"]["name"])
            self.assertIn("feature", profile["branches"]["allowed_prefixes"])


if __name__ == "__main__":
    unittest.main()
