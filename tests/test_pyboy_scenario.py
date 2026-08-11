"""Tests for tools/pyboy_scenario.py"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import pyboy_scenario as ps


class FakeScreen:
    def __init__(self, emu):
        self._emu = emu

    @property
    def image(self):
        return self._emu  # FakeEmu implements tobytes()/save()


class FakeEmu:
    """Minimal stand-in for PyBoy. Deterministic, no emulation."""

    def __init__(self, memory=None, frames=None):
        # memory: dict addr -> value, or dict addr -> list of values indexed by tick count
        self.memory = dict(memory or {})
        self.ticks = 0
        self.rendered = 0
        self.presses = []          # (button, delay, frame_at_press)
        self.render_log = []       # bool per tick
        self.saved = []
        self._frames = frames or []   # per-tick screen payload for hashing
        self.screen = FakeScreen(self)

    # --- PyBoy surface -------------------------------------------------
    def tick(self, n=1, render=False):
        for _ in range(int(n)):
            self.ticks += 1
            self.render_log.append(bool(render))
            if render:
                self.rendered += 1

    def button(self, name, delay=1):
        self.presses.append((name, delay, self.ticks))

    # --- screen.image surface -------------------------------------------
    def tobytes(self):
        if self._frames:
            return bytes(self._frames[min(self.ticks, len(self._frames) - 1)])
        return b'\x00'

    def save(self, path):
        self.saved.append(path)
        with open(path, 'wb') as f:
            f.write(self.tobytes())


def write(path, text):
    with open(path, 'w') as f:
        f.write(text)


class TestLoadSymbols(unittest.TestCase):

    def test_manifest_wins_over_noi_and_map(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = os.path.join(d, 'game-manifest.json')
            noi = os.path.join(d, 'rom.noi')
            mapf = os.path.join(d, 'rom.map')
            write(manifest, json.dumps({'symbols': {'_hp': '0xC4F2'}}))
            write(noi, 'DEF _hp 0xDEAD\n')
            write(mapf, '0000BEEF  _hp\n')
            syms = ps.load_symbols(manifest, noi, mapf)
            self.assertEqual(syms['_hp'], 0xC4F2)

    def test_noi_supplies_full_length_names_map_cannot(self):
        with tempfile.TemporaryDirectory() as d:
            noi = os.path.join(d, 'rom.noi')
            write(noi, 'DEF _active_lap_count 0xC2E5\nDEF _px 0xC246\n')
            syms = ps.load_symbols(None, noi, None)
            self.assertEqual(syms['_active_lap_count'], 0xC2E5)
            self.assertEqual(syms['_px'], 0xC246)

    def test_noi_ignores_symbols_outside_wram(self):
        with tempfile.TemporaryDirectory() as d:
            noi = os.path.join(d, 'rom.noi')
            write(noi, 'DEF _rom_thing 0x4000\nDEF _hp 0xC4F2\n')
            syms = ps.load_symbols(None, noi, None)
            self.assertNotIn('_rom_thing', syms)
            self.assertIn('_hp', syms)

    def test_manifest_null_symbol_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            manifest = os.path.join(d, 'game-manifest.json')
            write(manifest, json.dumps({'symbols': {'_cp_next': None, '_hp': '0xC4F2'}}))
            syms = ps.load_symbols(manifest, None, None)
            self.assertNotIn('_cp_next', syms)
            self.assertEqual(syms['_hp'], 0xC4F2)

    def test_missing_files_are_tolerated(self):
        self.assertEqual(ps.load_symbols('/nope/a.json', '/nope/b.noi', '/nope/c.map'), {})


class TestResolve(unittest.TestCase):

    def test_hex_literal(self):
        self.assertEqual(ps.resolve('0xC199', {}), 0xC199)

    def test_symbol_lookup(self):
        self.assertEqual(ps.resolve('_hp', {'_hp': 0xC4F2}), 0xC4F2)

    def test_unknown_symbol_raises_scenario_error(self):
        with self.assertRaises(ps.ScenarioError):
            ps.resolve('_nope', {'_hp': 0xC4F2})


class TestReadValue(unittest.TestCase):

    def test_byte_read(self):
        emu = FakeEmu(memory={0xC4F2: 7})
        self.assertEqual(ps.read_value(emu, 0xC4F2), 7)

    def test_little_endian_word_read(self):
        emu = FakeEmu(memory={0xC246: 0x34, 0xC247: 0x12})
        self.assertEqual(ps.read_value(emu, 0xC246, 2), 0x1234)

    def test_px_and_py_default_to_word_width(self):
        self.assertEqual(ps.DEFAULT_WIDTHS['_px'], 2)
        self.assertEqual(ps.DEFAULT_WIDTHS['_py'], 2)


class TestLoadScenario(unittest.TestCase):

    def _lib(self, d, name, obj):
        path = os.path.join(d, name + '.json')
        write(path, json.dumps(obj))
        return path

    def test_bare_list_is_accepted_and_defaults_applied(self):
        sc = ps.load_scenario([{"action": "advance", "frames": 3}])
        self.assertEqual(sc['steps'], [{"action": "advance", "frames": 3}])
        self.assertTrue(sc['blocking'])
        self.assertEqual(sc['watch'], [])

    def test_dict_form_preserves_metadata(self):
        sc = ps.load_scenario({
            "name": "x", "blocking": False, "watch": ["_hp"],
            "steps": [{"action": "advance", "frames": 1}],
        })
        self.assertEqual(sc['name'], 'x')
        self.assertFalse(sc['blocking'])
        self.assertEqual(sc['watch'], ['_hp'])

    def test_include_is_inlined_by_concatenation(self):
        with tempfile.TemporaryDirectory() as d:
            self._lib(d, 'snippet', {"steps": [
                {"action": "advance", "frames": 1},
                {"action": "advance", "frames": 2},
            ]})
            sc = ps.load_scenario({"steps": [
                {"action": "include", "name": "snippet"},
                {"action": "advance", "frames": 3},
            ]}, library_dir=d)
            self.assertEqual([s['frames'] for s in sc['steps']], [1, 2, 3])
            self.assertNotIn('include', [s['action'] for s in sc['steps']])

    def test_nested_includes_are_inlined(self):
        with tempfile.TemporaryDirectory() as d:
            self._lib(d, 'inner', {"steps": [{"action": "advance", "frames": 1}]})
            self._lib(d, 'outer', {"steps": [
                {"action": "include", "name": "inner"},
                {"action": "advance", "frames": 2},
            ]})
            sc = ps.load_scenario({"steps": [{"action": "include", "name": "outer"}]},
                                  library_dir=d)
            self.assertEqual([s['frames'] for s in sc['steps']], [1, 2])

    def test_include_cycle_raises(self):
        with tempfile.TemporaryDirectory() as d:
            self._lib(d, 'a', {"steps": [{"action": "include", "name": "b"}]})
            self._lib(d, 'b', {"steps": [{"action": "include", "name": "a"}]})
            with self.assertRaises(ps.ScenarioError):
                ps.load_scenario({"steps": [{"action": "include", "name": "a"}]},
                                 library_dir=d)

    def test_dangling_include_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ps.ScenarioError):
                ps.load_scenario({"steps": [{"action": "include", "name": "ghost"}]},
                                 library_dir=d)

    def test_unknown_action_raises(self):
        with self.assertRaises(ps.ScenarioError):
            ps.load_scenario([{"action": "teleport"}])

    def test_missing_required_field_raises(self):
        with self.assertRaises(ps.ScenarioError):
            ps.load_scenario([{"action": "assert_memory", "address": "_hp"}])

    def test_scenario_loaded_from_path(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._lib(d, 'file', {"steps": [{"action": "advance", "frames": 9}]})
            sc = ps.load_scenario(p, library_dir=d)
            self.assertEqual(sc['steps'][0]['frames'], 9)
            self.assertEqual(sc['name'], 'file')


class TestPressSemantics(unittest.TestCase):

    def test_rendered_tick_precedes_every_press(self):
        emu = FakeEmu()
        ctx = ps.RunContext(symbols={})
        ps.run(emu, [{"action": "press", "buttons": ["start"], "delay": 4}], ctx)
        # The frame immediately before the press must have been rendered.
        _, _, at = emu.presses[0]
        self.assertTrue(emu.render_log[at - 1],
                        "KEY_TICKED requires a rendered frame before button()")

    def test_multi_button_press_is_simultaneous(self):
        emu = FakeEmu()
        ctx = ps.RunContext(symbols={})
        ps.run(emu, [{"action": "press", "buttons": ["a", "left"], "delay": 6}], ctx)
        self.assertEqual([p[0] for p in emu.presses], ["a", "left"])
        # Both queued at the same tick count => held together.
        self.assertEqual(emu.presses[0][2], emu.presses[1][2])

    def test_press_holds_for_delay_frames(self):
        emu = FakeEmu()
        ctx = ps.RunContext(symbols={})
        ps.run(emu, [{"action": "press", "buttons": ["a"], "delay": 10}], ctx)
        self.assertEqual(emu.presses[0][1], 10)


class TestAdvanceAndWait(unittest.TestCase):

    def test_advance_ticks_requested_frames(self):
        emu = FakeEmu()
        ctx = ps.RunContext(symbols={})
        ps.run(emu, [{"action": "advance", "frames": 25}], ctx)
        self.assertEqual(emu.ticks, 25)
        self.assertEqual(ctx.frame, 25)

    def test_wait_memory_returns_when_value_matches(self):
        emu = FakeEmu(memory={0xC199: 1})
        ctx = ps.RunContext(symbols={'_hp': 0xC199})
        ps.run(emu, [{"action": "wait_memory", "address": "_hp",
                      "value": 1, "max_frames": 50}], ctx)
        self.assertLess(emu.ticks, 50)

    def test_wait_memory_timeout_raises_step_failure(self):
        emu = FakeEmu(memory={0xC199: 0})
        ctx = ps.RunContext(symbols={'_hp': 0xC199})
        with self.assertRaises(ps.StepFailure) as cm:
            ps.run(emu, [{"action": "wait_memory", "address": "_hp",
                          "value": 1, "max_frames": 8}], ctx)
        self.assertEqual(cm.exception.kind, 'timeout')
        self.assertEqual(cm.exception.step, 0)

    def test_wait_memory_supports_operator_and_width(self):
        emu = FakeEmu(memory={0xC246: 0x00, 0xC247: 0x02})   # _px == 512
        ctx = ps.RunContext(symbols={'_px': 0xC246})
        ps.run(emu, [{"action": "wait_memory", "address": "_px", "value": 100,
                      "op": "gt", "width": 2, "max_frames": 5}], ctx)
        self.assertLess(emu.ticks, 5)

    def test_screenshot_step_saves_to_named_path(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, 'shot.png')
            emu = FakeEmu()
            ctx = ps.RunContext(symbols={}, default_out=os.path.join(d, 'default.png'))
            ps.run(emu, [{"action": "screenshot", "out": out}], ctx)
            self.assertIn(out, emu.saved)


class TestTraceAndFreeze(unittest.TestCase):

    def test_trace_samples_at_interval_and_tags_step(self):
        emu = FakeEmu(memory={0xC4F2: 5})
        ctx = ps.RunContext(symbols={'_hp': 0xC4F2}, watch=['_hp'], trace_every=10)
        ps.run(emu, [{"action": "advance", "frames": 30}], ctx)
        self.assertEqual(len(ctx.trace), 3)
        self.assertEqual(ctx.trace[0]['values']['_hp'], 5)
        self.assertEqual(ctx.trace[0]['step'], 0)
        self.assertEqual(ctx.trace[0]['action'], 'advance')
        self.assertEqual([r['frame'] for r in ctx.trace], [10, 20, 30])

    def test_trace_records_screen_hash(self):
        emu = FakeEmu()
        ctx = ps.RunContext(symbols={}, trace_every=5)
        ps.run(emu, [{"action": "advance", "frames": 5}], ctx)
        self.assertIn('screen_hash', ctx.trace[0])

    def test_freeze_watchdog_fires_on_static_screen(self):
        emu = FakeEmu()                      # tobytes() constant => hash never changes
        ctx = ps.RunContext(symbols={}, trace_every=10, freeze_frames=30)
        with self.assertRaises(ps.StepFailure) as cm:
            ps.run(emu, [{"action": "advance", "frames": 200}], ctx)
        self.assertEqual(cm.exception.kind, 'freeze')

    def test_freeze_watchdog_silent_when_screen_changes(self):
        emu = FakeEmu(frames=[[i % 251] for i in range(300)])
        ctx = ps.RunContext(symbols={}, trace_every=10, freeze_frames=30)
        ps.run(emu, [{"action": "advance", "frames": 200}], ctx)   # must not raise
        self.assertEqual(ctx.frame, 200)

    def test_freeze_watchdog_disabled_when_zero(self):
        emu = FakeEmu()
        ctx = ps.RunContext(symbols={}, trace_every=10, freeze_frames=0)
        ps.run(emu, [{"action": "advance", "frames": 200}], ctx)
        self.assertEqual(ctx.frame, 200)


class ChangingEmu(FakeEmu):
    """_px increments every tick; everything else is static."""

    def tick(self, n=1, render=False):
        super().tick(n, render)
        val = self.ticks & 0xFFFF
        self.memory[0xC246] = val & 0xFF
        self.memory[0xC247] = (val >> 8) & 0xFF


class TickingSymbolEmu(FakeEmu):
    """A FakeEmu whose watched byte advances on every tick, while the screen
    payload never changes. It is the fixture that separates "the symbol moved"
    from "the screen moved"."""

    def __init__(self, address, memory=None, frames=None):
        super().__init__(memory=dict(memory or {}), frames=frames)
        self._address = address

    def tick(self, n=1, render=False):
        for _ in range(int(n)):
            super().tick(1, render=render)
            self.memory[self._address] = (self.memory[self._address] + 1) & 0xFF


class TestAssertMemory(unittest.TestCase):

    def test_passes_on_equal(self):
        emu = FakeEmu(memory={0xC199: 1})
        ctx = ps.RunContext(symbols={'_hp': 0xC199})
        ps.run(emu, [{"action": "assert_memory", "address": "_hp", "value": 1}], ctx)

    def test_fails_on_mismatch_with_step_index(self):
        emu = FakeEmu(memory={0xC199: 0})
        ctx = ps.RunContext(symbols={'_hp': 0xC199})
        with self.assertRaises(ps.StepFailure) as cm:
            ps.run(emu, [{"action": "advance", "frames": 1},
                         {"action": "assert_memory", "address": "_hp", "value": 1}], ctx)
        self.assertEqual(cm.exception.step, 1)
        self.assertEqual(cm.exception.kind, 'assert')

    def test_gt_operator(self):
        emu = FakeEmu(memory={0xC4F2: 9})
        ctx = ps.RunContext(symbols={'_hp': 0xC4F2})
        ps.run(emu, [{"action": "assert_memory", "address": "_hp", "value": 0, "op": "gt"}], ctx)

    def test_gt_operator_fails_at_zero(self):
        emu = FakeEmu(memory={0xC4F2: 0})
        ctx = ps.RunContext(symbols={'_hp': 0xC4F2})
        with self.assertRaises(ps.StepFailure):
            ps.run(emu, [{"action": "assert_memory", "address": "_hp",
                          "value": 0, "op": "gt"}], ctx)

    def test_word_width_read(self):
        emu = FakeEmu(memory={0xC246: 0x00, 0xC247: 0x01})   # 256
        ctx = ps.RunContext(symbols={'_px': 0xC246})
        ps.run(emu, [{"action": "assert_memory", "address": "_px",
                      "value": 256, "width": 2}], ctx)

    def test_px_defaults_to_word_width_without_explicit_field(self):
        emu = FakeEmu(memory={0xC246: 0x00, 0xC247: 0x01})
        ctx = ps.RunContext(symbols={'_px': 0xC246})
        ps.run(emu, [{"action": "assert_memory", "address": "_px", "value": 256}], ctx)


class TestAssertLive(unittest.TestCase):

    def test_passes_when_symbol_and_screen_change(self):
        emu = ChangingEmu(memory={0xC246: 0, 0xC247: 0},
                          frames=[[i % 251] for i in range(400)])
        ctx = ps.RunContext(symbols={'_px': 0xC246})
        ps.run(emu, [{"action": "assert_live", "symbols": ["_px"],
                      "screen": True, "frames": 30}], ctx)

    def test_fails_when_symbol_is_frozen(self):
        emu = FakeEmu(memory={0xC246: 7, 0xC247: 0},
                      frames=[[i % 251] for i in range(400)])
        ctx = ps.RunContext(symbols={'_px': 0xC246})
        with self.assertRaises(ps.StepFailure) as cm:
            ps.run(emu, [{"action": "assert_live", "symbols": ["_px"],
                          "screen": True, "frames": 20}], ctx)
        self.assertEqual(cm.exception.kind, 'stale-symbol')
        self.assertIn('_px', cm.exception.message)

    def test_fails_when_screen_is_frozen(self):
        emu = ChangingEmu(memory={0xC246: 0, 0xC247: 0})   # constant screen bytes
        ctx = ps.RunContext(symbols={'_px': 0xC246})
        with self.assertRaises(ps.StepFailure) as cm:
            ps.run(emu, [{"action": "assert_live", "symbols": ["_px"],
                          "screen": True, "frames": 20}], ctx)
        self.assertEqual(cm.exception.kind, 'stale-screen')
        self.assertIn('screen', cm.exception.message)

    def test_screen_check_can_be_disabled(self):
        emu = ChangingEmu(memory={0xC246: 0, 0xC247: 0})
        ctx = ps.RunContext(symbols={'_px': 0xC246})
        ps.run(emu, [{"action": "assert_live", "symbols": ["_px"],
                      "screen": False, "frames": 20}], ctx)


class TestNav(unittest.TestCase):

    MANIFEST = {
        "navigation": {
            "travel_frames_per_tile": 4,
            "overmap_to_track": {"1": ["left", "left"], "2": ["right"]},
            "overmap_to_hub":   {"1": ["up", "up"]},
        }
    }

    def test_nav_to_track_expands_manifest_path(self):
        emu = FakeEmu()
        ctx = ps.RunContext(symbols={}, manifest=self.MANIFEST)
        ps.run(emu, [{"action": "nav", "to": "track", "id": 1}], ctx)
        self.assertEqual([p[0] for p in emu.presses], ["left", "left"])
        self.assertEqual(emu.presses[0][1], 4)      # travel_frames_per_tile

    def test_nav_to_hub_expands_manifest_path(self):
        emu = FakeEmu()
        ctx = ps.RunContext(symbols={}, manifest=self.MANIFEST)
        ps.run(emu, [{"action": "nav", "to": "hub", "id": 1}], ctx)
        self.assertEqual([p[0] for p in emu.presses], ["up", "up"])

    def test_nav_without_manifest_raises_scenario_error(self):
        emu = FakeEmu()
        ctx = ps.RunContext(symbols={}, manifest={})
        with self.assertRaises(ps.ScenarioError):
            ps.run(emu, [{"action": "nav", "to": "track", "id": 1}], ctx)

    def test_nav_unknown_destination_raises_scenario_error(self):
        emu = FakeEmu()
        ctx = ps.RunContext(symbols={}, manifest=self.MANIFEST)
        with self.assertRaises(ps.ScenarioError):
            ps.run(emu, [{"action": "nav", "to": "track", "id": 99}], ctx)


class TestScreenshotCliSurface(unittest.TestCase):
    """AC2: screenshot.py's flags and step schema must not regress."""

    def _parser(self):
        import importlib
        mod = importlib.import_module('screenshot')
        return mod.build_parser()

    def test_legacy_flags_still_present(self):
        opts = {a.dest for a in self._parser()._actions}
        for flag in ('rom', 'map', 'out', 'steps', 'steps_file'):
            self.assertIn(flag, opts)

    def test_new_optional_flags_present(self):
        opts = {a.dest for a in self._parser()._actions}
        for flag in ('noi', 'manifest', 'library'):
            self.assertIn(flag, opts)

    def test_default_steps_is_empty_json_array(self):
        args = self._parser().parse_args([])
        self.assertEqual(args.steps, '[]')


