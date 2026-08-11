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

# A .noi flat address is `bank << 16 | gb_addr` — the rule in
# tools/bank_post_build.py:25.
BANK_STRIDE = 0x10000

# `StateEntry` in src/state_manager.c is one uint8_t bank followed by three
# function pointers. SDCC packs structs on SM83, so the stride is 1 + 3*2.
# The bank byte sits at offset 0 of each entry. Measured on a real debug
# build: _stack 0xC176, _sm_slot_src 0xC184 — 14 bytes for STACK_MAX 2.
STATE_ENTRY_STRIDE = 7
# `sm_slot_src` is an array of `const State *` — two bytes per slot.
STATE_PTR_WIDTH = 2

# A Game Boy background tile is 8 px. The car is 16 px on each side, so it
# stops 16 px short of the far edge — the rule in src/vehicle_physics.c, and
# the one tools/emit_manifest.py uses for `drive_limits`.
TILE_PX = 8
CAR_SIZE_PX = 16

# The largest distance the car can move in one frame: TERRAIN_BOOST_MAX_SPEED
# in src/config.h, the boost-pad cap. `vehicle_step_axis_*` rejects a move that
# would cross a drive limit and keeps the old position, so a car pressed
# against a limit parks strictly less than one step short of it — almost never
# exactly on it. An equality test therefore misses the case this block exists
# to explain (#589, found by the AC4 evidence run).
MAX_STEP_PX = 8

_STATE_OBJ_RE = re.compile(r'^_state_(\w+)$')
_STATE_BANK_PREFIX = '___bank_state_'


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
        # Filled by run() at raise time: the state, the car and the hint that
        # explain this failure (R11-R13).
        self.context = None


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


def parse_noi_all(path):
    """Every DEF line as `{name: flat address}`. No mask, no range filter.

    `_parse_noi` keeps WRAM only, which drops every banked-ROM symbol. The
    state objects live in ROM, so they need the unfiltered view.
    """
    out = {}
    if not path:
        return out
    try:
        with open(path) as f:
            for line in f:
                m = _NOI_RE.match(line.strip())
                if m:
                    out[m.group(1)] = int(m.group(2), 16)
    except OSError:
        pass
    return out


def load_state_table(noi_path):
    """`{short state name: (bank, gb_addr)}` for every `const State` object.

    A name qualifies only when a `___bank_state_<name>` symbol exists AND its
    value equals `flat >> 16`. That pair separates a state object from a
    state-manager function: `_state_push` and `_state_results_set_earned` both
    start with `_state_`, and neither has a companion bank symbol.
    """
    defs = parse_noi_all(noi_path)
    table = {}
    for name, flat in defs.items():
        m = _STATE_OBJ_RE.match(name)
        if not m:
            continue
        bank = flat // BANK_STRIDE
        if defs.get(_STATE_BANK_PREFIX + m.group(1)) != bank:
            continue
        table[m.group(1)] = (bank, flat % BANK_STRIDE)
    return table


def normalize_state_name(name):
    """`_state_playing`, `state_playing` and `playing` all name one state."""
    text = str(name)
    for prefix in ('_state_', 'state_'):
        if text.startswith(prefix):
            return text[len(prefix):]
    return text


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


def load_symbols(manifest_path=None, noi_path=None, map_path=None,
                 debug_noi_path=None):
    """Merge symbol sources, lowest priority first:
    .map -> debug .noi -> .noi -> manifest.

    The debug symbol file is a strict superset built from the same bytes
    (tests/test_rom_parity.py). It sits below the release .noi so a release
    address always wins, and it is what makes the `static` state-machine
    variables readable. `_parse_noi` swallows OSError, so a missing file
    contributes nothing and raises nothing.
    """
    symbols = {}
    symbols.update(_parse_map(map_path))
    symbols.update(_parse_noi(debug_noi_path))
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
    "assert_memory", "assert_live", "assert_changes",
    "assert_screen_changes", "assert_state", "wait_state", "nav",
}

REQUIRE_KEYS = {"state", "address", "value", "op", "width"}

# Actions whose `state` field names a state.
STATE_FIELD_ACTIONS = ("assert_state", "wait_state")

