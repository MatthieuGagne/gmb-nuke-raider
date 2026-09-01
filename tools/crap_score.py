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


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import install_hooks  # noqa: E402  (path must be set first)


def _scope_from_diff(diff_text):
    """{'src/foo.c': {11, 12}} — the post-image lines a unified diff touches."""
    scope = {}
    current = None
    for line in diff_text.splitlines():
        if line.startswith('+++ '):
            path = line[4:].strip()
            if path == '/dev/null':
                current = None
            else:
                current = path[2:] if path.startswith('b/') else path
                scope.setdefault(current, set())
        elif line.startswith('@@') and current is not None:
            if '+' not in line:
                continue
            # "@@ -10,0 +11,2 @@ int foo_hairy(int a)" -> "11,2"
            body = line.split('+', 1)[1].split(' ', 1)[0]
            start, _, count = body.partition(',')
            try:
                start = int(start)
                count = int(count) if count else 1
            except ValueError:
                continue
            scope[current].update(range(start, start + count))
    return scope


def scope_from_commit_range(rev_range, repo_root='.'):
    # clean_env(): git exports GIT_DIR/GIT_INDEX_FILE into every hook's
    # environment and they override cwd, so a crap_score invoked from a hook
    # would otherwise diff the hook's repository, not repo_root (#441).
    proc = subprocess.run(
        ['git', 'diff', '--unified=0', rev_range],
        cwd=repo_root, capture_output=True, text=True, env=install_hooks.clean_env(),
    )
    if proc.returncode != 0:
        raise ToolMissing(
            f"crap_score: git diff --unified=0 {rev_range} failed in {repo_root} — "
            f"{proc.stderr.strip()}"
        )
    return _scope_from_diff(proc.stdout)


def render(records, threshold):
    over = [r for r in records if r['over']]
    lines = [f"CRAP threshold {threshold:g} — {len(over)} over threshold "
             f"of {len(records)} in-scope function(s)"]
    for r in over:
        lines.append(
            f"  {r['file']}:{r['line']}  {r['function']}  "
            f"complexity={r['complexity']}  coverage={r['coverage'] * 100:.1f}%  "
            f"crap={r['crap']:.1f}"
        )
    if over:
        lines.append("")
        lines.append("Fix each by covering its untested branches, or by splitting it into "
                     "smaller functions. Re-run `make coverage` before re-checking. Note "
                     "complexity is measured unpreprocessed, so #ifdef __SDCC branches count.")
    return "\n".join(lines)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(
        prog='crap_score.py',
        description='CRAP score gate for diff-scoped src/*.c functions (#699).',
    )
    parser.add_argument('--threshold', type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument('--files', nargs='+', default=None,
                        help='repo-relative paths; every function in each file is scored')
    parser.add_argument('--commit-range', default=None,
                        help='e.g. origin/master...HEAD; only functions whose span '
                             'intersects the changed lines are scored')
    parser.add_argument('--coverage-dir', default=DEFAULT_COVERAGE_DIR)
    parser.add_argument('--repo-root', default='.')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    if bool(args.files) == bool(args.commit_range):
        sys.stderr.write(
            "crap_score: give exactly one scope — --files <paths> or --commit-range <range>. "
            "Scoring the whole codebase is out of scope by design (#699).\n"
        )
        return 2

    line_scope = None
    try:
        if args.commit_range:
            line_scope = scope_from_commit_range(args.commit_range, args.repo_root)
            files = sorted(line_scope)
        else:
            files = list(args.files)
        files = [f.replace('\\', '/') for f in files]
        files = [f for f in files if f.startswith('src/') and f.endswith('.c')]
        scoped = [f for f in files if f not in EXEMPT_FILES]
        exempt = [f for f in files if f in EXEMPT_FILES]
        if not scoped:
            if args.json:
                print(json.dumps({'threshold': args.threshold, 'scope': [], 'exempt': exempt,
                                  'findings': [], 'violations': 0}, indent=2))
            else:
                print(render([], args.threshold))
            return 0
        coverage = collect_coverage(args.coverage_dir, args.repo_root, expected=scoped)
        complexity = collect_complexity(scoped, args.repo_root)
    except ToolMissing as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2

    records = score(files, coverage, complexity, args.threshold, line_scope)
    if args.json:
        print(json.dumps({
            'threshold': args.threshold,
            'scope': scoped,
            'exempt': exempt,
            'findings': records,
            'violations': sum(1 for r in records if r['over']),
        }, indent=2))
    else:
        print(render(records, args.threshold))
    return 1 if any(r['over'] for r in records) else 0


if __name__ == '__main__':
    sys.exit(main())
