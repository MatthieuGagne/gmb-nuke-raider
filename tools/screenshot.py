#!/usr/bin/env python3
"""Headless Game Boy screenshot capture.

Boots the ROM via PyBoy (headless), runs a navigation sequence, saves a PNG.
Run from the repo root or any worktree root — paths resolve relative to this
script's location so it works identically from main tree and worktrees.

Usage:
    python3 tools/screenshot.py [--steps JSON] [--steps-file FILE] [--out PATH] [--rom PATH]

Navigation step types (JSON array):
  {"action": "advance",     "frames": N}
  {"action": "press",       "buttons": ["start"], "delay": 1}
  {"action": "wait_memory", "address": "0xC000" | "_symbol", "value": N, "max_frames": 600}
  {"action": "screenshot",  "out": "/tmp/mid.png"}
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def _exit(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(1)


try:
    from pyboy import PyBoy
except ImportError:
    _exit("PyBoy not found. Run: pip install -r requirements.txt")


def _load_symbols(map_path: str) -> dict:
    symbols: dict = {}
    pat = re.compile(r'([0-9A-Fa-f]{8})\s+(_\w+)')
    try:
        with open(map_path) as f:
            for line in f:
                for m in pat.finditer(line):
                    symbols[m.group(2)] = int(m.group(1), 16) & 0xFFFF
    except FileNotFoundError:
        pass
    return symbols


def _resolve(addr: str, symbols: dict) -> int:
    if addr.startswith(('0x', '0X')):
        return int(addr, 16)
    if addr in symbols:
        return symbols[addr]
    raise ValueError(f"Unknown symbol: {addr!r}")


def _capture(pyboy, path: str) -> None:
    pyboy.tick(1, render=True)
    pyboy.screen.image.save(path)
    print(f"Screenshot: {path}")


def _run(pyboy, steps: list, symbols: dict, default_out: str) -> None:
    for i, step in enumerate(steps):
        act = step.get("action", "")

        if act == "advance":
            n = int(step["frames"])
            if n > 1:
                pyboy.tick(n - 1, render=False)
            if n > 0:
                pyboy.tick(1, render=True)

        elif act == "press":
            delay = int(step.get("delay", 1))
            for btn in step["buttons"]:
                pyboy.button(btn.lower(), delay)
            pyboy.tick(delay, render=False)
            pyboy.tick(1, render=True)

        elif act == "wait_memory":
            addr = _resolve(step["address"], symbols)
            target = int(step["value"])
            max_f = int(step.get("max_frames", 600))
            for _ in range(max_f):
                if pyboy.memory[addr] == target:
                    break
                pyboy.tick(1, render=False)
            else:
                out = step.get("out", default_out)
                _capture(pyboy, out)
                _exit(
                    f"Step {i}: wait_memory timed out after {max_f} frames "
                    f"(addr={hex(addr)}, got={pyboy.memory[addr]}, want={target}). "
                    f"Screenshot saved to {out}"
                )
            pyboy.tick(1, render=True)

        elif act == "screenshot":
            _capture(pyboy, step.get("out", default_out))

        else:
            print(f"Step {i}: unknown action {act!r}, skipping.", file=sys.stderr)


def main() -> None:
    root = Path(__file__).parent.parent
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--rom",        default=str(root / "build" / "nuke-raider.gb"))
    parser.add_argument("--map",        default=str(root / "build" / "nuke-raider.map"))
    parser.add_argument("--out",        default="/tmp/nuke-raider-screenshot.png")
    parser.add_argument("--steps",      default="[]")
    parser.add_argument("--steps-file", default=None)
    args = parser.parse_args()

    if not os.path.exists(args.rom):
        _exit(f"ROM not found: {args.rom}  (build first with 'make')")

    steps = json.load(open(args.steps_file)) if args.steps_file else json.loads(args.steps)
    symbols = _load_symbols(args.map)

    pyboy = PyBoy(args.rom, window="null", sound_emulated=False)
    try:
        _run(pyboy, steps, symbols, args.out)
        _capture(pyboy, args.out)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"PyBoy error: {exc}", file=sys.stderr)
        try:
            _capture(pyboy, args.out)
            print("Screenshot saved (crash state).", file=sys.stderr)
        except Exception:
            pass
        sys.exit(1)
    finally:
        pyboy.stop()


if __name__ == "__main__":
    main()
