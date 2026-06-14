"""Tests for tools/memory_check.py"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import memory_check


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_repo(d, map_content='', tile_files=None, config_content=''):
    """Create a minimal repo layout in temp dir d."""
    os.makedirs(os.path.join(d, 'build'), exist_ok=True)
    os.makedirs(os.path.join(d, 'src'), exist_ok=True)

    with open(os.path.join(d, 'build', 'nuke-raider.map'), 'w') as f:
        f.write(map_content)

    for filename, content in (tile_files or {}).items():
        with open(os.path.join(d, 'src', filename), 'w') as f:
            f.write(content)

    with open(os.path.join(d, 'src', 'config.h'), 'w') as f:
        f.write(config_content)


def _map_with_heap_e(addr):
    """Return minimal map content with s__HEAP_E at given hex address."""
    return f'     {addr:08X}  s__HEAP_E\n'


def _config(max_sprites=28, proj=8, enemies=8, racers=2, patrols=0):
    """Full OAM-relevant config.h. Playing peak = 4 + proj + enemies + racers*4 + patrols*4."""
    return (
        f'#define MAX_SPRITES {max_sprites}u\n'
        f'#define MAX_PROJECTILES {proj}u\n'
        f'#define MAX_ENEMIES {enemies}u\n'
        f'#define MAX_ENEMY_RACERS {racers}u\n'
        f'#define MAX_PATROLS {patrols}u\n'
    )


def _playing_peak(proj=8, enemies=8, racers=2, patrols=0):
    return 4 + proj + enemies + racers * 4 + patrols * 4


# ── WRAM tests ─────────────────────────────────────────────────────────────────

class TestCheckWRAM(unittest.TestCase):
    def test_pass(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, map_content=_map_with_heap_e(0xC23D))
            used, status = memory_check._check_wram(d)
            self.assertEqual(used, 573)
            self.assertEqual(status, 'PASS')

    def test_warn(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, map_content=_map_with_heap_e(0xC000 + 6554))
            used, status = memory_check._check_wram(d)
            self.assertEqual(status, 'WARN')

    def test_fail(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, map_content=_map_with_heap_e(0xC000 + 8192))
            used, status = memory_check._check_wram(d)
            self.assertEqual(status, 'FAIL')

    def test_missing_symbol_returns_error(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, map_content='no symbols here\n')
            used, status = memory_check._check_wram(d)
            self.assertIsNone(used)
            self.assertEqual(status, 'ERROR')

    def test_missing_map_file_returns_error(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'build'), exist_ok=True)
            os.makedirs(os.path.join(d, 'src'), exist_ok=True)
            used, status = memory_check._check_wram(d)
            self.assertIsNone(used)
            self.assertEqual(status, 'ERROR')


# ── VRAM tests ─────────────────────────────────────────────────────────────────

class TestCheckVRAM(unittest.TestCase):
    def test_pass(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, tile_files={
                'track_tiles.c':  'const uint8_t track_tile_data_count = 7u;\n',
                'dialog_tiles.c': 'const uint8_t dialog_border_tiles_count = 8u;\n',
            })
            used, status = memory_check._check_vram(d)
            self.assertEqual(used, 15)
            self.assertEqual(status, 'PASS')

    def test_warn(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, tile_files={
                'big_tiles.c': 'const uint8_t big_tiles_count = 308u;\n',
            })
            used, status = memory_check._check_vram(d)
            self.assertEqual(status, 'WARN')

    def test_fail(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, tile_files={
                'big_tiles.c': 'const uint8_t big_tiles_count = 384u;\n',
            })
            used, status = memory_check._check_vram(d)
            self.assertEqual(status, 'FAIL')

    def test_no_tile_files_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            used, status = memory_check._check_vram(d)
            self.assertEqual(used, 0)
            self.assertEqual(status, 'PASS')


# ── Config-constant parsing ──────────────────────────────────────────────────────

class TestParseConfig(unittest.TestCase):
    def test_parses_u_suffix(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, config_content='#define MAX_PROJECTILES 8u\n#define MAX_SPRITES 32\n')
            consts = memory_check._parse_config_constants(d)
            self.assertEqual(consts['MAX_PROJECTILES'], 8)
            self.assertEqual(consts['MAX_SPRITES'], 32)

    def test_missing_config_file_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'src'), exist_ok=True)
            self.assertIsNone(memory_check._parse_config_constants(d))


# ── Scene breakdown ──────────────────────────────────────────────────────────────

class TestSceneBreakdown(unittest.TestCase):
    def _consts(self, **kw):
        defaults = dict(MAX_SPRITES=28, MAX_PROJECTILES=8, MAX_ENEMIES=8,
                        MAX_ENEMY_RACERS=2, MAX_PATROLS=0)
        defaults.update(kw)
        return defaults

    def test_playing_peak_sums_consumers(self):
        scenes = memory_check._scene_breakdown(self._consts())
        self.assertEqual(scenes['Playing']['peak'], _playing_peak())  # 4+8+8+8+0 = 28

    def test_overmap_and_hub_are_one(self):
        scenes = memory_check._scene_breakdown(self._consts())
        self.assertEqual(scenes['Overmap']['peak'], 1)
        self.assertEqual(scenes['Hub']['peak'], 1)

    def test_text_scenes_are_zero(self):
        scenes = memory_check._scene_breakdown(self._consts())
        self.assertEqual(scenes['Title']['peak'], 0)
        self.assertEqual(scenes['Prerace']['peak'], 0)
        self.assertEqual(scenes['Results']['peak'], 0)
        self.assertEqual(scenes['GameOver']['peak'], 0)  # blast reuses player slots

    def test_playing_lists_five_consumers(self):
        scenes = memory_check._scene_breakdown(self._consts())
        labels = [c['label'] for c in scenes['Playing']['consumers']]
        self.assertEqual(labels, ['player', 'projectiles', 'turrets', 'racers', 'patrol'])

    def test_racers_use_four_slots_each(self):
        scenes = memory_check._scene_breakdown(self._consts(MAX_ENEMY_RACERS=2))
        racers = next(c for c in scenes['Playing']['consumers'] if c['label'] == 'racers')
        self.assertEqual(racers['slots'], 8)


# ── OAM check (scene-aware) ──────────────────────────────────────────────────────

class TestCheckOAM(unittest.TestCase):
    def test_busiest_scene_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, config_content=_config())
            oam = memory_check._check_oam(d)
            self.assertEqual(oam['worst_scene'], 'Playing')
            self.assertEqual(oam['used'], _playing_peak())  # 28
            self.assertEqual(oam['budget'], 40)

    def test_pass_when_pool_matches_and_under_80pct(self):
        # peak 28, pool 28 -> crosscheck PASS, util 70% PASS
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, config_content=_config(max_sprites=28))
            oam = memory_check._check_oam(d)
            self.assertEqual(oam['crosscheck'], 'PASS')
            self.assertEqual(oam['status'], 'PASS')

    def test_util_warn_at_80pct(self):
        # peak 32, pool 32 -> crosscheck PASS but util 80% -> WARN
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, config_content=_config(max_sprites=32, patrols=1))
            oam = memory_check._check_oam(d)
            self.assertEqual(oam['used'], 32)
            self.assertEqual(oam['crosscheck'], 'PASS')
            self.assertEqual(oam['status'], 'WARN')

    def test_crosscheck_fail_when_pool_too_small(self):
        # peak 32, pool 20 -> FAIL
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, config_content=_config(max_sprites=20, patrols=1))
            oam = memory_check._check_oam(d)
            self.assertEqual(oam['crosscheck'], 'FAIL')
            self.assertEqual(oam['status'], 'FAIL')

    def test_crosscheck_warn_when_over_provisioned(self):
        # peak 28, pool 40 -> crosscheck WARN, util 70% PASS -> overall WARN
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, config_content=_config(max_sprites=40))
            oam = memory_check._check_oam(d)
            self.assertEqual(oam['crosscheck'], 'WARN')
            self.assertEqual(oam['status'], 'WARN')

    def test_util_fail_over_hardware_cap(self):
        # peak 44, pool 44 -> crosscheck PASS but util 110% -> FAIL
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, config_content=_config(max_sprites=44, proj=20, patrols=1))
            oam = memory_check._check_oam(d)
            self.assertEqual(oam['used'], 44)
            self.assertEqual(oam['status'], 'FAIL')

    def test_missing_config_file_returns_error(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'src'), exist_ok=True)
            oam = memory_check._check_oam(d)
            self.assertIsNone(oam['used'])
            self.assertEqual(oam['status'], 'ERROR')

    def test_scenes_present_in_result(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, config_content=_config())
            oam = memory_check._check_oam(d)
            self.assertIn('Playing', oam['scenes'])
            self.assertIn('Overmap', oam['scenes'])


# ── scenes_json emitter ──────────────────────────────────────────────────────────

class TestScenesJson(unittest.TestCase):
    def test_shape(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, config_content=_config())
            model = memory_check.scenes_json(d)
            self.assertEqual(model['budget'], 40)
            self.assertEqual(model['pool'], 28)
            self.assertEqual(model['worst_scene'], 'Playing')
            self.assertEqual(model['scenes']['Playing']['peak'], _playing_peak())


# ── Integration / report tests ─────────────────────────────────────────────────

class TestCheck(unittest.TestCase):
    def test_all_pass(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(
                d,
                map_content=_map_with_heap_e(0xC23D),
                tile_files={'track_tiles.c': 'const uint8_t t_count = 7u;\n'},
                config_content=_config(max_sprites=28),
            )
            result = memory_check.check(d)
            self.assertEqual(result['wram']['status'], 'PASS')
            self.assertEqual(result['vram']['status'], 'PASS')
            self.assertEqual(result['oam']['status'],  'PASS')

    def test_report_contains_scene_breakdown(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(
                d,
                map_content=_map_with_heap_e(0xC23D),
                tile_files={'track_tiles.c': 'const uint8_t t_count = 7u;\n'},
                config_content=_config(max_sprites=28),
            )
            result = memory_check.check(d)
            report = memory_check._format_report(result)
            self.assertIn('OAM', report)
            self.assertIn('Playing', report)
            self.assertIn('cross-check', report)

    def test_fail_exit_code(self):
        result = {
            'wram': {'used': 8192, 'budget': 8192, 'status': 'FAIL'},
            'vram': {'used': 10,   'budget': 384,  'status': 'PASS'},
            'oam':  {'used': 19,   'budget': 40,   'status': 'PASS'},
        }
        self.assertEqual(memory_check.overall_status(result), 'FAIL')

    def test_warn_exit_code(self):
        result = {
            'wram': {'used': 7000, 'budget': 8192, 'status': 'WARN'},
            'vram': {'used': 10,   'budget': 384,  'status': 'PASS'},
            'oam':  {'used': 19,   'budget': 40,   'status': 'PASS'},
        }
        self.assertEqual(memory_check.overall_status(result), 'WARN')

    def test_error_treated_as_fail(self):
        result = {
            'wram': {'used': None, 'budget': 8192, 'status': 'ERROR'},
            'vram': {'used': 10,   'budget': 384,  'status': 'PASS'},
            'oam':  {'used': 19,   'budget': 40,   'status': 'PASS'},
        }
        self.assertEqual(memory_check.overall_status(result), 'FAIL')


if __name__ == '__main__':
    unittest.main()
