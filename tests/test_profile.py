"""Tests for profile merging and loading behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pm_dawn_core.profile import (
    BASE_PROJECT_PROFILE,
    clone_profile,
    classify_path_fallback,
    load_project_profile,
    make_default_profile,
    merge_profile,
    project_profile_path,
    repo_root,
)


class TestCloneProfile(unittest.TestCase):
    def test_clone_returns_independent_dict(self) -> None:
        original = {"key": {"nested": "value"}}
        cloned = clone_profile(original)
        self.assertEqual(original, cloned)
        cloned["key"]["nested"] = "modified"
        self.assertEqual("value", original["key"]["nested"])


class TestRepoRoot(unittest.TestCase):
    def test_repo_root_resolves_absolute_path(self) -> None:
        root = repo_root(".")
        self.assertTrue(root.is_absolute())


class TestProjectProfilePath(unittest.TestCase):
    def test_project_profile_path_in_pm_dawn_dir(self) -> None:
        root = Path(tempfile.gettempdir())
        path = project_profile_path(root)
        self.assertEqual(path.name, "project-profile.toml")
        self.assertIn(".pm-dawn", path.parts)


class TestMergeProfile(unittest.TestCase):
    def test_merge_deeply_overrides(self) -> None:
        base = {"a": 1, "b": {"c": 2, "d": 3}}
        override = {"b": {"c": 99}}
        merged = merge_profile(base, override)
        self.assertEqual({"a": 1, "b": {"c": 99, "d": 3}}, merged)

    def test_merge_shallow_override(self) -> None:
        base = {"key": "old"}
        override = {"key": "new"}
        merged = merge_profile(base, override)
        self.assertEqual({"key": "new"}, merged)

    def test_merge_adds_new_keys(self) -> None:
        base = {"existing": "value"}
        override = {"new": "value2"}
        merged = merge_profile(base, override)
        self.assertEqual({"existing": "value", "new": "value2"}, merged)

    def test_merge_preserves_base_when_no_override(self) -> None:
        base = {"key": "value"}
        merged = merge_profile(base, {})
        self.assertEqual(base, merged)


class TestMakeDefaultProfile(unittest.TestCase):
    def test_make_default_profile_produces_base(self) -> None:
        default = make_default_profile()
        self.assertEqual(BASE_PROJECT_PROFILE, default)

    def test_make_default_profile_applies_overrides(self) -> None:
        overrides = {"project": {"name": "Custom Project"}}
        profile = make_default_profile(overrides)
        self.assertEqual("Custom Project", profile["project"]["name"])
        # Ensure base values still present
        self.assertIn("issue_key_pattern", profile["project"])


class TestLoadProjectProfile(unittest.TestCase):
    def test_load_missing_profile_returns_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile = load_project_profile(root)
            self.assertEqual(BASE_PROJECT_PROFILE, profile)

    def test_load_existing_profile_merges(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pm_dir = root / ".pm-dawn"
            pm_dir.mkdir()
            profile_path = pm_dir / "project-profile.toml"
            profile_path.write_text(
                "[project]\nname = \"Custom Project\"\n", encoding="utf-8"
            )
            loaded = load_project_profile(root)
            self.assertEqual("Custom Project", loaded["project"]["name"])
            # Ensure base values still present
            self.assertIn("issue_key_pattern", loaded["project"])


class TestClassifyPathFallback(unittest.TestCase):
    def test_classify_tests_path(self) -> None:
        self.assertEqual("tests", classify_path_fallback("tests/unit/test_foo.py"))
        self.assertEqual("tests", classify_path_fallback("tests/integration/test_bar.py"))
        self.assertEqual("tests", classify_path_fallback("test_foo.py"))

    def test_classify_contract_path(self) -> None:
        self.assertEqual("contract", classify_path_fallback("pm_dawn_core/profile.py"))
        self.assertEqual("contract", classify_path_fallback("pm_dawn_core/layout.py"))
        self.assertEqual("contract", classify_path_fallback("pm_dawn_core/markdown.py"))
        self.assertEqual("contract", classify_path_fallback("pm_dawn_core/bootstrap.py"))
        self.assertEqual("contract", classify_path_fallback("pm_dawn_core/common.py"))

    def test_classify_cleanup_path(self) -> None:
        self.assertEqual("cleanup", classify_path_fallback("README.md"))
        self.assertEqual("cleanup", classify_path_fallback("docs/skill.md"))
        self.assertEqual("cleanup", classify_path_fallback("references/some_file.md"))

    def test_classify_wiring_path(self) -> None:
        self.assertEqual("wiring", classify_path_fallback("epic-slice-plan/scripts/generate.py"))
        # Note: pm_dawn_core/profile.py is classified as 'contract' since profile.py is in the contract list
        self.assertEqual("contract", classify_path_fallback("pm_dawn_core/profile.py"))

    def test_classify_default_to_cleanup(self) -> None:
        self.assertEqual("cleanup", classify_path_fallback("some/random/file.xyz"))


if __name__ == "__main__":
    unittest.main()
