#!/usr/bin/env python3
"""Notification hook: record a factory run blocked on a permission prompt.

Claude Code fires Notification when it needs a human to approve a tool call.
Nothing else observes that today, so an unattended run that stalls on a prompt
is invisible once the terminal is gone — even though #432 R6 says a mid-run
prompt *is* an allowlist bug. This hook turns it into a journal entry.

Correlation is by NUKE_FACTORY_RUN carrying the issue number, never by cwd: a
GATE-stage prompt happens before any worktree exists, and its cwd matches every
run in the registry equally.

Notification payloads carry a message, not a tool name, so the tool is parsed
out of the message and the command is unavailable — the deny gate records the
command, this records the stall.

This is the one agent-specific surface in an otherwise agent-agnostic registry.
Under any other agent no events are recorded and a run with none renders as
normal, not broken.

Usage:
    registered as a Notification hook in .claude/settings.json; reads the hook
    payload on stdin.

Exit codes:
    0  always — an observability hook must never block a tool call.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factory_run
import hook_common

_TOOL = re.compile(r"permission to use ([A-Za-z_][\w.-]*)")


def parse_tool(message):
    """The tool named in a permission prompt, or None."""
    match = _TOOL.search(message or "")
    return match.group(1) if match else None


def main():
    payload = hook_common.read_payload()
    if payload is None:
        return 0                      # fail open, like every hook here
    issue = factory_run.run_issue()
    if issue is None:
        return 0                      # not an attributable factory run
    message = payload.get("message") or ""
    try:
        factory_run.append_event(issue, "permission",
                                 tool=parse_tool(message) or "unknown",
                                 outcome="blocked", message=message)
    except Exception:
        pass                          # recording must never block the call
    return 0


if __name__ == "__main__":
    sys.exit(main())
