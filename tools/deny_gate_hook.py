#!/usr/bin/env python3
"""PreToolUse hook: refuse operations that must never happen in this repo.

Scans the raw command string of Bash and PowerShell tool calls. Scanning the
raw string rather than tokenising is deliberate: it catches wrapper forms such
as ``bash -c "git push --force"`` with the same pattern that catches the bare
command, which prefix-matched deny rules cannot do.

Exit 2 blocks the call and returns stderr to Claude; exit 0 allows it.

Two rule sets:
  UNCONDITIONAL  never legitimate here.
  FACTORY_ONLY   legitimate when a human is driving, forbidden to an
                 unattended run; active only when NUKE_FACTORY_RUN is set.

Fails open on unparseable input, matching the other hooks in this repo. The
`permissions.deny` list in .claude/settings.json is the backstop for that case.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hook_common

SHELL_TOOLS = ('Bash', 'PowerShell')

# A git push whose argument run contains a force flag in any spelling.
# (?<![\w-]) stops -f matching inside --follow-tags.
_FORCE = re.compile(
    r'\bgit\b[^\n;|&]*?\bpush\b[^\n;|&]*?'
    r'(--force\b|--force-with-lease\b|(?<![\w-])-f\b)')

# A git push targeting the default branch. Requires whitespace before the
# branch name and a boundary after it, so feature-master-fix is not caught.
_PUSH_DEFAULT = re.compile(
    r'\bgit\b[^\n;|&]*?\bpush\b[^\n;|&]*?\s(?:origin\s+)?(?:master|main)(?:\s|$)')

_PR_MERGE = re.compile(r'\bgh\b[^\n;|&]*?\bpr\b[^\n;|&]*?\bmerge\b')

UNCONDITIONAL = [
    (_FORCE, 'force push'),
    (_PUSH_DEFAULT, 'push to the default branch'),
    (_PR_MERGE, 'PR merge'),
]

FACTORY_ONLY = [
    (re.compile(r'\bgit\b[^\n;|&]*?\bworktree\b[^\n;|&]*?\b(?:remove|prune)\b'),
     'worktree removal'),
    (re.compile(r'\bgit\b[^\n;|&]*?\bbranch\b[^\n;|&]*?(?<![\w-])-[dD]\b'),
     'branch deletion'),
    (re.compile(r'\bgit\b[^\n;|&]*?\breset\b[^\n;|&]*?--hard\b'),
     'hard reset'),
]


def verdict(command, factory_run):
    """Return a refusal reason for *command*, or None to allow it."""
    for pattern, reason in UNCONDITIONAL:
        if pattern.search(command):
            return reason
    if factory_run:
        for pattern, reason in FACTORY_ONLY:
            if pattern.search(command):
                return reason
    return None


def main():
    data = hook_common.read_payload()
    if data is None:
        sys.exit(0)  # fail open, consistent with the other hooks

    if data.get('tool_name') not in SHELL_TOOLS:
        sys.exit(0)

    command = data.get('tool_input', {}).get('command', '')
    if not command:
        sys.exit(0)

    reason = verdict(command, bool(os.environ.get('NUKE_FACTORY_RUN')))
    if reason:
        sys.stderr.write(
            'Refused by the deny gate: %s.\n'
            'This operation is forbidden by .claude/settings.json and '
            'tools/deny_gate_hook.py (see docs/adr/0001-settings-tier-contract.md).\n'
            % reason)
        sys.exit(2)

    sys.exit(0)


if __name__ == '__main__':
    main()