class TestSmoketestResults(unittest.TestCase):

    def _mod(self):
        import importlib
        return importlib.import_module('smoketest_headless')

    def test_trace_is_written_as_jsonl(self):
        st = self._mod()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'trace.jsonl')
            st.write_trace([{"frame": 10, "values": {"_hp": 8}},
                            {"frame": 20, "values": {"_hp": 7}}], path)
            lines = [json.loads(l) for l in open(path) if l.strip()]
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[1]['values']['_hp'], 7)

    def test_passing_result_has_pass_verdict(self):
        st = self._mod()
        ctx = ps.RunContext(symbols={})
        ctx.frame = 100
        res = st.build_result('generic-smoke', ctx)
        self.assertEqual(res['verdict'], 'pass')
        self.assertEqual(res['scenario'], 'generic-smoke')
        self.assertEqual(res['frames'], 100)
        self.assertIsNone(res['failure'])

    def test_failing_result_records_step_and_kind(self):
        st = self._mod()
        ctx = ps.RunContext(symbols={})
        fail = ps.StepFailure(19, 'stale-symbol', '_px unchanged over 60 frames', 'assert_live')
        res = st.build_result('generic-smoke', ctx, failure=fail)
        self.assertEqual(res['verdict'], 'fail')
        self.assertEqual(res['failure']['step'], 19)
        self.assertEqual(res['failure']['kind'], 'stale-symbol')
        self.assertEqual(res['failure']['action'], 'assert_live')

    def test_exit_codes_are_zero_one_two(self):
        st = self._mod()
        self.assertEqual(st.EXIT_PASS, 0)
        self.assertEqual(st.EXIT_FAIL, 1)
        self.assertEqual(st.EXIT_USAGE, 2)


