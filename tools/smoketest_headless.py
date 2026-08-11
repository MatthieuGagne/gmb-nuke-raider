#!/usr/bin/env python3
"""Headless crash/freeze smoketest for nuke-raider.

Runs a scenario against a built ROM, asserting the game boots, reaches
gameplay, and stays alive. Emits a WRAM sentinel trace and a machine-readable
result. Intended as the agent factory's blocking VERIFY gate.

Usage:
    python3 tools/smoketest_headless.py [--scenario NAME|PATH] [--all]
                                        [--rom PATH] [--ref-rom PATH]
                                        [--out-dir DIR] [--json]

Exit codes: 0 = pass, 1 = run failure, 2 = tool/usage error,
            3 = scenario invalid (the scenario is wrong, not the game).

Output goes to the MAIN work tree by default, not to the checkout the run was
started from: a worktree is deleted when its branch merges, and the evidence
died with it (#588 R14). `--out-dir` still wins.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

# See the note in screenshot.py: tools/ leads sys.path only for our own import.
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TOOLS_DIR)
import pyboy_scenario as ps
import factory_run
sys.path.remove(_TOOLS_DIR)

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_SCENARIO_INVALID = 0, 1, 2, 3

DEFAULT_WATCH = ["_hp", "_px", "_py", "_active_lap_count"]

# Sample the WRAM sentinels (and render, feeding the freeze watchdog) this often.
DEFAULT_TRACE_EVERY = 30          # frames — twice per second at 60fps
# Deliberately loose: only a genuine hard hang holds the screen this long.
DEFAULT_FREEZE_FRAMES = 600       # frames — ~10s. 0 disables the watchdog.


def default_out_dir():
    """``<main work tree>/build/smoketest/<checkout directory name>``.

    factory_run.repo_root uses `git rev-parse --git-common-dir`, which is the
    one form that resolves the MAIN tree from inside a linked worktree
    (`--show-toplevel` returns the worktree). Outside a git tree the local
    checkout is the fallback, so the tool still runs from a tarball.

    The last element names the checkout the run started from. Two worktrees
    running the same scenario would otherwise overwrite each other's
    results.json, trace and screenshots, and factory_run.smoketest_dir would
    hand one run the other run's evidence.
    """
    local = Path(__file__).parent.parent
    leaf = os.path.basename(os.path.normpath(str(local)))
    try:
        main = factory_run.repo_root(str(local))
    except Exception:
        main = str(local)
    return os.path.join(main, "build", "smoketest", leaf)


def rebase_screenshots(steps, out_dir):
    """Point every relative screenshot path at this run's output directory.

    The library scenarios name a file, not a path. An older scenario that
    still names `build/smoketest/<name>/<file>.png` would write inside the
    checkout, which is what AC9 forbids, so only its file name is kept.
    """
    for step in steps:
        if step.get("action") != "screenshot":
            continue
        out = step.get("out")
        if not out or os.path.isabs(out):
            continue
        step["out"] = os.path.join(out_dir, os.path.basename(out))


def resolve_exit_code(results):
    """The process exit code for a whole run.

    A blocking game failure outranks an invalid scenario: a broken game is the
    more urgent report, and an invalid scenario is still visible in the JSON.
    """
    invalid = any(r["verdict"] == "scenario-invalid" for r in results)
    failed = any(r["verdict"] == "fail" and r.get("blocking") for r in results)
    if failed:
        return EXIT_FAIL
    if invalid:
        return EXIT_SCENARIO_INVALID
    return EXIT_PASS


def write_combined_results(results, out_dir):
    """One file holding every scenario outcome (R15). Returns its path."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "all-results.json")
    with open(path, "w") as f:
        json.dump({"verdicts": {r["scenario"]: r["verdict"] for r in results},
                   "scenarios": results}, f, indent=2)
    return path


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).parent.parent
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--scenario",      default="generic-smoke")
    p.add_argument("--all",           action="store_true",
                   help="run every scenario in the library")
    p.add_argument("--rom",           default=str(root / "build" / "nuke-raider.gb"))
    p.add_argument("--ref-rom",       default=None, dest="ref_rom")
    p.add_argument("--map",           default=str(root / "build" / "nuke-raider.map"))
    p.add_argument("--noi",           default=str(root / "build" / "nuke-raider.noi"))
    p.add_argument("--manifest",      default=str(root / "build" / "game-manifest.json"))
    p.add_argument("--library",       default=str(root / "tools" / "scenarios"))
    p.add_argument("--out-dir",       default=default_out_dir(),
                   dest="out_dir")
    p.add_argument("--json",          action="store_true", dest="as_json")
    p.add_argument("--trace-every",   type=int, default=DEFAULT_TRACE_EVERY,
                   dest="trace_every")
    p.add_argument("--freeze-frames", type=int, default=DEFAULT_FREEZE_FRAMES,
                   dest="freeze_frames")
    return p


