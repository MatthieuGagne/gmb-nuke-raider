#!/usr/bin/env python3
"""
crap_score.py — CRAP score gate: per-function cyclomatic complexity joined with
per-function line coverage, scored as comp**2 * (1 - cov)**3 + comp (#699).

Coverage comes from `gcov --json-format --stdout` over the .gcda files that
`make coverage` writes under build/coverage/obj/. Complexity comes from the
`lizard` Python package, pinned in requirements.txt. Neither tool is optional:
a missing one raises ToolMissing and exits 2, because a CRAP gate that cannot
run is a gate that silently passes — the exact shape that hid #461 for months.

Known limitation: lizard does not preprocess, gcov does. Code inside
`#ifdef __SDCC` guards (src/patrol.c, src/racer.c) counts toward lizard's
complexity but never reaches the host build, so gcov's line denominator
excludes it. Complexity is therefore biased upward on those files. The bias is
in the safe direction — it over-reports rather than under-reports — and is
accepted rather than fixed by duplicating SDCC's -D set.

Exit codes:
    0  every in-scope function is at or under the threshold
    1  at least one in-scope function is over it
    2  operational or usage error (missing tool, no coverage data, no scope)
"""
import glob
import importlib.util
import json
import os
import shutil
import subprocess
import sys

DEFAULT_THRESHOLD = 8
DEFAULT_COVERAGE_DIR = os.path.join('build', 'coverage')

# Exemptions are declared, never inferred (R5). A file leaves the gate only by
# appearing here, and tests/test_crap_score.py asserts every path still exists
# so a rename fails loudly instead of silently widening the exemption.
#
# main.c and the five state_*.c screens have no host test and cannot get one:
# they are GBDK entry points that call hardware init. state_hub.c,
# state_manager.c and state_playing.c DO have tests and stay in scope.
EXEMPT_SCREENS = (
    'src/main.c',
    'src/state_game_over.c',
    'src/state_overmap.c',
    'src/state_prerace.c',
    'src/state_results.c',
    'src/state_title.c',
)

# Generated asset data — tiles, sprites, maps, dialog and music tables emitted
# by tools/png_to_tiles.py, tools/tmx_to_c.py, tools/overmap_to_c.py and
# tools/dialog_to_c.py. Editing them by hand is already forbidden, so a CRAP
# finding in one is unactionable.
#
# Twenty entries, where #699's Notes counted nineteen. The difference is
# src/hub_data.c: it is generated (`// GENERATED — do not edit by hand`) but it
# also has tests/test_hub_data.c, so the issue's "generated files without a
# test" arithmetic excluded it. Generated is the criterion here, not untested.
EXEMPT_GENERATED = (
    'src/beam_tiles.c',
    'src/bullet_sprite.c',
    'src/dialog_arrow_sprite.c',
    'src/dialog_border_tiles.c',
    'src/dialog_data.c',
    'src/explosion_sprite.c',
    'src/hub_data.c',
    'src/music_data.c',
    'src/npc_drifter_portrait.c',
    'src/npc_mechanic_portrait.c',
    'src/npc_trader_portrait.c',
    'src/overmap_car_sprite.c',
    'src/overmap_map.c',
    'src/overmap_tiles.c',
    'src/player_sprite.c',
    'src/track2_map.c',
    'src/track3_map.c',
    'src/track_map.c',
    'src/track_tiles.c',
    'src/turret_sprite.c',
)

EXEMPT_FILES = EXEMPT_SCREENS + EXEMPT_GENERATED

# Indirection so tests can simulate an absent tool without touching the
# environment. Both are patched by tests/test_crap_score.py.
_find_spec = importlib.util.find_spec
_which = shutil.which


class ToolMissing(Exception):
    """A required external tool or input is absent. Carries an actionable message."""


def crap(complexity, coverage):
    """The standard CRAP score. `coverage` is a fraction in [0.0, 1.0]."""
    return complexity ** 2 * (1.0 - coverage) ** 3 + complexity


def _import_lizard():
    if _find_spec('lizard') is None:
        raise ToolMissing(
            "crap_score: the cyclomatic complexity tool 'lizard' is not installed. "
            "Install it with: python -m pip install -r requirements.txt"
        )
    import lizard
    return lizard


def _gcov_path():
    path = _which('gcov')
    if path is None:
        raise ToolMissing(
            "crap_score: the coverage tool 'gcov' is not on PATH. Install GCC "
            "(MinGW-W64 on Windows) so gcov resolves, then run: make coverage"
        )
    return path


def _rel_src_path(raw, repo_root='.'):
    """Normalise a gcov 'file' field to a repo-relative src/ path, or None.

    Anchored on the repo root, not on a trailing 'src' component: both
    tests/unity/src/unity.c and lib/hUGEDriver/src/hUGEDriver.c end in a src/
    directory and must be rejected (AC2)."""
    path = os.path.normpath(raw.replace('\\', '/')).replace('\\', '/')
    if os.path.isabs(path):
        try:
            path = os.path.relpath(path, os.path.abspath(repo_root)).replace('\\', '/')
        except ValueError:          # different drive on Windows
            return None
    parts = path.split('/')
    if len(parts) != 2 or parts[0] != 'src' or not parts[1].endswith('.c'):
        return None
    return 'src/' + parts[1]


