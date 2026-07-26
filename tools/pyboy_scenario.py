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

import hashlib
import json
import os
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


MAX_INCLUDE_DEPTH = 8

KNOWN_ACTIONS = {
    "advance", "press", "wait_memory", "screenshot",
    "assert_memory", "assert_live", "nav",
}

# action -> required field names
_REQUIRED = {
    "advance":       ("frames",),
    "press":         ("buttons",),
    "wait_memory":   ("address", "value"),
    "screenshot":    (),
    "assert_memory": ("address", "value"),
    "assert_live":   (),
    "nav":           ("to", "id"),
}


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except OSError as exc:
        raise ScenarioError(f"Cannot read scenario {path!r}: {exc}") from exc
    except ValueError as exc:
        raise ScenarioError(f"Malformed JSON in {path!r}: {exc}") from exc


def _as_dict(obj, name):
    if isinstance(obj, list):
        return {"name": name, "blocking": True, "watch": [], "steps": obj}
    if isinstance(obj, dict):
        steps = obj.get("steps")
        if not isinstance(steps, list):
            raise ScenarioError(f"Scenario {name!r} has no 'steps' array")
        return {
            "name":     obj.get("name", name),
            "blocking": bool(obj.get("blocking", True)),
            "watch":    list(obj.get("watch", [])),
            "steps":    steps,
        }
    raise ScenarioError(f"Scenario {name!r} must be a JSON array or object")


def _inline(steps, library_dir, stack, depth):
    if depth > MAX_INCLUDE_DEPTH:
        raise ScenarioError(f"Include depth exceeded {MAX_INCLUDE_DEPTH}: {' -> '.join(stack)}")
    out = []
    for step in steps:
        if not isinstance(step, dict):
            raise ScenarioError(f"Step must be an object, got {type(step).__name__}")
        if step.get("action") != "include":
            out.append(step)
            continue
        name = step.get("name")
        if not name:
            raise ScenarioError("include step requires a 'name'")
        if name in stack:
            raise ScenarioError(f"Include cycle: {' -> '.join(stack + [name])}")
        if not library_dir:
            raise ScenarioError(f"include {name!r} requires a scenario library directory")
        path = os.path.join(library_dir, name + ".json")
        if not os.path.exists(path):
            raise ScenarioError(f"Unknown scenario snippet: {name!r} (looked in {library_dir})")
        inner = _as_dict(_read_json(path), name)
        out.extend(_inline(inner["steps"], library_dir, stack + [name], depth + 1))
    return out


def _validate(steps):
    for i, step in enumerate(steps):
        act = step.get("action")
        if act not in KNOWN_ACTIONS:
            raise ScenarioError(f"Step {i}: unknown action {act!r}")
        for field in _REQUIRED[act]:
            if field not in step:
                raise ScenarioError(f"Step {i}: action {act!r} requires field {field!r}")


def load_scenario(src, library_dir=None):
    """Parse a scenario, inline its includes, and validate it.

    src may be a path, a bare step list, or a scenario dict.
    Includes are inlined at load time, so the returned step list is flat.
    """
    if isinstance(src, str):
        name = os.path.splitext(os.path.basename(src))[0]
        obj = _read_json(src)
    else:
        name = "inline"
        obj = src
    sc = _as_dict(obj, name)
    sc["steps"] = _inline(sc["steps"], library_dir, [sc["name"]], 1)
    _validate(sc["steps"])
    return sc


_OPS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b,
}


