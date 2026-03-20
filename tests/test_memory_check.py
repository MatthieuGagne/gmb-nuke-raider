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


# ── OAM tests ──────────────────────────────────────────────────────────────────

class TestCheckOAM(unittest.TestCase):
    def _make_config(self, max_sprites):
        return f'#define MAX_SPRITES  {max_sprites}\n'

    def test_pass(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, config_content=self._make_config(16))
            used, status = memory_check._check_oam(d)
            self.assertEqual(used, 19)
            self.assertEqual(status, 'PASS')

    def test_warn(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, config_content=self._make_config(29))
            used, status = memory_check._check_oam(d)
            self.assertEqual(status, 'WARN')

    def test_fail(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, config_content=self._make_config(37))
            used, status = memory_check._check_oam(d)
            self.assertEqual(status, 'FAIL')

    def test_missing_define_returns_zero(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, config_content='/* no MAX_SPRITES here */\n')
            used, status = memory_check._check_oam(d)
            self.assertEqual(used, 3)
            self.assertEqual(status, 'PASS')

    def test_missing_config_file_returns_error(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'src'), exist_ok=True)
            used, status = memory_check._check_oam(d)
            self.assertIsNone(used)
            self.assertEqual(status, 'ERROR')


# ── Integration / report tests ─────────────────────────────────────────────────

class TestCheck(unittest.TestCase):
    def test_all_pass(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(
                d,
                map_content=_map_with_heap_e(0xC23D),
                tile_files={'track_tiles.c': 'const uint8_t t_count = 7u;\n'},
                config_content='#define MAX_SPRITES 16\n',
            )
            result = memory_check.check(d)
            self.assertEqual(result['wram']['status'], 'PASS')
            self.assertEqual(result['vram']['status'], 'PASS')
            self.assertEqual(result['oam']['status'],  'PASS')

    def test_report_contains_pass(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(
                d,
                map_content=_map_with_heap_e(0xC23D),
                tile_files={'track_tiles.c': 'const uint8_t t_count = 7u;\n'},
                config_content='#define MAX_SPRITES 16\n',
            )
            result = memory_check.check(d)
            report = memory_check._format_report(result)
            self.assertIn('PASS', report)
            self.assertIn('WRAM', report)
            self.assertIn('VRAM', report)
            self.assertIn('OAM', report)

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
