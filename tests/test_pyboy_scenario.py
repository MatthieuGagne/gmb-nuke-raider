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


if __name__ == '__main__':
    unittest.main()