def rec(frame, step, values, action='advance'):
    return {"frame": frame, "step": step, "action": action,
            "values": values, "screen_hash": "x"}


class TestDiffTraces(unittest.TestCase):

    def test_identical_traces_have_no_divergence(self):
        a = [rec(10, 0, {"_hp": 8}), rec(20, 1, {"_hp": 8})]
        self.assertIsNone(ps.diff_traces(a, list(a)))

    def test_reports_first_diverging_symbol_with_both_values(self):
        a = [rec(10, 0, {"_hp": 8}), rec(20, 1, {"_hp": 0})]
        b = [rec(10, 0, {"_hp": 8}), rec(20, 1, {"_hp": 8})]
        d = ps.diff_traces(a, b)
        self.assertEqual(d['step'], 1)
        self.assertEqual(d['symbol'], '_hp')
        self.assertEqual(d['main'], 0)
        self.assertEqual(d['ref'], 8)
        self.assertEqual(d['frame'], 20)

    def test_timing_shift_within_a_step_does_not_desynchronise(self):
        # Same step, ref sampled one extra time; values agree where compared.
        a = [rec(10, 0, {"_hp": 8}), rec(20, 0, {"_hp": 8})]
        b = [rec(10, 0, {"_hp": 8}), rec(20, 0, {"_hp": 8}), rec(30, 0, {"_hp": 8})]
        d = ps.diff_traces(a, b)
        self.assertEqual(d['symbol'], '__sample_count__')
        self.assertEqual(d['step'], 0)

    def test_earlier_step_divergence_wins_over_later(self):
        a = [rec(10, 0, {"_hp": 1}), rec(20, 5, {"_hp": 9})]
        b = [rec(10, 0, {"_hp": 2}), rec(20, 5, {"_hp": 3})]
        self.assertEqual(ps.diff_traces(a, b)['step'], 0)

    def test_only_shared_symbols_are_compared(self):
        a = [rec(10, 0, {"_hp": 8, "_px": 5})]
        b = [rec(10, 0, {"_hp": 8})]
        self.assertIsNone(ps.diff_traces(a, b))


