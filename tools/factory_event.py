#!/usr/bin/env python3
"""Append one factory run event from the command line (#437).

`factory_run` is the sole writer of run state and the journal, but it is a
library with no CLI (ADR 0003 (#468)) — `factory_status` and `factory_report`
are read-only surfaces, so nothing could write an event from a skill's prose.
This is that surface: a thin argv wrapper over `factory_run.append_event`.

It adds no schema of its own. `--kind` is validated against
`factory_run.EVENT_KINDS` and every `--field` lands in the event verbatim, so
the vocabulary stays owned by `factory_run` and this file never has to be
edited when an event grows a field.

A field value is parsed as JSON when it parses and kept as a string when it
does not, so `--field blocking=true` records a boolean, `--field count=3` an
int, and `--field result=pass` the string "pass". A decision text that happens
to be bare digits is therefore recorded as a number; quote it as `"123"` when
that matters.

Exit codes:
    0  event appended
    2  misuse (unknown kind, malformed --field, bad --now) or operational error
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import factory_run


def parse_field(text):
    """Split one KEY=VALUE argument. VALUE is JSON when it parses."""
    if '=' not in text:
        raise ValueError('malformed --field %r: expected KEY=VALUE' % text)
    key, _, raw = text.partition('=')
    if not key:
        raise ValueError('malformed --field %r: empty key' % text)
    try:
        return key, json.loads(raw)
    except ValueError:
        return key, raw


def parse_fields(items):
    """Turn a list of KEY=VALUE arguments into a dict."""
    fields = {}
    for item in items or ():
        key, value = parse_field(item)
        fields[key] = value
    return fields


def build_parser():
    parser = argparse.ArgumentParser(
        description='Append one event to a factory run journal.')
    parser.add_argument('--issue', type=int, required=True,
                        help='spec issue number')
    parser.add_argument('--kind', required=True,
                        help='event kind (one of: %s)'
                             % ', '.join(factory_run.EVENT_KINDS))
    parser.add_argument('--field', action='append', default=[],
                        metavar='KEY=VALUE',
                        help='event field; repeatable')
    parser.add_argument('--attempt', type=int, default=None,
                        help='attempt number; inherits run state when omitted')
    parser.add_argument('--registry', default=None,
                        help='registry root (default: <main repo root>/.factory)')
    parser.add_argument('--now', default=None,
                        help='pin the clock, UTC ISO-8601')
    parser.add_argument('--json', action='store_true', dest='as_json',
                        help='print the written event as JSON')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    try:
        fields = parse_fields(args.field)
    except ValueError as exc:
        sys.stderr.write('factory-event: %s\n' % exc)
        return 2

    if args.now:
        try:
            pinned = factory_run.parse_now(args.now)
        except ValueError as exc:
            sys.stderr.write('factory-event: %s\n' % exc)
            return 2
        factory_run.set_clock(lambda: pinned)

    try:
        event = factory_run.append_event(args.issue, args.kind,
                                         registry=args.registry,
                                         attempt=args.attempt, **fields)
    except (TypeError, ValueError, RuntimeError, OSError) as exc:
        sys.stderr.write('factory-event: %s\n' % exc)
        return 2

    if args.as_json:
        sys.stdout.write(json.dumps(event, indent=2, sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
