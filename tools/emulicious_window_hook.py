#!/usr/bin/env python3
"""PreToolUse hook: park the Emulicious windows before the emulator launches.

Emulicious restores its last window position, which drifts off-screen across
sessions. This resets it to a known spot and closes the debugger pane.

The ini path is machine-specific and comes from the environment, supplied by
the user settings tier (~/.claude/settings.json):

  EMULICIOUS_INI   Absolute path to Emulicious.ini. When unset or missing the
                   hook does nothing.

Always exits 0 — a cosmetic convenience must never block a launch.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hook_common

WINDOW_SETTINGS = {
    'WindowEmuliciousX': '100',
    'WindowEmuliciousY': '50',
    'WindowDebuggerX': '100',
    'WindowDebuggerY': '50',
    'WindowDebuggerOpen': 'false',
}

_LAUNCH = re.compile(r'emulicious\.jar', re.IGNORECASE)


def is_launch(command):
    """True when *command* launches the Emulicious jar."""
    return bool(command) and bool(_LAUNCH.search(command))


def rewrite(text):
    """Return *text* with the window keys reset. Absent keys are not added."""
    out = []
    for line in text.splitlines(True):
        newline = ''
        stripped = line
        if stripped.endswith('\n'):
            stripped, newline = stripped[:-1], '\n'
        key, sep, _ = stripped.partition('=')
        if sep and key in WINDOW_SETTINGS:
            out.append('%s=%s%s' % (key, WINDOW_SETTINGS[key], newline))
        else:
            out.append(line)
    return ''.join(out)


def main():
    data = hook_common.read_payload()
    if data is None:
        sys.exit(0)

    if not is_launch(data.get('tool_input', {}).get('command', '')):
        sys.exit(0)

    path = os.environ.get('EMULICIOUS_INI')
    if not path or not os.path.isfile(path):
        sys.exit(0)

    try:
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(rewrite(text))
    except OSError:
        pass  # cosmetic only — never block a launch

    sys.exit(0)


if __name__ == '__main__':
    main()