# Fixture WRAM map. The literals below match the real debug build:
#   _stack 0xC176 (StateEntry[2], stride 7), _sm_slot_src 0xC184 (2 bytes per
#   slot), _sm_depth 0xC5E9. Slot 1 is where a race actually runs, because the
#   canonical path is overmap(0) -> prerace(+1) -> playing(1).
SM_DEPTH, SM_SLOT_SRC, SM_STACK = 0xC5E9, 0xC184, 0xC176

NOI_STATES = (
    'DEF ___bank_state_hub 0x0\n'
    'DEF ___bank_state_overmap 0x0\n'
    'DEF ___bank_state_playing 0x1\n'
    'DEF ___bank_state_results 0x3\n'
    'DEF ___bank_state_title 0x3\n'
    'DEF ___func_state_playing 0x177E0\n'
    'DEF _state_hub 0xB9C\n'
    'DEF _state_overmap 0x1014\n'
    'DEF _state_playing 0x17EED\n'
    'DEF _state_results 0x35620\n'
    'DEF _state_title 0x35704\n'
    'DEF _state_push 0x136A\n'
    'DEF _state_pop 0x1397\n'
    'DEF _state_replace 0x13EC\n'
    'DEF _state_manager_init 0x1341\n'
    'DEF _state_manager_update 0x1346\n'
    'DEF _state_results_set_earned 0x3557C\n'
)


def state_symbols():
    return {'_sm_depth': SM_DEPTH, '_sm_slot_src': SM_SLOT_SRC,
            '_stack': SM_STACK}


def state_table():
    return {'hub': (0, 0x0B9C), 'overmap': (0, 0x1014),
            'playing': (1, 0x7EED), 'results': (3, 0x5620),
            'title': (3, 0x5704)}


def state_memory(bank, ptr, depth=1):
    """WRAM bytes that name one state at slot depth-1. Literal offsets."""
    if depth == 1:
        return {SM_DEPTH: 1,
                0xC184: ptr & 0xFF, 0xC185: (ptr >> 8) & 0xFF,   # slot 0 ptr
                0xC176: bank}                                     # slot 0 bank
    return {SM_DEPTH: 2,
            0xC184: 0xED, 0xC185: 0x7E,                           # slot 0 ptr
            0xC176: 1,                                            # slot 0 bank
            0xC186: ptr & 0xFF, 0xC187: (ptr >> 8) & 0xFF,        # slot 1 ptr
            0xC17D: bank}                                         # slot 1 bank