class RunContext:
    """Frame counter, trace sampler, and freeze watchdog for one run.

    The trace sampler doubles as the render heartbeat: when trace_every is
    non-zero the engine renders at every sample point, which is what gives
    the freeze watchdog a stream of frames to compare.
    """

    def __init__(self, symbols, manifest=None, watch=None, trace_every=0,
                 freeze_frames=0, default_out=None, widths=None):
        self.symbols = symbols
        self.manifest = manifest or {}
        self.watch = list(watch or [])
        self.trace_every = int(trace_every)
        self.freeze_frames = int(freeze_frames)
        self.default_out = default_out
        self.widths = dict(DEFAULT_WIDTHS)
        self.widths.update(widths or {})

        self.frame = 0
        self.step = -1
        self.action = None
        self.trace = []
        self.screenshots = []
        self._last_hash = None
        self._unchanged = 0

    # --- helpers ---------------------------------------------------------
    def screen_hash(self, emu):
        return hashlib.sha1(emu.screen.image.tobytes()).hexdigest()[:16]

    def width_of(self, name):
        return self.widths.get(name, 1)

    def sample(self, emu):
        values = {}
        for name in self.watch:
            addr = self.symbols.get(name)
            if addr is None:
                continue
            values[name] = read_value(emu, addr, self.width_of(name))
        digest = self.screen_hash(emu)
        self.trace.append({
            "frame": self.frame, "step": self.step, "action": self.action,
            "values": values, "screen_hash": digest,
        })
        if digest == self._last_hash:
            self._unchanged += self.trace_every
        else:
            self._unchanged = 0
        self._last_hash = digest
        if self.freeze_frames and self._unchanged >= self.freeze_frames:
            raise StepFailure(
                self.step, "freeze",
                f"screen unchanged for {self._unchanged} frames "
                f"(threshold {self.freeze_frames})", self.action)

    def tick(self, emu, n, render_all=False, render_last=False):
        """Advance n frames, rendering at sample points (and sampling there)."""
        n = int(n)
        if n <= 0:
            return
        sampling = self.trace_every > 0
        if not sampling and not render_all:
            # Fast path: no trace, no watchdog (screenshot.py's default).
            if n > 1:
                emu.tick(n - 1, render=False)
            emu.tick(1, render=render_last)
            self.frame += n
            return
        for _ in range(n):
            self.frame += 1
            due = sampling and (self.frame % self.trace_every == 0)
            emu.tick(1, render=bool(due or render_all))
            if due:
                self.sample(emu)

    def capture(self, emu, path):
        emu.tick(1, render=True)
        self.frame += 1
        emu.screen.image.save(path)
        self.screenshots.append(path)


def press(emu, ctx, buttons, delay=1):
    """Canonical press: one rendered frame first (KEY_TICKED), all buttons
    queued together (simultaneous), then held for `delay` frames."""
    emu.tick(1, render=True)
    ctx.frame += 1
    for btn in buttons:
        emu.button(str(btn).lower(), int(delay))
    ctx.tick(emu, int(delay))


def _cmp(step, actual, target):
    op = step.get("op", "eq")
    if op not in _OPS:
        raise ScenarioError(f"Unknown operator {op!r}")
    return _OPS[op](actual, target)


def _addr_and_width(ctx, step):
    name = step["address"]
    addr = resolve(name, ctx.symbols)
    width = int(step.get("width", ctx.width_of(name) if isinstance(name, str) else 1))
    return addr, width


def run(emu, steps, ctx):
    """Execute a flat step list. Raises StepFailure; never calls sys.exit."""
    for i, step in enumerate(steps):
        ctx.step = i
        ctx.action = step.get("action")
        _dispatch(emu, step, ctx, i)
    return ctx


def _dispatch(emu, step, ctx, i):
    act = step.get("action")

    if act == "advance":
        ctx.tick(emu, step["frames"], render_last=True)

    elif act == "press":
        press(emu, ctx, step["buttons"], step.get("delay", 1))

    elif act == "wait_memory":
        addr, width = _addr_and_width(ctx, step)
        target = int(step["value"])
        max_f = int(step.get("max_frames", 600))
        for _ in range(max_f):
            if _cmp(step, read_value(emu, addr, width), target):
                return
            ctx.tick(emu, 1)
        raise StepFailure(
            i, "timeout",
            f"wait_memory timed out after {max_f} frames "
            f"(addr={hex(addr)}, got={read_value(emu, addr, width)}, "
            f"want {step.get('op', 'eq')} {target})", act)

    elif act == "screenshot":
        ctx.capture(emu, step.get("out", ctx.default_out))

    else:
        raise ScenarioError(f"Step {i}: unhandled action {act!r}")