# action -> required field names
_REQUIRED = {
    "advance":               ("frames",),
    "press":                 ("buttons",),
    "wait_memory":           ("address", "value"),
    "screenshot":            (),
    "assert_memory":         ("address", "value"),
    "assert_live":           (),
    "assert_changes":        ("symbols",),
    "assert_screen_changes": (),
    "assert_state":          ("state",),
    "wait_state":            ("state",),
    "nav":                   ("to", "id"),
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
        if "require" in step:
            raise ScenarioError(
                "include step cannot carry a 'require' field — the include is "
                "inlined at load time and the field would be discarded. Put "
                "the 'require' on the first step after the include instead.")
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


def _validate_require(i, req):
    if not isinstance(req, dict):
        raise ScenarioError(
            f"Step {i}: 'require' must be an object, got {type(req).__name__}")
    extra = sorted(set(req) - REQUIRE_KEYS)
    if extra:
        raise ScenarioError(f"Step {i}: 'require' has unknown field(s) {extra}")
    if "state" not in req and "address" not in req:
        raise ScenarioError(f"Step {i}: 'require' needs a 'state' or an 'address'")
    if "address" in req and "value" not in req:
        raise ScenarioError(f"Step {i}: 'require' with an 'address' needs a 'value'")
    if "op" in req and req["op"] not in _OPS:
        raise ScenarioError(f"Step {i}: unknown operator {req['op']!r}")


def _validate(steps, state_names=None):
    for i, step in enumerate(steps):
        act = step.get("action")
        if act not in KNOWN_ACTIONS:
            raise ScenarioError(f"Step {i}: unknown action {act!r}")
        for field in _REQUIRED[act]:
            if field not in step:
                raise ScenarioError(f"Step {i}: action {act!r} requires field {field!r}")
        if "require" in step:
            _validate_require(i, step["require"])
        if state_names is None:
            continue
        wanted = []
        req = step.get("require")
        if isinstance(req, dict) and "state" in req:
            wanted.append(req["state"])
        if act in STATE_FIELD_ACTIONS and "state" in step:
            wanted.append(step["state"])
        for name in wanted:
            if normalize_state_name(name) not in state_names:
                known = ', '.join(sorted(state_names)) or '(none loaded)'
                raise ScenarioError(
                    f"Step {i}: unknown state {name!r} (known: {known})")


def load_scenario(src, library_dir=None, state_names=None):
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
    _validate(sc["steps"], state_names)
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
                 freeze_frames=0, default_out=None, widths=None,
                 state_table=None):
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

        self.state_table = dict(state_table or {})
        self._state_by_bank_addr = {(b, a): n
                                    for n, (b, a) in self.state_table.items()}
        self._state_by_addr = {}
        for n, (b, a) in self.state_table.items():
            self._state_by_addr.setdefault(a, []).append(n)
        self.state = None
        self.state_at_start = None
        self.state_changes = []

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
            "state": self.state,
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
        watching = self.state_readable()
        if not sampling and not render_all and not watching:
            # Fast path: no trace, no watchdog, no state (screenshot.py).
            if n > 1:
                emu.tick(n - 1, render=False)
            emu.tick(1, render=render_last)
            self.frame += n
            return
        for _ in range(n):
            self.frame += 1
            due = sampling and (self.frame % self.trace_every == 0)
            emu.tick(1, render=bool(due or render_all))
            self.observe_state(emu)
            if due:
                self.sample(emu)

    def capture(self, emu, path):
        emu.tick(1, render=True)
        self.frame += 1
        emu.screen.image.save(path)
        self.screenshots.append(path)

    # --- state ------------------------------------------------------------
    def state_readable(self):
        """True when a state table AND the debug symbols are both present."""
        return bool(self.state_table) and all(
            name in self.symbols for name in ('_sm_depth', '_sm_slot_src'))

    def read_state(self, emu):
        """The name of the state on top of the stack, or None.

        `sm_slot_src[depth-1]` holds the address of the `const State` object
        and `stack[depth-1].bank` holds its bank. The pair identifies the
        state. A unique address answers on its own, so a wrong bank byte
        degrades to the address match instead of naming the wrong state.
        """
        if not self.state_readable():
            return None
        depth = emu.memory[self.symbols['_sm_depth']]
        if depth == 0:
            return None
        slot = depth - 1
        ptr = read_value(
            emu, self.symbols['_sm_slot_src'] + STATE_PTR_WIDTH * slot, 2)
        stack = self.symbols.get('_stack')
        if stack is not None:
            bank = emu.memory[stack + STATE_ENTRY_STRIDE * slot]
            name = self._state_by_bank_addr.get((bank, ptr))
            if name is not None:
                return name
        names = self._state_by_addr.get(ptr, [])
        return names[0] if len(names) == 1 else None

    def begin_action(self, emu):
        """Reset the per-action state record. Called once per step."""
        self.state_changes = []
        self.state = self.read_state(emu)
        self.state_at_start = self.state

    def observe_state(self, emu):
        """Sample the state and record a change. Four reads per frame."""
        if not self.state_readable():
            return None
        now = self.read_state(emu)
        if now != self.state:
            self.state_changes.append(
                {"frame": self.frame, "from": self.state, "to": now})
            self.state = now
        return now

    # --- failure context --------------------------------------------------
    def car_position(self, emu):
        """The car in pixels and in tiles, or None when the symbols are absent."""
        if '_px' not in self.symbols or '_py' not in self.symbols:
            return None
        px = read_value(emu, self.symbols['_px'], self.width_of('_px'))
        py = read_value(emu, self.symbols['_py'], self.width_of('_py'))
        return {"px": px, "py": py, "tx": px // TILE_PX, "ty": py // TILE_PX}

    def drive_limits(self, emu):
        """The clamp the game applies to the car during a race, or None.

        The live map size is the first source: `_active_map_w` and
        `_active_map_h` are plain globals, they reach the release symbol file,
        and they describe the map the game actually loaded. The manifest track
        block is the fallback.
        """
        if '_active_map_w' in self.symbols and '_active_map_h' in self.symbols:
            w = emu.memory[self.symbols['_active_map_w']]
            h = emu.memory[self.symbols['_active_map_h']]
            return {"x_min": 0, "x_max": w * TILE_PX - CAR_SIZE_PX,
                    "y_min": 0, "y_max": h * TILE_PX - CAR_SIZE_PX,
                    "source": "wram"}
        tracks = (self.manifest or {}).get("tracks") or {}
        if '_current_race_id' in self.symbols:
            track = tracks.get(str(emu.memory[self.symbols['_current_race_id']]))
            limits = (track or {}).get("drive_limits")
            if limits:
                out = dict(limits)
                out["source"] = "manifest"
                return out
        return None

    def at_limit(self, car, limits):
        """Which clamps the car is pressed against.

        Within one frame of movement counts as 'at': see MAX_STEP_PX.
        """
        if not car or not limits:
            return []
        hits = []
        for axis, value in (("x", car["px"]), ("y", car["py"])):
            for edge in ("min", "max"):
                key = f"{axis}_{edge}"
                if key in limits and abs(value - limits[key]) < MAX_STEP_PX:
                    hits.append(key)
        return hits

    def hint(self, failure, block):
        """One sentence naming the most probable cause (R13)."""
        changes = block["state_changes"]
        if changes:
            first, last = changes[0], changes[-1]
            return (f"the game left _state_{first['from']} for "
                    f"_state_{last['to']} at frame {first['frame']}, so the "
                    f"action ran across a state change")
        if failure.kind == "precondition":
            return ("the scenario ran an action whose precondition is false, "
                    "so the scenario is wrong, not the game")
        if (failure.kind in ("stale-symbol", "freeze")
                and block["state_at_failure"] not in ("playing", None)):
            return (f"the game is in _state_{block['state_at_failure']}, not "
                    f"racing, so a race symbol stops for a correct reason")
        if block["at_limit"] and failure.kind in ("stale-symbol", "freeze"):
            return (f"the car is at the {', '.join(block['at_limit'])} drive "
                    f"limit, so it cannot move on that axis")
        if failure.kind == "stale-screen":
            return "the screen did not change, so the game may be on a static screen"
        if failure.kind == "state":
            return (f"the game is in _state_{block['state_at_failure']}, "
                    f"not the state the scenario expects")
        return "no state change and no drive limit explains this failure"

    def failure_context(self, emu, failure):
        """The `context` block on a failure record (R11-R13)."""
        state_now = self.read_state(emu)
        block = {
            "state_at_start":   self.state_at_start,
            "state_at_failure": state_now,
            "state_changes":    list(self.state_changes),
            "car":              None,
            "drive_limits":     None,
            "at_limit":         [],
        }
        # R12 applies when the state held still. `state_now is None` covers a
        # run with no debug symbols, where the state cannot be read at all.
        if not block["state_changes"] and state_now in ("playing", None):
            block["car"] = self.car_position(emu)
            block["drive_limits"] = self.drive_limits(emu)
            block["at_limit"] = self.at_limit(block["car"],
                                              block["drive_limits"])
        block["hint"] = self.hint(failure, block)
        return block


def press(emu, ctx, buttons, delay=1):
    """Canonical press: one rendered frame first (KEY_TICKED), all buttons
    queued together (simultaneous), then held for `delay` frames."""
    emu.tick(1, render=True)
    ctx.frame += 1
    ctx.observe_state(emu)
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


def check_require(emu, step, ctx, i):
    """Evaluate a step's `require` field BEFORE the step runs.

    A false requirement is a defect in the scenario, not in the game, so it
    raises the kind `precondition`, which the harness maps to the verdict
    `scenario-invalid` (R3).
    """
    req = step.get("require")
    if not req:
        return
    act = step.get("action")
    if "state" in req:
        want = normalize_state_name(req["state"])
        actual = ctx.read_state(emu)
        if actual != want:
            raise StepFailure(
                i, "precondition",
                f"require state {want!r}, the game is in {actual!r}", act)
    if "address" in req:
        name = req["address"]
        addr = resolve(name, ctx.symbols)
        width = int(req.get(
            "width", ctx.width_of(name) if isinstance(name, str) else 1))
        actual = read_value(emu, addr, width)
        target = int(req["value"])
        if not _cmp(req, actual, target):
            raise StepFailure(
                i, "precondition",
                f"require {name} {req.get('op', 'eq')} {target}, it is {actual}",
                act)


def validate_state_support(steps, state_readable):
    """Reject a scenario that needs the state reader when it is unavailable.

    Raised before frame 0, as a usage error: the run cannot answer the
    question the scenario asks (R14).
    """
    if state_readable:
        return
    for i, step in enumerate(steps):
        req = step.get("require") or {}
        if step.get("action") in STATE_FIELD_ACTIONS or "state" in req:
            raise ScenarioError(
                f"Step {i}: action {step.get('action')!r} needs the game state, "
                "and the state-machine symbols are missing. They live in the "
                "debug symbol file only. Run 'make build-debug', then pass "
                "--debug-noi build/debug/nuke-raider.noi")


def run(emu, steps, ctx):
    """Execute a flat step list. Raises StepFailure; never calls sys.exit."""
    for i, step in enumerate(steps):
        ctx.step = i
        ctx.action = step.get("action")
        ctx.begin_action(emu)
        try:
            check_require(emu, step, ctx, i)
            _dispatch(emu, step, ctx, i)
        except StepFailure as exc:
            exc.context = ctx.failure_context(emu, exc)
            raise
    return ctx


def _liveness(emu, ctx, step, i, want_symbols, want_screen):
    """The body behind assert_live, assert_changes and assert_screen_changes.

    The two failures are separate kinds on purpose: a symbol that does not
    move and a screen that does not move have different causes and different
    fixes (R9).
    """
    act = step.get("action")
    frames = int(step.get("frames", 60))
    names = list(step.get("symbols", [])) if want_symbols else []
    addrs = {n: (resolve(n, ctx.symbols), ctx.width_of(n)) for n in names}
    start = {n: read_value(emu, a, w) for n, (a, w) in addrs.items()}
    changed, hashes = set(), set()
    for _ in range(frames):
        ctx.tick(emu, 1, render_all=True)
        hashes.add(ctx.screen_hash(emu))
        for n, (a, w) in addrs.items():
            if read_value(emu, a, w) != start[n]:
                changed.add(n)
    stale = [n for n in names if n not in changed]
    if stale:
        raise StepFailure(
            i, "stale-symbol",
            f"{', '.join(stale)} did not change over {frames} frames", act)
    if want_screen and len(hashes) < 2:
        raise StepFailure(
            i, "stale-screen",
            f"the screen did not change over {frames} frames", act)


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

    elif act == "assert_memory":
        addr, width = _addr_and_width(ctx, step)
        target = int(step["value"])
        actual = read_value(emu, addr, width)
        if not _cmp(step, actual, target):
            raise StepFailure(
                i, "assert",
                f"{step['address']} is {actual}, expected "
                f"{step.get('op', 'eq')} {target}", act)

    elif act == "assert_live":
        _liveness(emu, ctx, step, i, True, bool(step.get("screen", True)))

    elif act == "assert_changes":
        _liveness(emu, ctx, step, i, True, False)

    elif act == "assert_screen_changes":
        _liveness(emu, ctx, step, i, False, True)

    elif act == "assert_state":
        want = normalize_state_name(step["state"])
        actual = ctx.read_state(emu)
        if actual != want:
            raise StepFailure(
                i, "state",
                f"expected state {want!r}, the game is in {actual!r}", act)

    elif act == "wait_state":
        want = normalize_state_name(step["state"])
        max_f = int(step.get("max_frames", 600))
        for _ in range(max_f):
            if ctx.read_state(emu) == want:
                return
            ctx.tick(emu, 1)
        raise StepFailure(
            i, "timeout",
            f"wait_state timed out after {max_f} frames "
            f"(want {want!r}, the game is in {ctx.read_state(emu)!r})", act)

    elif act == "nav":
        nav = ctx.manifest.get("navigation")
        if not nav:
            raise ScenarioError(
                "nav step requires build/game-manifest.json "
                "(run 'make' to generate it)")
        key = {"track": "overmap_to_track", "hub": "overmap_to_hub"}.get(step["to"])
        if key is None:
            raise ScenarioError(f"nav 'to' must be 'track' or 'hub', got {step['to']!r}")
        table = nav.get(key, {})
        dirs = table.get(str(step["id"]))
        if dirs is None:
            raise ScenarioError(f"No manifest path for {step['to']} {step['id']!r}")
        per_tile = int(nav.get("travel_frames_per_tile", 4))
        settle = int(step.get("settle", per_tile))
        for direction in dirs:
            press(emu, ctx, [direction], per_tile)
            ctx.tick(emu, settle)

    else:
        raise ScenarioError(f"Step {i}: unhandled action {act!r}")


def _group_by_step(trace):
    grouped = {}
    for rec in trace:
        grouped.setdefault(rec["step"], []).append(rec)
    return grouped


def diff_traces(main, ref):
    """Step-anchored comparison of two WRAM traces.

    Both runs execute the same flat step list, so step indices always
    correspond even when timing shifts inside a step. Returns the first
    divergence, or None when the traces agree.
    """
    ga, gb = _group_by_step(main), _group_by_step(ref)
    for step in sorted(set(ga) | set(gb)):
        ra, rb = ga.get(step, []), gb.get(step, [])
        for i in range(min(len(ra), len(rb))):
            shared = sorted(set(ra[i]["values"]) & set(rb[i]["values"]))
            for sym in shared:
                if ra[i]["values"][sym] != rb[i]["values"][sym]:
                    return {"step": step, "action": ra[i]["action"],
                            "frame": ra[i]["frame"], "symbol": sym,
                            "main": ra[i]["values"][sym],
                            "ref":  rb[i]["values"][sym]}
        if len(ra) != len(rb):
            anchor = (ra or rb)[-1]
            return {"step": step, "action": anchor["action"],
                    "frame": anchor["frame"], "symbol": "__sample_count__",
                    "main": len(ra), "ref": len(rb)}
    return None
