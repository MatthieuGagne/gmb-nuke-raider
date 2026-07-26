#!/usr/bin/env python3
"""Validate .claude/settings.json's permission rules.

Two checks:

  --hygiene   Structural rules over the allow list. The canonical-form rule is
              load-bearing, not cosmetic: the coverage check must decide
              whether a command is permitted, and a checker that approximates
              Claude Code's full matching semantics can report coverage the
              real harness will not honour. Constraining the grammar to one
              form per tool makes the matcher exact over this file.

  --coverage  Every command in the inventory must match at least one allow
              rule and no deny rule.

Exit 0 when clean, 1 when any check fails.
"""
import argparse
import json
import os
import re
import sys

DEFAULT_SETTINGS = os.path.join('.claude', 'settings.json')
DEFAULT_INVENTORY = os.path.join('tests', 'fixtures', 'factory_commands.txt')

# Canonical rule suffix per shell tool. Any other spelling is a hygiene error.
SHELL_FORMS = {'Bash': ':*', 'PowerShell': ' *'}

ABSOLUTE_PATH = re.compile(r'[A-Za-z]:[\\/]|//[a-z]/|/opt/|Program Files')

_ENTRY = re.compile(r'^([A-Za-z]+)\((.*)\)$', re.DOTALL)


def load_settings(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def _split(entry):
    """Return (tool, spec) for ``Tool(spec)``, or (entry, None) for bare names."""
    m = _ENTRY.match(entry)
    if not m:
        return entry, None
    return m.group(1), m.group(2)


def parse_rule(entry):
    """Return (tool, prefix) for a canonical shell rule.

    Non-shell tools return (tool, None) — they carry no prefix semantics and are
    exempt from the canonical-form rule. A malformed shell rule returns None.
    """
    tool, spec = _split(entry)
    if tool not in SHELL_FORMS:
        return (tool, None)
    if spec is None:
        return None
    suffix = SHELL_FORMS[tool]
    if not spec.endswith(suffix):
        return None
    prefix = spec[:-len(suffix)]
    if not prefix or '*' in prefix:
        return None
    return (tool, prefix)


def rule_matches(prefix, command):
    """True when *command* is *prefix* or begins with it at a word boundary."""
    return command == prefix or command.startswith(prefix + ' ')


def check_hygiene(settings):
    """Return a list of human-readable hygiene errors (empty when clean)."""
    perms = settings.get('permissions', {})
    allow = perms.get('allow', [])
    deny = perms.get('deny', [])
    errors = []

    for entry in allow:
        if ABSOLUTE_PATH.search(entry):
            errors.append(
                '%s: absolute path — machine-specific values belong in the '
                'user tier (~/.claude/settings.json)' % entry)

    parsed = {}
    for entry in allow:
        tool, _ = _split(entry)
        if tool not in SHELL_FORMS:
            continue
        rule = parse_rule(entry)
        if rule is None:
            errors.append(
                '%s: not in canonical form — %s entries must be written '
                '%s(prefix%s)' % (entry, tool, tool, SHELL_FORMS[tool]))
        else:
            parsed[entry] = rule

    for entry, (tool, prefix) in parsed.items():
        for other, (otool, oprefix) in parsed.items():
            if other == entry or otool != tool:
                continue
            if len(oprefix) < len(prefix) and rule_matches(oprefix, prefix):
                errors.append('%s: redundant — already covered by %s'
                              % (entry, other))
                break

    if allow != sorted(allow):
        errors.append('allow list is not sorted')

    for entry in allow:
        if entry in deny:
            errors.append('%s: appears in both allow and deny' % entry)

    return errors


def load_inventory(path):
    """Return [(tool, command)] from the inventory, skipping comments/blanks."""
    out = []
    with open(path, encoding='utf-8') as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            tool, _, command = line.partition(':')
            out.append((tool.strip(), command.strip()))
    return out


def check_coverage(settings, inventory):
    """Return a list of coverage errors (empty when every command is covered)."""
    perms = settings.get('permissions', {})
    allows = [r for r in (parse_rule(e) for e in perms.get('allow', []))
              if r and r[1] is not None]
    denies = [r for r in (parse_rule(e) for e in perms.get('deny', []))
              if r and r[1] is not None]
    errors = []

    for tool, command in inventory:
        blocked = [p for t, p in denies if t == tool and rule_matches(p, command)]
        if blocked:
            errors.append('%s: %s — matched by deny rule %s(%s)'
                          % (tool, command, tool, blocked[0]))
            continue
        if not any(t == tool and rule_matches(p, command) for t, p in allows):
            errors.append('%s: %s — no allow rule covers this command'
                          % (tool, command))
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--hygiene', action='store_true')
    ap.add_argument('--coverage', action='store_true')
    ap.add_argument('--settings', default=DEFAULT_SETTINGS)
    ap.add_argument('--inventory', default=DEFAULT_INVENTORY)
    args = ap.parse_args(argv)

    run_all = not (args.hygiene or args.coverage)
    settings = load_settings(args.settings)
    errors = []

    if args.hygiene or run_all:
        errors += check_hygiene(settings)
    if args.coverage or run_all:
        errors += check_coverage(settings, load_inventory(args.inventory))
        print('note: coverage is necessary but not sufficient — the supervised '
              'bootstrap run (#432 AC2) is the empirical confirmation.')

    for e in errors:
        print('FAIL %s' % e)
    if errors:
        print('%d problem(s) in %s' % (len(errors), args.settings))
        return 1
    print('OK %s' % args.settings)
    return 0


if __name__ == '__main__':
    sys.exit(main())
