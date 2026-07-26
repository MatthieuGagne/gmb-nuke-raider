#!/usr/bin/env python3
"""Skill overlay injection hook (PostToolUse:Skill + UserPromptSubmit).

Reads hook JSON from stdin. If the invoked skill (model-invoked Skill tool,
or a user-typed /command which bypasses the Skill tool) has a project
overlay at <repo-root>/.claude/skill-overlays/<name>.md, emits
hookSpecificOutput JSON whose additionalContext is the overlay body.

The repo root is found by walking up from the hook JSON's `cwd`, so a
worktree session sees its own overlay edits; fallback is this script's own
repository.

Version canary: an overlay whose frontmatter says `baseline: superpowers@X`
gets a drift warning prepended when X differs from the installed
superpowers version in ~/.claude/plugins/installed_plugins.json
(override path for tests: env SKILL_OVERLAY_PLUGINS_JSON).

Fail-open by design: missing overlay, malformed input, or ANY internal
error -> exit 0 with no output. This hook must never block.
"""
import json
import os
import re
import sys

PLUGINS_JSON = os.environ.get('SKILL_OVERLAY_PLUGINS_JSON') or os.path.join(
    os.path.expanduser('~'), '.claude', 'plugins', 'installed_plugins.json')
SUPERPOWERS_KEY = 'superpowers@claude-plugins-official'
NAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]*$')


def skill_name(data):
    """Extract the bare skill name from either hook event; None = no-op."""
    event = data.get('hook_event_name')
    if event == 'PostToolUse':
        if data.get('tool_name') != 'Skill':
            return None
        raw = str(data.get('tool_input', {}).get('skill', ''))
    elif event == 'UserPromptSubmit':
        prompt = str(data.get('prompt', '')).lstrip()
        if not prompt.startswith('/'):
            return None
        tokens = prompt[1:].split()
        raw = tokens[0] if tokens else ''
    else:
        return None
    if ':' in raw:  # strip plugin prefix, e.g. superpowers:writing-plans
        raw = raw.rsplit(':', 1)[1]
    return raw if NAME_RE.match(raw) else None


def find_overlay(cwd, name):
    """Walk up from cwd to the nearest .claude/skill-overlays/<name>.md."""
    if cwd and os.path.isdir(cwd):
        start = cwd
    else:
        start = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    d = os.path.abspath(start)
    while True:
        path = os.path.join(d, '.claude', 'skill-overlays', name + '.md')
        if os.path.isfile(path):
            return path
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def split_frontmatter(text):
    """Return (frontmatter_dict, body); tolerate absent frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            fm = {}
            for line in lines[1:i]:
                if ':' in line:
                    key, _, value = line.partition(':')
                    fm[key.strip()] = value.strip()
            return fm, '\n'.join(lines[i + 1:]).lstrip('\n')
    return {}, text


def installed_superpowers_version():
    try:
        with open(PLUGINS_JSON, encoding='utf-8') as fh:
            return json.load(fh)['plugins'][SUPERPOWERS_KEY][0]['version']
    except Exception:
        return None


def canary_note(frontmatter):
    """One-line drift warning when the overlay's baseline lags the install."""
    plugin, sep, overlay_ver = frontmatter.get('baseline', '').partition('@')
    if not sep or plugin.strip() != 'superpowers':
        return ''  # no version source for non-superpowers baselines
    installed = installed_superpowers_version()
    if installed is None or installed == overlay_ver.strip():
        return ''
    return ('NOTE: the superpowers baseline has updated since this overlay '
            'was written (overlay baseline {0}, installed {1}) — if the '
            'baseline skill contradicts this overlay, flag it to the user '
            'instead of guessing.\n\n'
            .format(overlay_ver.strip(), installed))


def main():
    data = json.load(sys.stdin)
    name = skill_name(data)
    if not name:
        return
    path = find_overlay(data.get('cwd', ''), name)
    if not path:
        return
    with open(path, encoding='utf-8') as fh:
        frontmatter, body = split_frontmatter(fh.read())
    if not body.strip():
        return
    context = (
        "Project overlay for skill '{0}' (.claude/skill-overlays/{0}.md — "
        "project rules that extend and override the baseline skill; on "
        "conflict, the overlay wins):\n\n".format(name)
        + canary_note(frontmatter) + body
    )
    print(json.dumps({'hookSpecificOutput': {
        'hookEventName': data.get('hook_event_name'),
        'additionalContext': context,
    }}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        pass  # fail-open: never block, never emit noise
    sys.exit(0)
