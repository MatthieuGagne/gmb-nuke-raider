#!/usr/bin/env python3
"""Shared PyBoy scenario engine.

Owns symbol resolution, scenario loading/composition, and step execution
against an *injected* emulator. Never constructs PyBoy. Never calls sys.exit.

Emulator contract (duck-typed, satisfied by PyBoy and by tests' FakeEmu):
    emu.tick(n, render=bool)
    emu.memory[addr] -> int
    emu.button(name, delay)
    emu.screen.image  -> object with .save(path) and .tobytes()
"""
from __future__ import annotations

import json
import re

# _px / _py are little-endian 16-bit words; every other sentinel is one byte.
DEFAULT_WIDTHS = {"_px": 2, "_py": 2}

_NOI_RE = re.compile(r'^DEF\s+(_\w+)\s+(0x[0-9A-Fa-f]+)')
_MAP_RE = re.compile(r'([0-9A-Fa-f]{8})\s+(_\w+)')

WRAM_LO, WRAM_HI = 0xC000, 0xDFFF


class ScenarioError(Exception):
    """Malformed scenario, unknown symbol, or unresolvable include (usage error)."""


class StepFailure(Exception):
    """A step's assertion, timeout, or watchdog fired (run outcome)."""

    def __init__(self, step, kind, message, action=None):
        super().__init__(message)
        self.step = step
        self.kind = kind
        self.message = message
        self.action = action


def _parse_map(path):
    """Parse .map. NOTE: names are truncated to 9 chars in this format."""
    out = {}
    if not path:
        return out
    try:
        with open(path) as f:
            for line in f:
                for m in _MAP_RE.finditer(line):
                    out[m.group(2)] = int(m.group(1), 16) & 0xFFFF
    except OSError:
        pass
    return out


def _parse_noi(path):
    """Parse .noi DEF lines. Full symbol names; WRAM range only."""
    out = {}
    if not path:
        return out
    try:
        with open(path) as f:
            for line in f:
                m = _NOI_RE.match(line.strip())
                if not m:
                    continue
                addr = int(m.group(2), 16) & 0xFFFF
                if WRAM_LO <= addr <= WRAM_HI:
                    out[m.group(1)] = addr
    except OSError:
        pass
    return out


def _parse_manifest_symbols(path):
    out = {}
    if not path:
        return out
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return out
    for name, val in (data.get('symbols') or {}).items():
        if val is None:
            continue          # static, not promoted — resolved via .noi/.map instead
        out[name] = int(val, 16) & 0xFFFF if isinstance(val, str) else int(val) & 0xFFFF
    return out


def load_symbols(manifest_path=None, noi_path=None, map_path=None):
    """Merge symbol sources, lowest priority first: .map -> .noi -> manifest."""
    symbols = {}
    symbols.update(_parse_map(map_path))
    symbols.update(_parse_noi(noi_path))
    symbols.update(_parse_manifest_symbols(manifest_path))
    return symbols


def resolve(addr, symbols):
    """Resolve '0xC199' or '_hp' to an int address."""
    if isinstance(addr, int):
        return addr
    if addr.startswith(('0x', '0X')):
        return int(addr, 16)
    if addr in symbols:
        return symbols[addr]
    raise ScenarioError(f"Unknown symbol: {addr!r}")


def read_value(emu, addr, width=1):
    """Read a byte, or a little-endian word when width == 2."""
    if width == 2:
        return emu.memory[addr] | (emu.memory[addr + 1] << 8)
    return emu.memory[addr]
