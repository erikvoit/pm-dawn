#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
import shlex

from common import emit_json, opencode_server_session_name, repo_root
from pm_dawn_core.runtime import require_cli, run_cmd, tmux_has_session


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ensure a tmux-backed opencode server is running.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--port", type=int, default=4096)
    parser.add_argument("--hostname", default="127.0.0.1")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = repo_root(args.repo_root)
    require_cli("opencode")
    session_name = opencode_server_session_name(root)
    server_url = f"http://{args.hostname}:{args.port}"

    started = False
    if not tmux_has_session(session_name):
        cmd = (
            f"cd {shlex.quote(str(root))} && "
            f"opencode serve --hostname {shlex.quote(args.hostname)} "
            f"--port {shlex.quote(str(args.port))}"
        )
        run_cmd(["tmux", "new-session", "-d", "-s", session_name, cmd])
        started = True
        time.sleep(1)

    emit_json(
        {
            "repo_root": str(root),
            "server_url": server_url,
            "tmux_session": session_name,
            "status": "started" if started else "already_running",
        }
    )


if __name__ == "__main__":
    main()
