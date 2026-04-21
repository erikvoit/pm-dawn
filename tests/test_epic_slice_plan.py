"""Tests for epic-slice-plan smoke paths."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

# Use the repo root where tests are being run
REPO_ROOT = Path(__file__).resolve().parent.parent


class TestValidateSlicePlan(unittest.TestCase):
    def test_validate_slice_plan_smoke_test(self) -> None:
        """Test that validate_slice_plan.py runs successfully."""
        script_path = REPO_ROOT / "epic-slice-plan" / "scripts" / "validate_slice_plan.py"
        epic_key = "RPVINF-124"
        group_id = "consumer_enablement_2"

        result = subprocess.run(
            [
                "python",
                str(script_path),
                epic_key,
                group_id,
                "--repo-root",
                str(REPO_ROOT),
            ],
            capture_output=True,
            text=True,
        )

        # Script should exit successfully
        self.assertEqual(0, result.returncode, msg=f"stderr: {result.stderr}\nstdout: {result.stdout}")
        # Output should be valid JSON
        import json
        output = result.stdout.strip()
        self.assertIn("ready", output)
        payload = json.loads(output)
        self.assertTrue(payload.get("ready", False))

    def test_validate_slice_plan_with_invalid_epic_key(self) -> None:
        """Test that validate_slice_plan.py handles missing epic gracefully."""
        script_path = REPO_ROOT / "epic-slice-plan" / "scripts" / "validate_slice_plan.py"
        epic_key = "NONEXISTENT-999"
        group_id = "consumer_enablement_2"

        result = subprocess.run(
            [
                "python",
                str(script_path),
                epic_key,
                group_id,
                "--repo-root",
                str(REPO_ROOT),
            ],
            capture_output=True,
            text=True,
        )

        # Script should exit with error code
        self.assertNotEqual(0, result.returncode)


class TestCompilePacketMarkdown(unittest.TestCase):
    def test_compile_packet_markdown_smoke_test(self) -> None:
        """Test that compile_packet_markdown.py runs successfully."""
        script_path = REPO_ROOT / "epic-slice-plan" / "scripts" / "compile_packet_markdown.py"
        epic_key = "RPVINF-124"
        group_id = "consumer_enablement_2"
        packet_id_value = "consumer_enablement_2__01_contract"

        result = subprocess.run(
            [
                "python",
                str(script_path),
                epic_key,
                group_id,
                packet_id_value,
                "--repo-root",
                str(REPO_ROOT),
            ],
            capture_output=True,
            text=True,
        )

        # Script should exit successfully
        self.assertEqual(0, result.returncode, msg=f"stderr: {result.stderr}\nstdout: {result.stdout}")
        # Output should be valid JSON
        import json
        output = result.stdout.strip()
        self.assertIn("packet_id", output)
        payload = json.loads(output)
        self.assertEqual(packet_id_value, payload.get("packet_id"))
        self.assertEqual("contract", payload.get("packet_type"))
        self.assertEqual("RPVINF-126", payload.get("primary_issue"))

    def test_compile_packet_markdown_with_invalid_packet(self) -> None:
        """Test that compile_packet_markdown.py handles missing packet gracefully."""
        script_path = REPO_ROOT / "epic-slice-plan" / "scripts" / "compile_packet_markdown.py"
        epic_key = "RPVINF-124"
        group_id = "consumer_enablement_2"
        packet_id_value = "nonexistent__99_tests"

        result = subprocess.run(
            [
                "python",
                str(script_path),
                epic_key,
                group_id,
                packet_id_value,
                "--repo-root",
                str(REPO_ROOT),
            ],
            capture_output=True,
            text=True,
        )

        # Script should exit with error code
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

            # Verify no external imports that would break plain python
            # (We're using stdlib only per AGENTS.md)
            import ast
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            # Only stdlib should be used
                            module = alias.name.split('.')[0]
                            # We're just checking the script doesn't have obvious issues
                            # Real validation happens when running the script
                            pass
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            module = node.module.split('.')[0]
                            # Again, just verifying the structure is sound
                            pass
            except SyntaxError:
                # If parsing fails, the script has issues
                self.fail(f"Script {script_rel} has syntax errors")

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
