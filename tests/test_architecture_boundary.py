"""Tests for PM Dawn architecture boundary constraints."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = REPO_ROOT / "pm_dawn_core"
FORBIDDEN_CORE_IMPORT_PREFIXES = {
    "harness_opencode",
    "harness_pi",
    "harness_pi_embedded",
}
FORBIDDEN_CORE_IMPORT_NAMES = {
    "acli",
    "gh",
    "opencode",
    "pi",
    "tmux",
}


class TestArchitectureBoundary(unittest.TestCase):
    def test_core_does_not_import_harness_or_external_client_modules(self) -> None:
        violations: list[str] = []
        for path in sorted(CORE_ROOT.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                imported: list[str] = []
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported = [node.module]
                for module in imported:
                    root_name = module.split(".", 1)[0]
                    if module in FORBIDDEN_CORE_IMPORT_PREFIXES or root_name in FORBIDDEN_CORE_IMPORT_NAMES:
                        violations.append(f"{path.relative_to(REPO_ROOT)} imports {module}")

        self.assertEqual([], violations)

    def test_core_runtime_is_the_only_core_module_with_subprocess_control(self) -> None:
        violations: list[str] = []
        for path in sorted(CORE_ROOT.glob("*.py")):
            if path.name == "runtime.py":
                continue
            text = path.read_text(encoding="utf-8")
            if "subprocess" in text:
                violations.append(str(path.relative_to(REPO_ROOT)))

        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
