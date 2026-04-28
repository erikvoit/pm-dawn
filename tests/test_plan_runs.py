"""Tests for shared planning and run-state services."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pm_dawn_core.artifacts import write_json, write_text
from pm_dawn_core.plan import load_slice_handoff_payload, validate_slice_plan_artifacts
from pm_dawn_core.runs import (
    apply_implementation_monitor_status,
    merge_run_metadata,
    run_plan_monitor_state,
    run_plan_review_state,
)


SLICE_MARKDOWN = """# RPVINF-124 / consumer_enablement_11

Group ID: consumer_enablement_11
Primary Jira Key: RPVINF-137
Secondary Jira Keys: None

Goal:
- Thin skill scripts around core services.

Branch Recommendation:
- feature/RPVINF-137-thin-skill-scripts

PR Traceability:
- Primary: RPVINF-137
- Additional: None

Entry Criteria:
- Stable upstream harness work.

Exit Criteria:
- Shared services are wired.

Repo Surfaces:
- pm_dawn_core/

Implementation Steps:
- Extract helpers.

Validation Steps:
- Run tests.

Risks and Constraints:
- Keep harness orchestration out of core.

Open Questions:
- None

Source Review Context:
- Derived from `RPVINF-137`.
"""

PLAN_MARKDOWN = """# RPVINF-124 / consumer_enablement_11 / Slice Plan

Slice Identity:
- Group ID: consumer_enablement_11
- Primary Jira Key: RPVINF-137
- Secondary Jira Keys: None

Goal:
- Thin skill scripts around core services.

Approved Implementation Approach:
- Extract shared helpers.

Files Likely to Change:
- pm_dawn_core/plan.py

Files Explicitly Not to Change:
- None

Validation Strategy:
- Run tests.

Risks and Constraints:
- Keep harness orchestration out of core.

Open Questions:
- None

Packet Breakdown:
- consumer_enablement_11__03_planning_run_services: Rewire planning and run services.

Packet Ordering:
- consumer_enablement_11__03_planning_run_services

Source Context:
- Slice Markdown: fixture
- Inspect payload: None
"""

PACKET_MARKDOWN = """# RPVINF-124 / consumer_enablement_11__03_planning_run_services

Packet ID:
- consumer_enablement_11__03_planning_run_services

Goal:
- Rewire planning and run services.

Why This Packet Is Isolated:
- Packet type: wiring

Depends On:
- None

Files to Read:
- pm_dawn_core/plan.py

Files to Change:
- pm_dawn_core/plan.py

Implementation Steps:
- Add shared services.

Validation Steps:
- Run tests.

Acceptance Checks:
- All packet validation steps pass.

Constraints:
- Keep harness orchestration out of core.

Open Questions:
- None

Execution Routing:
- Risk Class: broad
- Recommended Executor: direct_or_strong_model
- Review carefully.

Branch Recommendation:
- feature/RPVINF-137-thin-skill-scripts

Commit Scope Guidance:
- Reference RPVINF-137.

Jira Traceability:
- Primary: RPVINF-137
- Additional: None
"""


def write_fixture(root: Path) -> None:
    epic_root = root / ".pm-dawn" / "epics" / "RPVINF-124"
    write_text(epic_root / "slices" / "consumer_enablement_11.md", SLICE_MARKDOWN)
    write_text(epic_root / "plans" / "consumer_enablement_11.plan.md", PLAN_MARKDOWN)
    write_text(epic_root / "packets" / "consumer_enablement_11__03_planning_run_services.md", PACKET_MARKDOWN)


class TestPlanServices(unittest.TestCase):
    def test_load_slice_handoff_payload_preserves_cli_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_fixture(root)

            payload = load_slice_handoff_payload(root, "RPVINF-124", "consumer_enablement_11")

            self.assertEqual(str(root.resolve()), payload["repo_root"])
            self.assertTrue(payload["handoff_markdown_present"])
            self.assertEqual("RPVINF-137", payload["handoff"]["primary_issue"])
            self.assertTrue(payload["slice_markdown_path"].endswith("consumer_enablement_11.md"))

    def test_validate_slice_plan_artifacts_reports_ready_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            write_fixture(root)

            payload = validate_slice_plan_artifacts(root, "RPVINF-124", "consumer_enablement_11")

            self.assertTrue(payload["ready"])
            self.assertEqual(1, payload["packet_count"])
            self.assertEqual([], payload["errors"])


class TestRunServices(unittest.TestCase):
    def test_merge_run_metadata_preserves_existing_artifacts_and_decodes_monitor_payloads(self) -> None:
        payload = merge_run_metadata(
            existing={"time": {"created": "old"}, "artifacts": {"plan_md": "/tmp/plan.md"}},
            epic_key="RPVINF-124",
            group_id="consumer_enablement_11",
            handoff_path="handoff.json",
            packet_id="consumer_enablement_11__03_planning_run_services",
            branch_name="feature/RPVINF-137-thin-skill-scripts",
            runtime_mode="server",
            harness="opencode",
            model="model",
            status="running",
            phase="implementing",
            completion_state="in_progress",
            server_url="http://localhost",
            session_id="ses_1",
            tmux_session=None,
            server_tmux_session=None,
            session_dir=None,
            last_action="launch",
            attach_instructions=["attach"],
            plan_artifact=None,
            implementation_plan_artifact=None,
            result_artifact="result.md",
            worker_status="pending_review",
            worker_note="ready",
            model_check={"matches_active_model": True},
            monitoring={"initial_session_check_seconds": 5},
            embedded_session=None,
            created_at="old",
            updated_at="new",
        )

        self.assertEqual("old", payload["time"]["created"])
        self.assertEqual("new", payload["time"]["updated"])
        self.assertEqual("pending_review", payload["worker"]["status"])
        self.assertEqual("ses_1", payload["opencode"]["session_id"])
        self.assertTrue(payload["artifacts"]["result_md"].endswith("result.md"))

    def test_run_monitor_helpers_share_plan_and_implementation_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            state_path = (
                root
                / ".pm-dawn"
                / "epics"
                / "RPVINF-124"
                / "ops"
                / "artifacts"
                / "consumer_enablement_11__03_planning_run_services.plan-review.json"
            )
            write_json(state_path, {"status": "changes_requested"})
            run_meta = {
                "packet_id": "consumer_enablement_11__03_planning_run_services",
                "phase": "implementing",
                "worker": {"status": "pending_review"},
                "last_action": "worker_marked_pending_review",
            }

            review = run_plan_review_state(root, "RPVINF-124", run_meta["packet_id"])
            monitor = run_plan_monitor_state(root, "RPVINF-124", run_meta["packet_id"], plan_review=review)
            status, completion_state, implementation_monitor = apply_implementation_monitor_status(
                root,
                "RPVINF-124",
                "consumer_enablement_11",
                run_meta,
                phase="implementing",
                status="running",
                completion_state="in_progress",
            )

            self.assertEqual("changes_requested", review["status"])
            self.assertTrue(monitor["requires_revision_run"])
            self.assertEqual("pending_review", status)
            self.assertEqual("in_progress", completion_state)
            self.assertTrue(implementation_monitor["review_ready"])


if __name__ == "__main__":
    unittest.main()