def emu_in_state(bank, ptr, depth=1):
    return FakeEmu(memory=state_memory(bank, ptr, depth))


class TestStateTable(unittest.TestCase):

    def test_every_state_object_is_listed_with_its_bank(self):
        with tempfile.TemporaryDirectory() as d:
            noi = os.path.join(d, 'rom.noi')
            write(noi, NOI_STATES)
            self.assertEqual(ps.load_state_table(noi), state_table())

    def test_state_manager_functions_are_not_states(self):
        with tempfile.TemporaryDirectory() as d:
            noi = os.path.join(d, 'rom.noi')
            write(noi, NOI_STATES)
            table = ps.load_state_table(noi)
            for name in ('push', 'pop', 'replace', 'manager_init',
                         'manager_update', 'results_set_earned'):
                self.assertNotIn(name, table)

    def test_a_bank_symbol_that_disagrees_with_the_flat_address_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            noi = os.path.join(d, 'rom.noi')
            write(noi, 'DEF ___bank_state_bogus 0x2\nDEF _state_bogus 0x17EED\n')
            self.assertEqual(ps.load_state_table(noi), {})

    def test_a_missing_file_gives_an_empty_table(self):
        self.assertEqual(ps.load_state_table('nope.noi'), {})

    def test_names_normalize_to_the_short_form(self):
        self.assertEqual(ps.normalize_state_name('_state_playing'), 'playing')
        self.assertEqual(ps.normalize_state_name('state_playing'), 'playing')
        self.assertEqual(ps.normalize_state_name('playing'), 'playing')


class TestReadState(unittest.TestCase):

    def ctx(self):
        return ps.RunContext(symbols=state_symbols(), state_table=state_table())

    def test_a_banked_state_is_named(self):
        self.assertEqual(self.ctx().read_state(emu_in_state(1, 0x7EED)), 'playing')

    def test_a_bank_zero_state_is_named(self):
        self.assertEqual(self.ctx().read_state(emu_in_state(0, 0x1014)), 'overmap')

    def test_slot_one_is_read_at_the_right_offsets(self):
        """Depth 2 is the depth a race runs at. This is the test that fails
        when STATE_PTR_WIDTH or STATE_ENTRY_STRIDE is wrong."""
        self.assertEqual(self.ctx().read_state(emu_in_state(3, 0x5620, depth=2)),
                         'results')

    def test_depth_zero_has_no_state(self):
        self.assertIsNone(self.ctx().read_state(FakeEmu(memory={SM_DEPTH: 0})))

    def test_a_wrong_bank_byte_still_resolves_by_address(self):
        self.assertEqual(self.ctx().read_state(emu_in_state(0xFF, 0x7EED)),
                         'playing')

    def test_a_colliding_address_needs_the_bank_to_decide(self):
        table = {'alpha': (1, 0x4000), 'beta': (2, 0x4000)}
        ctx = ps.RunContext(symbols=state_symbols(), state_table=table)
        self.assertEqual(ctx.read_state(emu_in_state(2, 0x4000)), 'beta')

    def test_a_colliding_address_with_no_bank_match_is_unknown(self):
        table = {'alpha': (1, 0x4000), 'beta': (2, 0x4000)}
        ctx = ps.RunContext(symbols=state_symbols(), state_table=table)
        self.assertIsNone(ctx.read_state(emu_in_state(7, 0x4000)))

    def test_state_is_unreadable_without_the_debug_symbols(self):
        ctx = ps.RunContext(symbols={'_hp': 0xC535}, state_table=state_table())
        self.assertFalse(ctx.state_readable())
        self.assertIsNone(ctx.read_state(FakeEmu()))

    def test_state_is_unreadable_without_a_state_table(self):
        self.assertFalse(
            ps.RunContext(symbols=state_symbols(), state_table={}).state_readable())


class TestRequire(unittest.TestCase):

    def ctx(self):
        return ps.RunContext(symbols=dict(state_symbols(), _hp=0xC535),
                             state_table=state_table())

    def test_a_true_state_requirement_lets_the_action_run(self):
        ctx = self.ctx()
        ps.run(emu_in_state(1, 0x7EED),
               [{'action': 'advance', 'frames': 3,
                 'require': {'state': 'playing'}}], ctx)
        self.assertEqual(ctx.frame, 3)

    def test_a_false_state_requirement_is_a_precondition_failure(self):
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(emu_in_state(3, 0x5620),
                   [{'action': 'advance', 'frames': 3,
                     'require': {'state': 'playing'}}], self.ctx())
        self.assertEqual(caught.exception.kind, 'precondition')
        self.assertIn('playing', caught.exception.message)
        self.assertIn('results', caught.exception.message)

    def test_a_false_requirement_stops_the_action_before_it_runs(self):
        emu = emu_in_state(3, 0x5620)
        with self.assertRaises(ps.StepFailure):
            ps.run(emu, [{'action': 'advance', 'frames': 50,
                          'require': {'state': 'playing'}}], self.ctx())
        self.assertEqual(emu.ticks, 0)

    def test_the_long_state_spelling_is_accepted(self):
        ps.run(emu_in_state(1, 0x7EED),
               [{'action': 'advance', 'frames': 1,
                 'require': {'state': '_state_playing'}}], self.ctx())

    def test_a_false_memory_requirement_is_a_precondition_failure(self):
        emu = emu_in_state(1, 0x7EED)
        emu.memory[0xC535] = 0
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(emu, [{'action': 'advance', 'frames': 1,
                          'require': {'address': '_hp', 'op': 'gt',
                                      'value': 0}}], self.ctx())
        self.assertEqual(caught.exception.kind, 'precondition')
        self.assertIn('_hp', caught.exception.message)

    def test_a_satisfied_memory_requirement_lets_the_action_run(self):
        emu = emu_in_state(1, 0x7EED)
        emu.memory[0xC535] = 5
        ctx = self.ctx()
        ps.run(emu, [{'action': 'advance', 'frames': 2,
                      'require': {'address': '_hp', 'op': 'gt',
                                  'value': 0}}], ctx)
        self.assertEqual(ctx.frame, 2)

    def test_a_memory_requirement_needs_no_state_reader(self):
        emu = FakeEmu(memory={0xC535: 5})
        ctx = ps.RunContext(symbols={'_hp': 0xC535})
        ps.run(emu, [{'action': 'advance', 'frames': 1,
                      'require': {'address': '_hp', 'op': 'gt',
                                  'value': 0}}], ctx)
        self.assertEqual(ctx.frame, 1)


