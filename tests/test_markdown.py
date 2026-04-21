"""Tests for shared markdown parsing helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pm_dawn_core.markdown import (
    bullet_values,
    parse_markdown_sections,
    parse_packet_markdown,
    parse_plan_markdown,
    single_bullet,
)


class TestParseMarkdownSections(unittest.TestCase):
    def test_parse_extract_title_and_sections(self) -> None:
        # Section headers require a colon at the end per SECTION_RE regex
        # Title is parsed from # prefix, sections from "Name:" format
        # Blank lines are included in section content, trailing newline produces empty string
        markdown = "# My Title\n\nOverview section content.\n\nImplementation Steps:\n\n- Step one\n- Step two\n\nValidation:\n\n- Check A\n- Check B\n"
        title, sections = parse_markdown_sections(markdown)
        self.assertEqual("My Title", title)
        self.assertIn("Implementation Steps", sections)
        self.assertIn("Validation", sections)
        self.assertEqual(["", "- Step one", "- Step two", ""], sections["Implementation Steps"])
        self.assertEqual(["", "- Check A", "- Check B"], sections["Validation"])

    def test_parse_empty_markdown(self) -> None:
        title, sections = parse_markdown_sections("")
        self.assertIsNone(title)
        self.assertEqual({}, sections)

    def test_parse_only_title(self) -> None:
        title, sections = parse_markdown_sections("# Title")
        self.assertEqual("Title", title)
        self.assertEqual({}, sections)

    def test_parse_no_title(self) -> None:
        # Section headers require a colon at the end
        # Lines must be indented at the same level as bullets to be captured
        # Blank lines are included in section content
        markdown = "Section One:\n\n- Content here.\n"
        title, sections = parse_markdown_sections(markdown)
        self.assertIsNone(title)
        self.assertIn("Section One", sections)
        # Verify content is captured correctly
        self.assertEqual(["", "- Content here."], sections["Section One"])

    def test_parse_preserves_whitespace_in_section_lines(self) -> None:
        # Section headers require a colon at the end
        # Lines must be indented at the same level as bullets to be captured
        # Blank lines are included in section content
        markdown = "Details:\n\n- Indented content\n- Less indented\n- No indent\n"
        title, sections = parse_markdown_sections(markdown)
        # Note: blank lines are captured as empty strings, trailing newline doesn't add empty line
        self.assertEqual(["", "- Indented content", "- Less indented", "- No indent"], sections["Details"])


class TestBulletValues(unittest.TestCase):
    def test_extract_bullets(self) -> None:
        lines = ["- First", "- Second", "- Third"]
        values = bullet_values(lines)
        self.assertEqual(["First", "Second", "Third"], values)

    def test_filter_non_bullets(self) -> None:
        lines = ["- Bullet", "Not bullet", "- Another", "  - With spaces"]
        values = bullet_values(lines)
        self.assertEqual(["Bullet", "Another", "With spaces"], values)

    def test_empty_lines_return_empty(self) -> None:
        values = bullet_values([])
        self.assertEqual([], values)

    def test_mixed_content_extraction(self) -> None:
        lines = [
            "Some header",
            "- item 1",
            "Some text",
            "- item 2",
            "- item 3",
        ]
        values = bullet_values(lines)
        self.assertEqual(["item 1", "item 2", "item 3"], values)


class TestSingleBullet(unittest.TestCase):
    def test_single_bullet_returns_first(self) -> None:
        lines = ["- First", "- Second"]
        result = single_bullet(lines)
        self.assertEqual("First", result)

    def test_single_bullet_default_for_empty(self) -> None:
        result = single_bullet([])
        self.assertEqual("", result)

    def test_single_bullet_custom_default(self) -> None:
        result = single_bullet([], default="fallback")
        self.assertEqual("fallback", result)

    def test_single_bullet_with_one_item(self) -> None:
        lines = ["- Only"]
        result = single_bullet(lines)
        self.assertEqual("Only", result)


class TestParsePacketMarkdown(unittest.TestCase):
    def test_parse_packet_markdown_with_actual_packet(self) -> None:
        # Use an actual packet artifact from the repo
        test_repo_root = Path(__file__).resolve().parent.parent
        packet_path = test_repo_root / ".pm-dawn" / "epics" / "RPVINF-124" / "packets" / "consumer_enablement_2__01_contract.md"
        if packet_path.exists():
            packet = parse_packet_markdown(packet_path)
            # Verify expected fields are present
            self.assertIn("title", packet)
            self.assertIn("packet_id", packet)
            self.assertIn("goal", packet)
            self.assertIn("packet_type", packet)
            self.assertIn("primary_issue", packet)
            self.assertIn("secondary_issues", packet)
            self.assertIn("branch_name", packet)
            self.assertIn("commit_scope_guidance", packet)
            self.assertIn("risk_class", packet)
            self.assertIn("recommended_executor", packet)
            # Verify specific known values for consumer_enablement_2__01_contract
            self.assertEqual("consumer_enablement_2__01_contract", packet["packet_id"])
            self.assertEqual("contract", packet["packet_type"])
            self.assertEqual("RPVINF-126", packet["primary_issue"])

    def test_parse_packet_markdown_missing_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            packet_path = root / "nonexistent" / "packet.md"
            with self.assertRaises(RuntimeError) as ctx:
                parse_packet_markdown(packet_path)
            self.assertIn("packet Markdown not found", str(ctx.exception))


class TestParsePlanMarkdown(unittest.TestCase):
    def test_parse_plan_markdown_with_actual_plan(self) -> None:
        # Use an actual plan artifact from the repo
        test_repo_root = Path(__file__).resolve().parent.parent
        plan_path = test_repo_root / ".pm-dawn" / "epics" / "RPVINF-124" / "plans" / "consumer_enablement_2.plan.md"
        if plan_path.exists():
            plan = parse_plan_markdown(plan_path)
            # Verify expected fields are present
            self.assertIn("title", plan)
            self.assertIn("slice_identity", plan)
            self.assertIn("goal", plan)
            self.assertIn("approved_approach", plan)
            self.assertIn("packets", plan)
            self.assertIn("packet_order", plan)
            # Verify specific known values for consumer_enablement_2 plan
            self.assertIn("consumer_enablement_2", plan.get("title", ""))
            # Check that packets list has expected entries
            packet_ids = [p["packet_id"] for p in plan.get("packets", [])]
            self.assertIn("consumer_enablement_2__01_contract", packet_ids)
            self.assertIn("consumer_enablement_2__02_wiring", packet_ids)
            self.assertIn("consumer_enablement_2__03_tests", packet_ids)

    def test_parse_plan_markdown_missing_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan_path = root / "nonexistent" / "plan.md"
            with self.assertRaises(RuntimeError) as ctx:
                parse_plan_markdown(plan_path)
            self.assertIn("plan Markdown not found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
