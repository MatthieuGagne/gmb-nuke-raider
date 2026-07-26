"""Synthetic factory registries for the factory_* tool tests.

Not a test module. Every registry is built through factory_run's own writers
under a pinned, auto-advancing clock, so the fixtures exercise the real append
path instead of hand-written JSON that could drift from the schema.
"""
import os
import struct
import sys
import zlib
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import factory_run

START = datetime(2026, 7, 26, 12, 0, 0, tzinfo=timezone.utc)
FIXED_NOW = datetime(2026, 7, 26, 14, 0, 0, tzinfo=timezone.utc)
STEP = timedelta(seconds=60)


def pinned_clock(start=START, step=STEP):
    """Install an auto-advancing clock; return a reset callable."""
    state = {'t': start}

    def tick():
        now = state['t']
        state['t'] = now + step
        return now

    factory_run.set_clock(tick)
    return lambda: factory_run.set_clock(None)


def _at(moment):
    """Pin the clock to one exact moment (no advance)."""
    factory_run.set_clock(lambda: moment)


def _worktree(tmpdir, issue, create=True):
    path = os.path.join(tmpdir, 'wt-%d' % issue)
    if create:
        os.makedirs(os.path.join(path, 'build', 'smoketest', 'reach-race'),
                    exist_ok=True)
    return path


GB_SCREEN = (160, 144)          # a real Game Boy frame, so the demo looks right


def _colour(name):
    """Deterministic colour per file name, bright enough on a dark page.

    Failure frames are red so the one screenshot that matters is obvious in
    the dashboard at a glance.
    """
    if os.path.basename(name).startswith('failure'):
        return (170, 60, 60)
    seed = sum(ord(c) * (i + 1) for i, c in enumerate(os.path.basename(name)))
    return (80 + seed * 37 % 176, 80 + seed * 61 % 176, 80 + seed * 89 % 176)


def _png_bytes(width, height, rgb):
    """A real, minimal RGB PNG. Stdlib only, byte-identical for a given colour.

    These fixtures once wrote a PNG signature followed by filler. Every
    decoder rejects that, so the dashboard embedded it happily and the browser
    drew a broken-image icon: a screenshot fixture that cannot be displayed
    cannot demonstrate the one thing the HTML page exists for.
    """
    scanlines = (b'\x00' + bytes(rgb) * width) * height

    def chunk(tag, payload):
        return (struct.pack('>I', len(payload)) + tag + payload
                + struct.pack('>I', zlib.crc32(tag + payload) & 0xffffffff))

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n'
            + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(scanlines, 9))
            + chunk(b'IEND', b''))


def _png(path):
    """Write a displayable PNG whose colour is derived from its name."""
    with open(path, 'wb') as fh:
        fh.write(_png_bytes(GB_SCREEN[0], GB_SCREEN[1], _colour(path)))
    return path