class TestRequireValidation(unittest.TestCase):

    def load(self, step, state_names=None):
        return ps.load_scenario([step], state_names=state_names)

    def test_a_require_that_is_not_an_object_is_a_usage_error(self):
        with self.assertRaises(ps.ScenarioError):
            self.load({'action': 'advance', 'frames': 1, 'require': 'playing'})

    def test_an_unknown_require_field_is_a_usage_error(self):
        with self.assertRaises(ps.ScenarioError):
            self.load({'action': 'advance', 'frames': 1,
                       'require': {'stat': 'playing'}})

    def test_an_empty_require_is_a_usage_error(self):
        with self.assertRaises(ps.ScenarioError):
            self.load({'action': 'advance', 'frames': 1, 'require': {}})

    def test_an_address_without_a_value_is_a_usage_error(self):
        with self.assertRaises(ps.ScenarioError):
            self.load({'action': 'advance', 'frames': 1,
                       'require': {'address': '_hp'}})

    def test_an_unknown_operator_is_a_usage_error(self):
        with self.assertRaises(ps.ScenarioError):
            self.load({'action': 'advance', 'frames': 1,
                       'require': {'address': '_hp', 'value': 0, 'op': 'wat'}})

    def test_an_unknown_state_name_is_a_usage_error(self):
        with self.assertRaises(ps.ScenarioError) as caught:
            self.load({'action': 'advance', 'frames': 1,
                       'require': {'state': 'flying'}},
                      state_names=set(state_table()))
        self.assertIn('flying', str(caught.exception))

    def test_a_known_state_name_loads(self):
        self.load({'action': 'advance', 'frames': 1,
                   'require': {'state': 'playing'}},
                  state_names=set(state_table()))

    def test_an_empty_state_name_set_still_rejects_a_state(self):
        """An empty set is not the same as 'do not check' — a missing symbol
        file must not switch AC7 off."""
        with self.assertRaises(ps.ScenarioError):
            self.load({'action': 'advance', 'frames': 1,
                       'require': {'state': 'playing'}}, state_names=set())

    def test_state_names_are_not_checked_when_none_is_passed(self):
        self.load({'action': 'advance', 'frames': 1,
                   'require': {'state': 'flying'}})

    def test_require_on_an_include_step_is_a_usage_error(self):
        """`_inline` rebuilds the step list and drops every other key, so a
        `require` here would vanish without a word."""
        with tempfile.TemporaryDirectory() as d:
            write(os.path.join(d, 'inner.json'),
                  json.dumps([{'action': 'advance', 'frames': 1}]))
            with self.assertRaises(ps.ScenarioError) as caught:
                ps.load_scenario([{'action': 'include', 'name': 'inner',
                                   'require': {'state': 'playing'}}],
                                 library_dir=d)
            self.assertIn('require', str(caught.exception))


class TestStateSupport(unittest.TestCase):

    def test_a_state_requirement_without_the_reader_is_a_usage_error(self):
        with self.assertRaises(ps.ScenarioError) as caught:
            ps.validate_state_support(
                [{'action': 'advance', 'frames': 1,
                  'require': {'state': 'playing'}}], False)
        self.assertIn('build-debug', str(caught.exception))

    def test_a_state_action_without_the_reader_is_a_usage_error(self):
        with self.assertRaises(ps.ScenarioError):
            ps.validate_state_support(
                [{'action': 'assert_state', 'state': 'playing'}], False)

    def test_a_memory_requirement_needs_no_reader(self):
        ps.validate_state_support(
            [{'action': 'advance', 'frames': 1,
              'require': {'address': '_hp', 'value': 0, 'op': 'gt'}}], False)

    def test_a_state_requirement_with_the_reader_is_accepted(self):
        ps.validate_state_support(
            [{'action': 'advance', 'frames': 1,
              'require': {'state': 'playing'}}], True)


class StatefulEmu(FakeEmu):
    """A FakeEmu that walks a scripted list of states as it ticks.

    `schedule` maps a tick count to a (bank, ptr) pair. The greatest key at or
    below the current tick wins, so the game changes under the harness exactly
    as it does on hardware.
    """

    def __init__(self, schedule, depth=1, extra=None):
        super().__init__(memory=dict(extra or {}))
        self._schedule = dict(schedule)
        self._depth = depth
        self._apply(0)

    def _apply(self, tick):
        keys = [k for k in self._schedule if k <= tick]
        if not keys:
            return
        bank, ptr = self._schedule[max(keys)]
        self.memory.update(state_memory(bank, ptr, self._depth))

    def tick(self, n=1, render=False):
        for _ in range(int(n)):
            super().tick(1, render=render)
            self._apply(self.ticks)


class TestStatefulEmuFixture(unittest.TestCase):
    """The fixture is machinery the other tests trust. Prove it first."""

    def test_a_schedule_that_starts_late_does_not_raise(self):
        emu = StatefulEmu({5: (1, 0x7EED)})
        emu.tick(4)
        emu.tick(1)
        ctx = ps.RunContext(symbols=state_symbols(), state_table=state_table())
        self.assertEqual(ctx.read_state(emu), 'playing')


class TestAssertState(unittest.TestCase):

    def ctx(self):
        return ps.RunContext(symbols=state_symbols(), state_table=state_table())

    def test_it_passes_in_the_expected_state(self):
        ps.run(emu_in_state(1, 0x7EED),
               [{'action': 'assert_state', 'state': 'playing'}], self.ctx())

    def test_it_fails_after_the_race_ends_and_names_the_real_state(self):
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(emu_in_state(3, 0x5620),
                   [{'action': 'assert_state', 'state': 'playing'}], self.ctx())
        self.assertEqual(caught.exception.kind, 'state')
        self.assertIn('results', caught.exception.message)

    def test_the_state_field_is_required(self):
        with self.assertRaises(ps.ScenarioError):
            ps.load_scenario([{'action': 'assert_state'}])


class TestWaitState(unittest.TestCase):

    def ctx(self):
        return ps.RunContext(symbols=state_symbols(), state_table=state_table())

    def test_it_reaches_the_target_state_inside_the_budget(self):
        emu = StatefulEmu({0: (3, 0x5704), 25: (1, 0x7EED)})
        ctx = self.ctx()
        ps.run(emu, [{'action': 'wait_state', 'state': 'playing',
                      'max_frames': 200}], ctx)
        self.assertLessEqual(ctx.frame, 200)
        self.assertEqual(ctx.read_state(emu), 'playing')

    def test_it_returns_at_once_when_already_there(self):
        emu = emu_in_state(1, 0x7EED)
        ps.run(emu, [{'action': 'wait_state', 'state': 'playing'}], self.ctx())
        self.assertEqual(emu.ticks, 0)

    def test_it_times_out_and_names_the_state_it_found(self):
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(emu_in_state(3, 0x5704),
                   [{'action': 'wait_state', 'state': 'playing',
                     'max_frames': 12}], self.ctx())
        self.assertEqual(caught.exception.kind, 'timeout')
        self.assertIn('title', caught.exception.message)

    def test_the_state_field_is_required(self):
        with self.assertRaises(ps.ScenarioError):
            ps.load_scenario([{'action': 'wait_state'}])