def _coverage_from_payload(payload, repo_root='.'):
    """{'src/foo.c': {'foo_hairy': 0.5}} from one gcov JSON document."""
    out = {}
    for entry in payload.get('files', []):
        rel = _rel_src_path(entry.get('file', ''), repo_root)
        if rel is None:
            continue
        per_line = {}
        for line in entry.get('lines', []):
            name = line.get('function_name')
            if not name:
                continue
            key = (name, line['line_number'])
            per_line[key] = per_line.get(key, False) or line.get('count', 0) > 0
        totals = {}
        for (name, _num), hit in per_line.items():
            covered, total = totals.get(name, (0, 0))
            totals[name] = (covered + (1 if hit else 0), total + 1)
        merged = out.setdefault(rel, {})
        for name, (covered, total) in totals.items():
            merged[name] = covered / total if total else 0.0
    return out


def _json_documents(text):
    """Yield every JSON document in `text`.

    gcov on MinGW-W64 15.1.0 emits exactly one document per .gcda, so this
    loop normally runs once. It is kept deliberately: --stdout concatenation
    is a documented gcov behaviour on other versions, and a silent parse of
    only the first document would drop coverage without any error."""
    decoder = json.JSONDecoder()
    text = text.strip()
    idx = 0
    while idx < len(text):
        doc, end = decoder.raw_decode(text, idx)
        yield doc
        idx = end
        while idx < len(text) and text[idx] in ' \r\n\t':
            idx += 1


def collect_coverage(coverage_dir, repo_root='.', expected=None):
    """Run gcov over every .gcda under `coverage_dir` and merge the results.

    `expected` is the list of scoped files. Any of them absent from the merged
    map raises rather than scoring its functions at 0.0 coverage — an absent
    file means the join broke or the file was never instrumented, and silently
    reporting it as untested would fire the gate for the wrong reason."""
    root = coverage_dir if os.path.isabs(coverage_dir) else os.path.join(repo_root, coverage_dir)
    gcda = sorted(glob.glob(os.path.join(root, '**', '*.gcda'), recursive=True))
    if not gcda:
        raise ToolMissing(
            f"crap_score: no coverage data under {coverage_dir} — run: make coverage"
        )
    gcov = _gcov_path()
    merged = {}
    for path in gcda:
        proc = subprocess.run(
            [gcov, '--json-format', '--stdout', os.path.basename(path)],
            cwd=os.path.dirname(path), capture_output=True, text=True,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            continue
        for doc in _json_documents(proc.stdout):
            for rel, funcs in _coverage_from_payload(doc, repo_root).items():
                merged.setdefault(rel, {}).update(funcs)
    if not merged:
        raise ToolMissing(
            f"crap_score: gcov produced no src/ coverage from {coverage_dir} — "
            "run: make coverage"
        )
    for rel in expected or ():
        if rel not in merged:
            raise ToolMissing(
                f"crap_score: {rel} has no coverage data under {coverage_dir}. It was "
                "never instrumented, or the gcov join broke — either way its functions "
                "would all read as 0% coverage. Run: make coverage"
            )
    return merged


def collect_complexity(files, repo_root='.'):
    lizard = _import_lizard()
    out = {}
    for rel in files:
        abs_path = os.path.join(repo_root, rel)
        if not os.path.isfile(abs_path):
            continue
        analysis = lizard.analyze_file(abs_path)
        out[rel] = [
            {
                'name': fn.name,
                'line': fn.start_line,
                'end_line': fn.end_line,
                'complexity': fn.cyclomatic_complexity,
            }
            for fn in analysis.function_list
        ]
    return out


def score(files, coverage, complexity, threshold=DEFAULT_THRESHOLD, line_scope=None):
    """One record per in-scope function, worst CRAP first.

    `line_scope` is None (whole file in scope) or {'src/foo.c': {12, 13}} —
    only functions whose span intersects those lines are scored (R3)."""
    records = []
    for rel in files:
        if rel in EXEMPT_FILES:
            continue
        for fn in complexity.get(rel, []):
            if line_scope is not None:
                changed = line_scope.get(rel, set())
                if not any(n in changed for n in range(fn['line'], fn['end_line'] + 1)):
                    continue
            cov = coverage.get(rel, {}).get(fn['name'], 0.0)
            value = crap(fn['complexity'], cov)
            records.append({
                'file': rel,
                'function': fn['name'],
                'line': fn['line'],
                'complexity': fn['complexity'],
                'coverage': cov,
                'crap': value,
                'over': value > threshold,
            })
    records.sort(key=lambda r: (-r['crap'], r['file'], r['line']))
    return records
