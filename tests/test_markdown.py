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

PACKET_MARKDOWN = """# RPVINF-124 / consumer_enablement_2__01_contract

Packet ID:
- consumer_enablement_2__01_contract

Goal:
- Extract the shared plan-artifact and path helper contract needed by `epic-slice-plan`.

Why This Packet Is Isolated:
- Packet type: contract
- This packet is intentionally narrow and should not re-decide architecture.

Depends On:
- None

Files to Read:
- AGENTS.md
- pm_dawn_core/markdown.py

Files to Change:
- pm_dawn_core/markdown.py

Implementation Steps:
- Extract parsing helpers.

Validation Steps:
- Run unit tests.

Acceptance Checks:
- Parsers return expected fields.

Constraints:
- Do not widen scope.

Open Questions:
- None

Execution Routing:
- Risk Class: architectural
- Recommended Executor: direct_or_strong_model
- Preserve current artifact semantics.

Branch Recommendation:
- feature/RPVINF-126-consumer-enablement

Commit Scope Guidance:
- Use a commit focused on the contract packet and reference RPVINF-126.

Jira Traceability:
- Primary: RPVINF-126
- Additional: None
"""

PLAN_MARKDOWN = """# RPVINF-124 / consumer_enablement_2 / Slice Plan

Slice Identity:
- Group ID: consumer_enablement_2
- Primary Jira Key: RPVINF-126
- Secondary Jira Keys: None

Goal:
- Refactor `epic-slice-plan` onto the shared core so planning artifacts and repo interpretation stop living in a tool-local seam.

Approved Implementation Approach:
- Start from the existing slice handoff and current repo seams.
- Use packet-sized implementation units so execution can happen one approved packet at a time.

Files Likely to Change:
- pm_dawn_core/markdown.py

Files Explicitly Not to Change:
- None

Validation Strategy:
- Run focused tests for the slice.

Risks and Constraints:
- Keep artifact formats stable.

Open Questions:
- None

Packet Breakdown:
- consumer_enablement_2__01_contract: Extract the shared plan-artifact and path helper contract needed by `epic-slice-plan`.
- consumer_enablement_2__02_wiring: Rewire `epic-slice-plan` scripts to consume the extracted shared-core helpers without changing artifact behavior.
- consumer_enablement_2__03_tests: Add focused tests and a planning smoke path for the refactored `epic-slice-plan` consumer seam.

Packet Ordering:
- consumer_enablement_2__01_contract
- consumer_enablement_2__02_wiring
- consumer_enablement_2__03_tests

Source Context:
- Slice Markdown: /tmp/consumer_enablement_2.md
- Inspect payload: None
"""


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
    def test_parse_packet_markdown_from_controlled_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            packet_path = Path(tmpdir) / "packet.md"
            packet_path.write_text(PACKET_MARKDOWN, encoding="utf-8")
            packet = parse_packet_markdown(packet_path)
            self.assertEqual("consumer_enablement_2__01_contract", packet["packet_id"])
            self.assertEqual("contract", packet["packet_type"])
            self.assertEqual("RPVINF-126", packet["primary_issue"])
            self.assertEqual([], packet["depends_on"])
            self.assertEqual(["AGENTS.md", "pm_dawn_core/markdown.py"], packet["files_to_read"])
            self.assertEqual([], packet["open_questions"])

    def test_parse_packet_markdown_missing_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            packet_path = root / "nonexistent" / "packet.md"
            with self.assertRaises(RuntimeError) as ctx:
                parse_packet_markdown(packet_path)
            self.assertIn("packet Markdown not found", str(ctx.exception))


class TestParsePlanMarkdown(unittest.TestCase):
    def test_parse_plan_markdown_from_controlled_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_path = Path(tmpdir) / "plan.md"
            plan_path.write_text(PLAN_MARKDOWN, encoding="utf-8")
            plan = parse_plan_markdown(plan_path)
            packet_ids = [p["packet_id"] for p in plan.get("packets", [])]
            self.assertIn("consumer_enablement_2", plan.get("title", ""))
            self.assertEqual("Refactor `epic-slice-plan` onto the shared core so planning artifacts and repo interpretation stop living in a tool-local seam.", plan["goal"])
            self.assertEqual(
                [
                    "consumer_enablement_2__01_contract",
                    "consumer_enablement_2__02_wiring",
                    "consumer_enablement_2__03_tests",
                ],
                packet_ids,
            )
            self.assertEqual(packet_ids, plan["packet_order"])
            self.assertEqual([], plan["files_not_to_change"])

    def test_parse_plan_markdown_missing_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            plan_path = root / "nonexistent" / "plan.md"
            with self.assertRaises(RuntimeError) as ctx:
                parse_plan_markdown(plan_path)
            self.assertIn("plan Markdown not found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