class TestLivenessSplit(unittest.TestCase):

    def dead_emu(self):
        """One frame payload for every tick: the screen hash never changes."""
        return FakeEmu(memory={0xC24B: 7, 0xC24C: 0}, frames=[[1]])

    def live_screen_emu(self):
        return FakeEmu(memory={0xC24B: 7, 0xC24C: 0},
                       frames=[[i % 7] for i in range(200)])

    def ctx(self):
        return ps.RunContext(symbols={'_px': 0xC24B})

    def test_a_stale_symbol_has_the_kind_stale_symbol(self):
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(self.live_screen_emu(),
                   [{'action': 'assert_changes', 'symbols': ['_px'],
                     'frames': 5}], self.ctx())
        self.assertEqual(caught.exception.kind, 'stale-symbol')
        self.assertIn('_px', caught.exception.message)

    def test_a_stale_screen_has_the_kind_stale_screen(self):
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(self.dead_emu(),
                   [{'action': 'assert_screen_changes', 'frames': 5}], self.ctx())
        self.assertEqual(caught.exception.kind, 'stale-screen')
        self.assertIn('screen', caught.exception.message)

    def test_the_two_messages_differ(self):
        symbol_msg = screen_msg = None
        try:
            ps.run(self.live_screen_emu(),
                   [{'action': 'assert_changes', 'symbols': ['_px'],
                     'frames': 5}], self.ctx())
        except ps.StepFailure as exc:
            symbol_msg = exc.message
        try:
            ps.run(self.dead_emu(),
                   [{'action': 'assert_screen_changes', 'frames': 5}], self.ctx())
        except ps.StepFailure as exc:
            screen_msg = exc.message
        self.assertIsNotNone(symbol_msg)
        self.assertIsNotNone(screen_msg)
        self.assertNotEqual(symbol_msg, screen_msg)

    def test_assert_changes_ignores_a_frozen_screen(self):
        """A live symbol behind a frozen screen must satisfy assert_changes.
        This is the case that fails if assert_changes also checks the screen."""
        emu = TickingSymbolEmu(0xC24B, memory={0xC24B: 0, 0xC24C: 0},
                               frames=[[1]])
        ps.run(emu, [{'action': 'assert_changes', 'symbols': ['_px'],
                      'frames': 5}], self.ctx())

    def test_assert_live_still_reports_the_frozen_screen(self):
        """Same fixture, assert_live: the screen half must still bite."""
        emu = TickingSymbolEmu(0xC24B, memory={0xC24B: 0, 0xC24C: 0},
                               frames=[[1]])
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(emu, [{'action': 'assert_live', 'symbols': ['_px'],
                          'frames': 5}], self.ctx())
        self.assertEqual(caught.exception.kind, 'stale-screen')

    def test_assert_screen_changes_ignores_symbols(self):
        """A stale symbol must not fail assert_screen_changes. `live_screen_emu`
        holds _px at 7 for the whole run, so a version that checked symbols
        would raise stale-symbol here."""
        ps.run(self.live_screen_emu(),
               [{'action': 'assert_screen_changes', 'symbols': ['_px'],
                 'frames': 5}], self.ctx())

    def test_assert_live_reports_the_symbol_first(self):
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(self.dead_emu(),
                   [{'action': 'assert_live', 'symbols': ['_px'], 'frames': 5}],
                   self.ctx())
        self.assertEqual(caught.exception.kind, 'stale-symbol')

    def test_assert_live_reports_the_screen_when_no_symbol_is_watched(self):
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(self.dead_emu(),
                   [{'action': 'assert_live', 'symbols': [], 'frames': 5}],
                   self.ctx())
        self.assertEqual(caught.exception.kind, 'stale-screen')

    def test_assert_changes_requires_symbols(self):
        with self.assertRaises(ps.ScenarioError):
            ps.load_scenario([{'action': 'assert_changes'}])


class TestTraceState(unittest.TestCase):

    def test_every_sample_carries_the_state(self):
        ctx = ps.RunContext(symbols=state_symbols(), state_table=state_table(),
                            trace_every=2)
        ps.run(emu_in_state(1, 0x7EED), [{'action': 'advance', 'frames': 6}], ctx)
        self.assertTrue(ctx.trace)
        for rec in ctx.trace:
            self.assertEqual(rec['state'], 'playing')

    def test_the_state_key_is_present_without_a_state_table(self):
        ctx = ps.RunContext(symbols={}, trace_every=2)
        ps.run(FakeEmu(memory={}), [{'action': 'advance', 'frames': 4}], ctx)
        self.assertTrue(ctx.trace)
        for rec in ctx.trace:
            self.assertIsNone(rec['state'])

    def test_a_state_change_during_an_action_carries_its_own_frame(self):
        """The fast path must not collapse a change onto the last frame."""
        emu = StatefulEmu({0: (1, 0x7EED), 10: (3, 0x5620)})
        ctx = ps.RunContext(symbols=state_symbols(), state_table=state_table())
        ps.run(emu, [{'action': 'advance', 'frames': 30}], ctx)
        self.assertEqual([(c['from'], c['to']) for c in ctx.state_changes],
                         [('playing', 'results')])
        self.assertEqual(ctx.state_changes[0]['frame'], 10)

    def test_two_changes_in_one_action_are_both_recorded(self):
        emu = StatefulEmu({0: (3, 0x5704), 5: (1, 0x7EED), 15: (3, 0x5620)})
        ctx = ps.RunContext(symbols=state_symbols(), state_table=state_table())
        ps.run(emu, [{'action': 'advance', 'frames': 25}], ctx)
        self.assertEqual([(c['frame'], c['to']) for c in ctx.state_changes],
                         [(5, 'playing'), (15, 'results')])

    def test_the_change_list_resets_at_every_action(self):
        emu = StatefulEmu({0: (1, 0x7EED), 5: (3, 0x5620)})
        ctx = ps.RunContext(symbols=state_symbols(), state_table=state_table())
        ps.run(emu, [{'action': 'advance', 'frames': 10},
                     {'action': 'advance', 'frames': 10}], ctx)
        self.assertEqual(ctx.state_changes, [])
        self.assertEqual(ctx.state_at_start, 'results')

    def test_the_fast_path_still_runs_when_no_state_is_readable(self):
        """The batched advance keeps screenshot.py fast.

        `emu.rendered` is what separates the two paths, NOT `len(render_log)`:
        `FakeEmu.tick` appends one entry per FRAME, so the log holds 40 entries
        either way. The fast path honours `render_last` and renders exactly one
        frame; the per-frame path renders only when a sample is due, and with
        `trace_every=0` none ever is, so it renders zero.
        """
        emu = FakeEmu(memory={})
        ctx = ps.RunContext(symbols={})
        ps.run(emu, [{'action': 'advance', 'frames': 40}], ctx)
        self.assertEqual(emu.ticks, 40)
        self.assertEqual(ctx.frame, 40)
        self.assertEqual(emu.rendered, 1)


