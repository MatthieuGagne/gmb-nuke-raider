#!/usr/bin/env python3
"""Headless Game Boy screenshot capture.

Boots the ROM via PyBoy (headless), runs a navigation sequence, saves a PNG.
Run from the repo root or any worktree root — paths resolve relative to this
script's location so it works identically from main tree and worktrees.

Usage:
    python3 tools/screenshot.py [--steps JSON] [--steps-file FILE] [--out PATH] [--rom PATH]

Navigation step types (JSON array):
  {"action": "advance",       "frames": N}
  {"action": "press",         "buttons": ["start"], "delay": 1}
  {"action": "wait_memory",   "address": "0xC000" | "_symbol", "value": N, "max_frames": 600}
  {"action": "screenshot",    "out": "/tmp/mid.png"}
  {"action": "assert_memory", "address": "_hp", "value": 0, "op": "gt"}
  {"action": "assert_live",   "symbols": ["_px"], "frames": 60}
  {"action": "nav",           "to": "track", "id": 1}
  {"action": "include",       "name": "reach-race"}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Put tools/ first only long enough to import our own module, then restore
# sys.path. Leaving it in front lets any tools/*.py shadow a stdlib module of
# the same name for everything imported afterwards (tools/trace.py would
# otherwise shadow stdlib `trace`).
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _TOOLS_DIR)
import pyboy_scenario as ps
sys.path.remove(_TOOLS_DIR)


def _exit(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)


try:
    from pyboy import PyBoy
except ImportError:
    _exit("PyBoy not found. Run: pip install -r requirements.txt")


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).parent.parent
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--rom",        default=str(root / "build" / "nuke-raider.gb"))
    p.add_argument("--map",        default=str(root / "build" / "nuke-raider.map"))
    p.add_argument("--out",        default=str(root / "build" / "screenshot.png"))
    p.add_argument("--steps",      default="[]")
    p.add_argument("--steps-file", default=None)
    p.add_argument("--noi",        default=str(root / "build" / "nuke-raider.noi"))
    p.add_argument("--manifest",   default=str(root / "build" / "game-manifest.json"))
    p.add_argument("--library",    default=str(root / "tools" / "scenarios"))
    return p


def main() -> None:
    args = build_parser().parse_args()

    if not os.path.exists(args.rom):
        _exit(f"ROM not found: {args.rom}  (build first with 'make')")

    src = args.steps_file if args.steps_file else json.loads(args.steps)
    try:
        scenario = ps.load_scenario(src, library_dir=args.library)
    except ps.ScenarioError as exc:
        _exit(f"Scenario error: {exc}")

    symbols = ps.load_symbols(args.manifest, args.noi, args.map)
    manifest = {}
    if os.path.exists(args.manifest):
        with open(args.manifest) as f:
            manifest = json.load(f)

    ctx = ps.RunContext(symbols=symbols, manifest=manifest, default_out=args.out)
    pyboy = PyBoy(args.rom, window="null", sound_emulated=False)
    try:
        ps.run(pyboy, scenario["steps"], ctx)
        ctx.capture(pyboy, args.out)
        print(f"Screenshot: {args.out}")
    except ps.StepFailure as exc:
        out = args.out
        try:
            ctx.capture(pyboy, out)
            print(f"Screenshot: {out}")
        except Exception:
            pass
        _exit(f"Step {exc.step}: {exc.message}. Screenshot saved to {out}")
    except ps.ScenarioError as exc:
        _exit(f"Scenario error: {exc}")
    except Exception as exc:
        print(f"PyBoy error: {exc}", file=sys.stderr)
        try:
            ctx.capture(pyboy, args.out)
            print("Screenshot saved (crash state).", file=sys.stderr)
        except Exception:
            pass
        sys.exit(1)
    finally:
        pyboy.stop()


if __name__ == "__main__":
    main()