def write_trace(records, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


def build_result(scenario_name, ctx, failure=None, divergence=None,
                 verdict=None, blocking=True):
    if verdict is None:
        verdict = "fail" if failure is not None else "pass"
    return {
        "verdict":  verdict,
        "scenario": scenario_name,
        "blocking": blocking,
        "steps_executed": ctx.step + 1,
        "frames":   ctx.frame,
        "failure":  None if failure is None else {
            "step":    failure.step,
            "action":  failure.action,
            "kind":    failure.kind,
            "message": failure.message,
        },
        "divergence": divergence,
        "artifacts": {"screenshots": list(ctx.screenshots)},
    }


def _resolve_scenario_path(name, library):
    if os.path.exists(name):
        return name
    candidate = os.path.join(library, name + ".json")
    if os.path.exists(candidate):
        return candidate
    raise ps.ScenarioError(f"Unknown scenario {name!r} (looked in {library})")


def _load_manifest(path):
    if not os.path.exists(path):
        raise ps.ScenarioError(
            f"Manifest not found: {path}. Run 'make' to generate it.")
    with open(path) as f:
        return json.load(f)


def run_one(rom, scenario, args, symbols, manifest, out_dir, tag=""):
    """Run one scenario against one ROM. Returns (ctx, failure_or_None)."""
    from pyboy import PyBoy

    os.makedirs(out_dir, exist_ok=True)
    ctx = ps.RunContext(
        symbols=symbols,
        manifest=manifest,
        watch=scenario.get("watch") or DEFAULT_WATCH,
        trace_every=args.trace_every,
        freeze_frames=args.freeze_frames,
        default_out=os.path.join(out_dir, f"final{tag}.png"),
    )
    emu = PyBoy(rom, window="null", sound_emulated=False)
    failure = None
    try:
        ps.run(emu, scenario["steps"], ctx)
    except (ps.StepFailure, ps.ScenarioError) as exc:
        # A ScenarioError raised mid-run — an unknown symbol, or a nav target
        # the manifest does not carry — used to escape as a traceback and kill
        # every scenario after this one, the blocking gate included (#507).
        # Report it as this scenario's failure instead. Everything downstream
        # then treats it exactly like an assertion failure.
        failure = exc if isinstance(exc, ps.StepFailure) else ps.StepFailure(
            ctx.step, "scenario", str(exc), ctx.action)
        try:
            ctx.capture(emu, os.path.join(out_dir, f"failure{tag}.png"))
        except Exception:
            pass
    finally:
        try:
            emu.stop()
        except Exception:
            pass
    write_trace(ctx.trace, os.path.join(out_dir, f"trace{tag}.jsonl"))
    return ctx, failure


def _report(result, as_json):
    if as_json:
        print(json.dumps(result, indent=2))
        return
    name = result["scenario"]
    mark = {"pass": "PASS", "fail": "FAIL",
            "scenario-invalid": "SCENARIO-INVALID"}[result["verdict"]]
    print(f"[{mark}] {name}  ({result['frames']} frames, "
          f"{result['steps_executed']} steps)")
    if result["failure"]:
        f = result["failure"]
        print(f"    step {f['step']} ({f['action']}) {f['kind']}: {f['message']}")
    if result["divergence"]:
        d = result["divergence"]
        print(f"    first divergence: step {d['step']} frame {d['frame']} "
              f"{d['symbol']} main={d['main']} ref={d['ref']}")


def main() -> int:
    args = build_parser().parse_args()

    if not os.path.exists(args.rom):
        print(f"ROM not found: {args.rom} (build first with 'make')", file=sys.stderr)
        return EXIT_USAGE

    try:
        manifest = _load_manifest(args.manifest)
        names = ([os.path.splitext(os.path.basename(p))[0]
                  for p in sorted(glob.glob(os.path.join(args.library, "*.json")))]
                 if args.all else [args.scenario])
        if not names:
            print(f"No scenarios found in {args.library}", file=sys.stderr)
            return EXIT_USAGE
        scenarios = [ps.load_scenario(_resolve_scenario_path(n, args.library),
                                      library_dir=args.library) for n in names]
    except ps.ScenarioError as exc:
        print(f"Scenario error: {exc}", file=sys.stderr)
        return EXIT_USAGE

    symbols = ps.load_symbols(args.manifest, args.noi, args.map)

    results = []
    for scenario in scenarios:
        out_dir = os.path.join(args.out_dir, scenario["name"])
        os.makedirs(out_dir, exist_ok=True)
        rebase_screenshots(scenario["steps"], out_dir)
        ctx, failure = run_one(args.rom, scenario, args, symbols, manifest, out_dir)
        divergence, verdict = None, None

        if args.ref_rom:
            if not os.path.exists(args.ref_rom):
                print(f"Reference ROM not found: {args.ref_rom}", file=sys.stderr)
                return EXIT_USAGE
            ref_ctx, ref_failure = run_one(args.ref_rom, scenario, args, symbols,
                                           manifest, out_dir, tag="-ref")
            divergence = ps.diff_traces(ctx.trace, ref_ctx.trace)
            if failure is not None and ref_failure is not None:
                verdict = "scenario-invalid"

        result = build_result(scenario["name"], ctx, failure=failure,
                              divergence=divergence, verdict=verdict,
                              blocking=scenario["blocking"])
        results.append(result)
        _report(result, args.as_json)
        if failure is not None and not scenario["blocking"] \
                and result["verdict"] != "scenario-invalid":
            print(f"    WARN: non-blocking scenario {scenario['name']} failed "
                  f"— reported as evidence, not gating.")
        with open(os.path.join(out_dir, "results.json"), "w") as f:
            json.dump(result, f, indent=2)

    if args.all:
        write_combined_results(results, args.out_dir)
    return resolve_exit_code(results)


if __name__ == "__main__":
    sys.exit(main())
