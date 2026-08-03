#!/usr/bin/env python3
"""Deterministic PR body for a factory run.

Renders from run state and journal only, in canonical order: gates by stage
(GATE → PLAN → BUILD → VERIFY → SHIP) and decisions in journal order, never
dict order. The output is compared byte-exactly by the tests, so trailing
whitespace and the final newline are part of the contract.

The body carries no absolute paths. The worktree path stays in the state,
journal, and autopsy bundle — where resume and forensics need it — and out of
the pull request. Anything that slips through is redacted rather than raising:
failing to ship because a decision mentioned a path is the worse outcome.

Usage:
    python3 tools/factory_report.py --issue 436
    python3 tools/factory_report.py --issue 436 --out body.md
    python3 tools/factory_report.py --issue 436 --registry PATH
    python3 tools/factory_report.py --issue 436 --now 2026-07-26T12:00:00+00:00
    or imported:  factory_report.render(state) -> str

Exit codes:
    0  body rendered
    2  operational error (no registry entry, output unwritable, bad --now)
"""
import argparse
import os
import re
import sys

_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TOOLS_DIR)
import factory_run
sys.path.remove(_TOOLS_DIR)

# Windows drive paths, UNC paths, and the usual POSIX absolute roots. Kept
# tight on purpose: a relative path like docs/plans/x.md must survive.
ABSOLUTE_PATH = re.compile(
    r'[A-Za-z]:[\\/][^\s`|]*'
    r'|\\\\[^\s`|]+'
    r'|(?<![\w.~-])/(?:home|Users|opt|mnt|srv|var|tmp)/[^\s`|]*')

REDACTION = '<path>'


def redact(text):
    """Replace absolute paths with a placeholder."""
    return ABSOLUTE_PATH.sub(REDACTION, text)


def _cell(value):
    """One table cell: None becomes a dash, pipes are escaped."""
    if value is None or value == '':
        return '-'
    return str(value).replace('|', r'\|')


def _outcome(state):
    if state.get('failure'):
        return 'failed'
    if state.get('finished'):
        return state['finished'].get('result') or 'finished'
    return 'in progress'


def _autopsy_rel(state):
    """Registry-relative autopsy path — relative by design (see module doc)."""
    return '.factory/runs/issue-%d/autopsy/attempt-%d/' % (
        state['issue'], int(state.get('attempt') or 1))


def decision_lines(decision, bullet="- "):
    """The Markdown for one decision, as a list of lines (#517 R17).

    A decision that carries a rationale renders as a bold one-line ruling plus
    a collapsed block; one that does not renders as the plain bullet it always
    was, so a journal written before the field split still renders. The two
    renderers share this function so the run issue and the pull request body
    cannot drift apart.
    """
    text = decision.get("text") or "-"
    rationale = decision.get("rationale")
    if not rationale:
        return ["%s%s" % (bullet, text)]
    indent = " " * len(bullet)
    out = ["%s**%s**" % (bullet, text),
           "%s<details><summary>Rationale</summary>" % indent,
           ""]
    for line in str(rationale).split("\n"):
        out.append((indent + line).rstrip() if line.strip() else "")
    out += ["", "%s</details>" % indent]
    return out


def render(state):
    """The full PR body for *state*, ending in exactly one newline."""
    issue = state['issue']
    out = [
        '## Summary',
        '',
        'Factory run for issue #%d — %s.' % (issue, state.get('slug') or '(no slug)'),
        '',
        '- Attempt: %d' % int(state.get('attempt') or 1),
        '- Stage reached: %s' % (state.get('stage') or '(none)'),
        '- Outcome: %s' % _outcome(state),
        '',
        '## Gate results',
        '',
        '| Stage | Gate | Result |',
        '| --- | --- | --- |',
    ]
    gates = factory_run.ordered_gates(state)
    if gates:
        out += ['| %s | %s | %s |' % (_cell(g.get('stage')), _cell(g.get('gate')),
                                      _cell(g.get('result'))) for g in gates]
    else:
        out.append('| - | _no gates recorded_ | - |')

    out += ['', '## Decisions made', '']
    decisions = state.get('decisions') or []
    if decisions:
        for decision in decisions:
            out += decision_lines(decision)
    else:
        out.append('_None recorded._')
    out.append('')

    if state.get('failure'):
        out += ['## FAILED', '',
                state['failure'].get('message') or '(no message)', '',
                'Autopsy bundle: `%s`' % _autopsy_rel(state), '']
    else:
        out += ['## Scenario evidence', '', '| Scenario | Result |', '| --- | --- |']
        scenarios = state.get('scenarios') or []
        if scenarios:
            out += ['| %s | %s |' % (_cell(s.get('scenario')), _cell(s.get('result')))
                    for s in scenarios]
        else:
            out.append('| _none run_ | - |')
        out.append('')

    permissions = state.get('permissions') or []
    if permissions:
        out += ['## Permission events', '', '| Tool | Outcome | Command |',
                '| --- | --- | --- |']
        out += ['| %s | %s | %s |' % (_cell(p.get('tool')), _cell(p.get('outcome')),
                                      _cell(p.get('command')))
                for p in permissions]
        out.append('')

    out.append('Closes #%d' % issue)
    return redact('\n'.join(out) + '\n')


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--issue', type=int, required=True,
                        help='issue number of the run to report on')
    parser.add_argument('--registry', default=None,
                        help='registry root (default: <main repo root>/.factory)')
    parser.add_argument('--out', default=None,
                        help='write the body here instead of stdout')
    parser.add_argument('--now', default=None,
                        help='pin the clock, UTC ISO-8601 (determinism seam)')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.now:
        try:
            pinned = factory_run.parse_now(args.now)
        except ValueError as exc:
            print('factory_report: bad --now: %s' % exc, file=sys.stderr)
            return 2
        factory_run.set_clock(lambda: pinned)

    try:
        registry = args.registry or factory_run.registry_root()
        state = factory_run.load_state(args.issue, registry)
    except (RuntimeError, OSError) as exc:
        print('factory_report: %s' % exc, file=sys.stderr)
        return 2
    if state is None:
        print('factory_report: no registry entry for issue #%d under %s'
              % (args.issue, registry), file=sys.stderr)
        return 2

    body = render(state)
    if args.out:
        try:
            directory = os.path.dirname(os.path.abspath(args.out))
            os.makedirs(directory, exist_ok=True)
            with open(args.out, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(body)
        except OSError as exc:
            print('factory_report: cannot write %s: %s' % (args.out, exc),
                  file=sys.stderr)
            return 2
    else:
        sys.stdout.write(body)
    return 0


if __name__ == '__main__':
    sys.exit(main())
