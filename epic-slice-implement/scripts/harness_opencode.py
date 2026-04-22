#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from common import emit_json, require_cli, run_cmd, write_text


def salvage_plan_from_stdout(stdout: str, epic_key: str, packet_id: str) -> str | None:
    text = stdout.strip()
    if not text:
        return None
    headers = [
        f"# {epic_key} / {packet_id} / Implementation Plan",
        f"# {epic_key} / {packet_id} / OpenCode Implementation Plan",
    ]
    for expected_header in headers:
        if expected_header in text:
            return text[text.index(expected_header) :].rstrip() + "\n"
    return None


def run_packet_planning(
    *,
    root: Path,
    epic_key: str,
    packet_id: str,
    model: str,
    title: str,
    prompt: str,
    output_path: Path,
    model_check: dict,
    packet_path: Path,
) -> None:
    require_cli("opencode")
    if output_path.exists():
        output_path.unlink()
    proc = run_cmd(
        [
            "opencode",
            "run",
            "--model",
            model,
            "--dir",
            str(root),
            "--title",
            title,
            prompt,
        ],
        check=False,
    )

    stdout = proc.stdout or ""
    stderr = proc.stderr or ""

    if proc.returncode != 0:
        emit_json(
            {
                "status": "failed",
                "reason": "opencode_run_failed",
                "harness": "opencode",
                "model": model,
                "model_check": model_check,
                "packet_path": str(packet_path),
                "output_path": str(output_path),
                "returncode": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        )
        raise SystemExit(proc.returncode)

    if not output_path.exists():
        salvaged = salvage_plan_from_stdout(stdout, epic_key, packet_id)
        if salvaged is not None:
            write_text(output_path, salvaged)
            emit_json(
                {
                    "status": "completed",
                    "harness": "opencode",
                    "model": model,
                    "model_check": model_check,
                    "packet_path": str(packet_path),
                    "output_path": str(output_path),
                    "title": title,
                    "recovered_from_stdout": True,
                }
            )
            return
        emit_json(
            {
                "status": "failed",
                "reason": "missing_plan_artifact",
                "harness": "opencode",
                "model": model,
                "model_check": model_check,
                "packet_path": str(packet_path),
                "output_path": str(output_path),
                "returncode": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        )
        raise SystemExit(2)

    emit_json(
        {
            "status": "completed",
            "harness": "opencode",
            "model": model,
            "model_check": model_check,
            "packet_path": str(packet_path),
            "output_path": str(output_path),
            "title": title,
        }
    )