def build_registry(tmpdir):
    """Three runs covering the dashboard's three interesting conditions.

      436  active  — retry, mixed gates, a denied permission, worktree present
      437  idle    — worktree present, last event two hours before FIXED_NOW
      999  stale   — worktree recorded but never created on disk

    Returns the registry root.
    """
    reg = os.path.join(tmpdir, 'registry')
    reset = pinned_clock(START)
    try:
        wt436 = _worktree(tmpdir, 436)
        shots = os.path.join(wt436, 'build', 'smoketest', 'reach-race')
        for name in ('checkpoint-1.png', 'checkpoint-2.png',
                     'checkpoint-3.png', 'checkpoint-4.png', 'failure.png'):
            _png(os.path.join(shots, name))

        ev = lambda kind, **kw: factory_run.append_event(
            436, kind, registry=reg, render=False, **kw)
        ev('start', slug='observability', branch='worktree-obs-436',
           worktree=wt436, plan='docs/plans/2026-07-26-issue436-observability.md',
           stage='GATE')
        ev('gate', stage='GATE', gate='spec lint', result='pass')
        ev('decision',
           text='Journal is the source of truth; state.json is a projection.')
        ev('stage', stage='PLAN')
        ev('stage', stage='BUILD')
        ev('gate', stage='BUILD', gate='make test-tools', result='fail')
        ev('retry', attempt=2, stage='BUILD')
        # A retry re-runs the gates from the top, so attempt 2 records its own
        # GATE-stage pass. Without it this run would carry a single gate and
        # could not exercise canonical cross-stage ordering.
        ev('gate', stage='GATE', gate='spec lint', result='pass')
        ev('gate', stage='BUILD', gate='make test-tools', result='pass')
        ev('permission', tool='Bash', outcome='denied',
           command='git push --force origin worktree-obs-436',
           reason='force push')
        # Last event lands one minute before FIXED_NOW → active, not idle.
        _at(FIXED_NOW - timedelta(seconds=60))
        factory_run.append_event(436, 'stage', registry=reg, render=False,
                                 stage='VERIFY')

        _at(START)
        wt437 = _worktree(tmpdir, 437)
        factory_run.append_event(437, 'start', registry=reg, render=False,
                                 slug='quiet', branch='worktree-quiet-437',
                                 worktree=wt437, stage='GATE')
        _at(FIXED_NOW - timedelta(hours=2))
        factory_run.append_event(437, 'stage', registry=reg, render=False,
                                 stage='BUILD')

        _at(START)
        factory_run.append_event(999, 'start', registry=reg, render=False,
                                 slug='ghost', branch='worktree-ghost-999',
                                 worktree=_worktree(tmpdir, 999, create=False),
                                 stage='BUILD')
    finally:
        reset()
    return reg


def build_shipped_run(tmpdir):
    """One complete, successful run (issue 440). Returns the registry root."""
    reg = os.path.join(tmpdir, 'registry-shipped')
    reset = pinned_clock(START)
    try:
        ev = lambda kind, **kw: factory_run.append_event(
            440, kind, registry=reg, render=False, **kw)
        ev('start', slug='observability', branch='worktree-obs-440',
           worktree=_worktree(tmpdir, 440),
           plan='docs/plans/2026-07-26-issue440-demo.md', stage='GATE')
        ev('gate', stage='GATE', gate='spec lint', result='pass')
        ev('decision',
           text='Journal is the source of truth; state.json is a projection.')
        ev('stage', stage='PLAN')
        ev('gate', stage='PLAN', gate='plan self-review', result='pass')
        ev('decision', text='Screenshots are embedded as data URIs so the '
                            'page survives worktree deletion.')
        ev('stage', stage='BUILD')
        ev('gate', stage='BUILD', gate='make test-tools', result='pass')
        ev('stage', stage='VERIFY')
        ev('scenario', scenario='reach-race', result='pass')
        ev('stage', stage='SHIP')
        ev('gate', stage='SHIP', gate='smoketest confirmed', result='pass')
        ev('finish', result='shipped')
    finally:
        reset()
    return reg


def build_failed_run(tmpdir):
    """One run that died in BUILD (issue 441). Returns the registry root."""
    reg = os.path.join(tmpdir, 'registry-failed')
    reset = pinned_clock(START)
    try:
        ev = lambda kind, **kw: factory_run.append_event(
            441, kind, registry=reg, render=False, **kw)
        ev('start', slug='autopsy-demo', branch='worktree-autopsy-441',
           worktree=_worktree(tmpdir, 441),
           plan='docs/plans/2026-07-26-issue441-demo.md', stage='GATE')
        ev('gate', stage='GATE', gate='spec lint', result='pass')
        ev('decision', text='Autopsy assembly is best-effort; a missing '
                            'artifact is never an error.')
        ev('stage', stage='BUILD')
        ev('gate', stage='BUILD', gate='make test', result='fail')
        ev('failure', message='make test: tests/test_factory_run.py failed')
    finally:
        reset()
    return reg