class TestFailureContext(unittest.TestCase):

    SYMS = dict(_px=0xC24B, _py=0xC24D, _active_map_w=0xC5F1,
                _active_map_h=0xC5F2, **state_symbols())

    def car(self, px, py, w=20, h=100):
        """Both bytes of each 16-bit symbol, plus the live map size."""
        return {0xC24B: px & 0xFF, 0xC24C: (px >> 8) & 0xFF,
                0xC24D: py & 0xFF, 0xC24E: (py >> 8) & 0xFF,
                0xC5F1: w, 0xC5F2: h}

    def racing(self, px, py, **kw):
        mem = dict(state_memory(1, 0x7EED))
        mem.update(self.car(px, py, **kw))
        return mem

    def test_a_state_change_is_reported_with_its_frame(self):
        """AC5 shape: the race ends under the assertion."""
        emu = StatefulEmu({0: (1, 0x7EED), 8: (3, 0x5620)},
                          extra=self.car(64, 300))
        ctx = ps.RunContext(symbols=self.SYMS, state_table=state_table())
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(emu, [{'action': 'assert_changes', 'symbols': ['_py'],
                          'frames': 20}], ctx)
        block = caught.exception.context
        self.assertEqual(block['state_at_start'], 'playing')
        self.assertEqual(block['state_at_failure'], 'results')
        self.assertEqual(block['state_changes'],
                         [{'frame': 8, 'from': 'playing', 'to': 'results'}])
        self.assertIsNone(block['car'])
        self.assertIsNone(block['drive_limits'])
        self.assertEqual(block['at_limit'], [])
        self.assertIn('results', block['hint'])
        self.assertIn('8', block['hint'])

    def test_a_car_at_the_top_limit_is_reported_with_the_limit(self):
        """AC4 shape: the car drives into the top limit and stops."""
        emu = FakeEmu(memory=self.racing(64, 0))
        ctx = ps.RunContext(symbols=self.SYMS, state_table=state_table())
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(emu, [{'action': 'assert_changes', 'symbols': ['_py'],
                          'frames': 10}], ctx)
        block = caught.exception.context
        self.assertEqual(block['state_changes'], [])
        self.assertEqual(block['car'], {'px': 64, 'py': 0, 'tx': 8, 'ty': 0})
        self.assertEqual(block['drive_limits']['y_min'], 0)
        self.assertEqual(block['drive_limits']['y_max'], 100 * 8 - 16)
        self.assertEqual(block['drive_limits']['source'], 'wram')
        self.assertEqual(block['at_limit'], ['y_min'])
        self.assertIn('y_min', block['hint'])

    def test_a_car_in_the_far_corner_names_both_limits(self):
        emu = FakeEmu(memory=self.racing(144, 784))
        ctx = ps.RunContext(symbols=self.SYMS, state_table=state_table())
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(emu, [{'action': 'assert_changes', 'symbols': ['_py'],
                          'frames': 5}], ctx)
        self.assertEqual(sorted(caught.exception.context['at_limit']),
                         ['x_max', 'y_max'])

    def test_a_failure_outside_a_race_reports_no_drive_limit(self):
        """The loader sets the same map size for the overmap."""
        mem = dict(state_memory(0, 0x1014))
        mem.update(self.car(64, 0))
        ctx = ps.RunContext(symbols=self.SYMS, state_table=state_table())
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(FakeEmu(memory=mem, frames=[[1]]),
                   [{'action': 'assert_screen_changes', 'frames': 4}], ctx)
        block = caught.exception.context
        self.assertEqual(block['state_at_failure'], 'overmap')
        self.assertIsNone(block['drive_limits'])
        self.assertEqual(block['at_limit'], [])

    def test_a_precondition_failure_carries_a_context(self):
        mem = dict(state_memory(3, 0x5620))
        mem.update(self.car(64, 300))
        ctx = ps.RunContext(symbols=self.SYMS, state_table=state_table())
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(FakeEmu(memory=mem),
                   [{'action': 'advance', 'frames': 5,
                     'require': {'state': 'playing'}}], ctx)
        self.assertEqual(caught.exception.context['state_at_start'], 'results')
        self.assertIn('scenario', caught.exception.context['hint'])

    def test_the_context_survives_without_the_state_reader(self):
        ctx = ps.RunContext(symbols={'_px': 0xC24B, '_py': 0xC24D,
                                     '_active_map_w': 0xC5F1,
                                     '_active_map_h': 0xC5F2})
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(FakeEmu(memory=self.car(64, 0), frames=[[1]]),
                   [{'action': 'assert_screen_changes', 'frames': 4}], ctx)
        block = caught.exception.context
        self.assertIsNone(block['state_at_start'])
        self.assertEqual(block['car'], {'px': 64, 'py': 0, 'tx': 8, 'ty': 0})
        self.assertTrue(block['hint'])

    def test_the_context_omits_the_car_when_no_symbol_resolves(self):
        ctx = ps.RunContext(symbols={})
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(FakeEmu(memory={}, frames=[[1]]),
                   [{'action': 'assert_screen_changes', 'frames': 3}], ctx)
        self.assertIsNone(caught.exception.context['car'])
        self.assertIsNone(caught.exception.context['drive_limits'])

    def test_the_manifest_supplies_limits_when_wram_cannot(self):
        manifest = {'tracks': {'3': {'drive_limits': {
            'x_min': 0, 'x_max': 144, 'y_min': 0, 'y_max': 192}}}}
        ctx = ps.RunContext(symbols={'_px': 0xC24B, '_py': 0xC24D,
                                     '_current_race_id': 0xC5DD},
                            manifest=manifest)
        emu = FakeEmu(memory={0xC24B: 64, 0xC24C: 0, 0xC24D: 0, 0xC24E: 0,
                              0xC5DD: 3}, frames=[[1]])
        with self.assertRaises(ps.StepFailure) as caught:
            ps.run(emu, [{'action': 'assert_screen_changes', 'frames': 3}], ctx)
        limits = caught.exception.context['drive_limits']
        self.assertEqual(limits['y_max'], 192)
        self.assertEqual(limits['source'], 'manifest')


if __name__ == '__main__':
    unittest.main()
