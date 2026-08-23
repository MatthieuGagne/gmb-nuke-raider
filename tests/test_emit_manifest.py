#!/usr/bin/env python3
"""Unit tests for tools/emit_manifest.py"""
import contextlib
import io
import json
import os
import sys
import unittest
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _repo(*parts):
    return os.path.join(_ROOT, *parts)


# #684 — manifest button names, as emitted, mapped to the GBDK joypad tokens
# src/player.c would have to reference to handle them.
_BUTTON_TO_J = {
    'a':      'J_A',
    'b':      'J_B',
    'up':     'J_UP',
    'down':   'J_DOWN',
    'left':   'J_LEFT',
    'right':  'J_RIGHT',
    'start':  'J_START',
    'select': 'J_SELECT',
}


def _buttons_handled_by_player_c():
    """Buttons src/player.c actually reads, comments stripped.

    src/player.c is the only button handler in the playing state — src/state_playing.c
    reads no buttons, it calls player_update(). Comments are stripped so a prose
    mention of a button never counts as a handler."""
    import re
    with open(_repo('src', 'player.c'), encoding='utf-8') as fh:
        code = fh.read()
    code = re.sub(r'/\*.*?\*/', ' ', code, flags=re.DOTALL)
    code = re.sub(r'//[^\n]*', ' ', code)
    return {btn for btn, tok in _BUTTON_TO_J.items()
            if re.search(r'\b' + tok + r'\b', code)}


def _run_main(noi_text="DEF _rs_laps 0xC1A4\nDEF _rs_cp_next 0xC1A8\n"):
    """Run emit_manifest.main() against the repo's real assets and return the
    parsed manifest. The module's only driver, so a broken payload key fails
    here instead of passing silently."""
    import emit_manifest
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.noi', delete=False)
    f.write(noi_text)
    f.close()
    argv = [
        'emit_manifest.py',
        '--noi', f.name,
        '--overmap', _repo('assets', 'maps', 'overmap.tmx'),
        '--tracks', _repo('assets', 'maps', 'track.tmx'),
                    _repo('assets', 'maps', 'track2.tmx'),
                    _repo('assets', 'maps', 'track3.tmx'),
        '--tsx', _repo('assets', 'maps', 'track.tsx'),
        '--state-overmap', _repo('src', 'state_overmap.c'),
        '--state-prerace', _repo('src', 'state_prerace.c'),
    ]
    buf = io.StringIO()
    old_argv = sys.argv
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(buf):
            emit_manifest.main()
    finally:
        sys.argv = old_argv
        os.unlink(f.name)
    return json.loads(buf.getvalue())


class TestBFS(unittest.TestCase):
    def _em(self):
        import emit_manifest
        return emit_manifest

    def test_bfs_direct_right(self):
        em = self._em()
        path = em.bfs([1, 1, 1], 3, 1, 0, 0, 2, 0)
        self.assertEqual(path, ['right', 'right'])

    def test_bfs_direct_left(self):
        em = self._em()
        path = em.bfs([1, 1, 1], 3, 1, 2, 0, 0, 0)
        self.assertEqual(path, ['left', 'left'])

    def test_bfs_blocked_returns_none(self):
        em = self._em()
        path = em.bfs([1, 0, 1], 3, 1, 0, 0, 2, 0)
        self.assertIsNone(path)

    def test_bfs_around_corner(self):
        em = self._em()
        # 2x2: (0,0)=road, (1,0)=wall, (0,1)=road, (1,1)=road
        path = em.bfs([1, 0, 1, 1], 2, 2, 0, 0, 1, 1)
        self.assertEqual(path, ['down', 'right'])

    def test_bfs_same_tile_returns_empty(self):
        em = self._em()
        path = em.bfs([1], 1, 1, 0, 0, 0, 0)
        self.assertEqual(path, [])

    def test_bfs_direct_down(self):
        em = self._em()
        # 1x3 vertical grid
        path = em.bfs([1, 1, 1], 1, 3, 0, 0, 0, 2)
        self.assertEqual(path, ['down', 'down'])


class TestParseNoi(unittest.TestCase):
    def _em(self):
        import emit_manifest
        return emit_manifest

    def _write_noi(self, content):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.noi', delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_wram_symbol_extracted(self):
        em = self._em()
        path = self._write_noi("DEF _cam_scx_shadow 0xC0B6\n")
        result = em.parse_noi(path)
        os.unlink(path)
        self.assertEqual(result.get('_cam_scx_shadow'), '0xc0b6')

    def test_rom_address_ignored(self):
        em = self._em()
        path = self._write_noi("DEF _some_func 0x04567\n")
        result = em.parse_noi(path)
        os.unlink(path)
        self.assertNotIn('_some_func', result)

    def test_missing_file_returns_empty(self):
        em = self._em()
        result = em.parse_noi('/tmp/nonexistent_emit_manifest_test.noi')
        self.assertEqual(result, {})

    def test_multiple_symbols(self):
        em = self._em()
        content = "DEF _px 0xC123\nDEF _hp 0xC124\nDEF _func 0x01234\n"
        path = self._write_noi(content)
        result = em.parse_noi(path)
        os.unlink(path)
        self.assertIn('_px', result)
        self.assertIn('_hp', result)
        self.assertNotIn('_func', result)


class TestParseTsx(unittest.TestCase):
    def _em(self):
        import emit_manifest
        return emit_manifest

    _TSX = '''<?xml version="1.0"?>
<tileset name="track" tilewidth="8" tileheight="8" tilecount="3" columns="3">
 <tile id="0"><properties><property name="type" value="TILE_WALL"/></properties></tile>
 <tile id="1"><properties><property name="type" value="TILE_ROAD"/></properties></tile>
 <tile id="2"><properties><property name="type" value="TILE_SAND"/></properties></tile>
</tileset>'''

    def test_tile_types_parsed(self):
        em = self._em()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tsx', delete=False) as f:
            f.write(self._TSX)
            path = f.name
        result = em.parse_tsx_tile_types(path)
        os.unlink(path)
        self.assertEqual(result[0], 'TILE_WALL')
        self.assertEqual(result[1], 'TILE_ROAD')
        self.assertEqual(result[2], 'TILE_SAND')


class TestParseDefine(unittest.TestCase):
    def _em(self):
        import emit_manifest
        return emit_manifest

    def _write_c(self, content):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False)
        f.write(content)
        f.close()
        return f.name

    def test_parse_integer_with_u_suffix(self):
        em = self._em()
        path = self._write_c("#define TRAVEL_FRAMES_PER_TILE 4u\n")
        self.assertEqual(em.parse_define(path, 'TRAVEL_FRAMES_PER_TILE'), 4)
        os.unlink(path)

    def test_parse_with_inline_comment(self):
        em = self._em()
        path = self._write_c("#define PR_CONFIG_ROWS 4u   /* rows 0-3 */\n")
        self.assertEqual(em.parse_define(path, 'PR_CONFIG_ROWS'), 4)
        os.unlink(path)

    def test_parse_missing_returns_none(self):
        em = self._em()
        path = self._write_c("/* no define */\n")
        self.assertIsNone(em.parse_define(path, 'MISSING'))
        os.unlink(path)

    def test_parse_does_not_match_prefix(self):
        em = self._em()
        path = self._write_c("#define PR_CONFIG_ROWS_EXTRA 99u\n")
        self.assertIsNone(em.parse_define(path, 'PR_CONFIG_ROWS'))
        os.unlink(path)


class TestCuratedSymbols(unittest.TestCase):
    def _em(self):
        import emit_manifest
        return emit_manifest

    def test_lap_and_checkpoint_symbols_are_curated(self):
        em = self._em()
        self.assertIn('_rs_laps', em.CURATED_SYMBOLS)
        self.assertIn('_rs_cp_next', em.CURATED_SYMBOLS)

    def test_dead_cp_next_entry_is_retired(self):
        # '_cp_next' never existed as a symbol: it always resolved to null.
        em = self._em()
        self.assertNotIn('_cp_next', em.CURATED_SYMBOLS)

    def test_dead_racer_active_entry_is_retired(self):
        # '_racer_active' resolved to a real address but was always 0: index 0
        # is the player's slot (PLAYER_SLOT 0u, src/config.h) and the enemy
        # loader activates slots 1 and up only (src/racer.c), so it reads 0 on
        # every track (#508).
        em = self._em()
        self.assertNotIn('_racer_active', em.CURATED_SYMBOLS)


class TestManifestSymbolEmission(unittest.TestCase):
    """Drives emit_manifest.main() for real, so a hoisted-but-unwired
    CURATED_SYMBOLS list fails here instead of passing silently."""

    def test_main_emits_curated_symbols(self):
        payload = _run_main()
        symbols = payload['symbols']
        self.assertEqual(symbols['_rs_laps'], '0xc1a4')
        self.assertEqual(symbols['_rs_cp_next'], '0xc1a8')
        self.assertNotIn('_cp_next', symbols)

    def test_the_manifest_carries_the_mailbox_addresses(self):
        payload = _run_main()
        mb = payload['mailbox']
        self.assertEqual(mb['base'], 0xDF70)
        self.assertEqual(mb['addresses']['epoch'], 0xDF77)


class TestTrackDescription(unittest.TestCase):
    """#588 R10-R12, AC7 — the per-track description the harness reasons about."""

    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

    def _repo(self, *parts):
        return os.path.join(self._ROOT, *parts)

    def _write_noi(self, content):
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.noi', delete=False)
        f.write(content)
        f.close()
        return f.name

    def _manifest(self):
        import emit_manifest as em
        noi = self._write_noi('DEF _px 0xC247\n')
        argv = ['emit_manifest.py',
                '--noi', noi,
                '--overmap', self._repo('assets', 'maps', 'overmap.tmx'),
                '--tracks', self._repo('assets', 'maps', 'track.tmx'),
                self._repo('assets', 'maps', 'track2.tmx'),
                self._repo('assets', 'maps', 'track3.tmx'),
                '--tsx', self._repo('assets', 'maps', 'track.tsx'),
                '--config', self._repo('src', 'config.h'),
                '--state-overmap', self._repo('src', 'state_overmap.c'),
                '--state-prerace', self._repo('src', 'state_prerace.c')]
        buf = io.StringIO()
        old = sys.argv
        sys.argv = argv
        try:
            with contextlib.redirect_stdout(buf):
                em.main()
        finally:
            sys.argv = old
            os.unlink(noi)
        return json.loads(buf.getvalue())

    def test_track_one_and_two_are_twenty_by_one_hundred(self):
        tracks = self._manifest()['tracks']
        for key in ('1', '2'):
            self.assertEqual(tracks[key]['size_tiles'], {'w': 20, 'h': 100})
            self.assertEqual(tracks[key]['size_px'], {'w': 160, 'h': 800})
            self.assertEqual(tracks[key]['drive_limits'],
                             {'x_min': 0, 'x_max': 144, 'y_min': 0, 'y_max': 784})
            self.assertEqual(len(tracks[key]['solid_grid']), 100)
            self.assertTrue(all(len(r) == 20 for r in tracks[key]['solid_grid']))

    def test_track_three_carries_its_own_true_size(self):
        """assets/maps/track3.tmx is 20x26, not 20x100. The manifest says so."""
        t3 = self._manifest()['tracks']['3']
        self.assertEqual(t3['size_tiles'], {'w': 20, 'h': 26})
        self.assertEqual(t3['size_px'], {'w': 160, 'h': 208})
        self.assertEqual(t3['drive_limits']['y_max'], 192)
        self.assertEqual(len(t3['solid_grid']), 26)

    def test_lap_targets_come_from_the_tmx(self):
        tracks = self._manifest()['tracks']
        self.assertEqual(tracks['1']['lap_target'], 1)
        self.assertEqual(tracks['2']['lap_target'], 3)
        self.assertEqual(tracks['3']['lap_target'], 1)

    def test_hud_scanline_comes_from_config_h(self):
        tracks = self._manifest()['tracks']
        for key in ('1', '2', '3'):
            self.assertEqual(tracks[key]['hud_scanline'], 128)

    def test_finish_line_rows_match_the_tile_data(self):
        tracks = self._manifest()['tracks']
        self.assertEqual(tracks['1']['finish_line']['ty_min'], 95)
        self.assertEqual(tracks['1']['finish_line']['ty_max'], 95)
        self.assertEqual(tracks['2']['finish_line']['ty_min'], 6)
        self.assertEqual(tracks['2']['finish_line']['ty_max'], 7)
        self.assertEqual(tracks['3']['finish_line']['ty_min'], 24)

    def test_the_grid_marks_wall_tiles_solid(self):
        manifest = self._manifest()
        self.assertEqual(manifest['solid_tile_types'], ['TILE_WALL'])
        wall = manifest['tile_legend']['TILE_WALL']
        finish = manifest['tile_legend']['TILE_FINISH']
        grid = manifest['tracks']['1']['solid_grid']
        # Track 1's outer columns are wall; its finish row carries finish tiles.
        self.assertEqual(grid[0][0], wall)
        self.assertIn(finish, grid[95])

    def test_the_grid_is_indexed_row_then_column(self):
        """solid_grid[ty][tx] — the order every consumer will assume."""
        manifest = self._manifest()
        t1 = manifest['tracks']['1']
        self.assertEqual(len(t1['solid_grid']), t1['size_tiles']['h'])
        self.assertEqual(len(t1['solid_grid'][0]), t1['size_tiles']['w'])


class TestPlayingControls(unittest.TestCase):
    """#684 — the manifest must describe the controls src/player.c implements."""

    def test_playing_has_no_accelerate_key(self):
        playing = _run_main()['controls']['playing']
        self.assertNotIn('accelerate', playing,
                         "there is no accelerate button; src/player.c maps J_A to fire")

    def test_playing_drive_covers_all_four_directions(self):
        playing = _run_main()['controls']['playing']
        self.assertIn('drive', playing,
                      "no drive key — the D-pad control the manifest must name")
        self.assertEqual(sorted(playing['drive']),
                         ['down', 'left', 'right', 'up'])

    def test_playing_fire_is_a(self):
        self.assertEqual(_run_main()['controls']['playing']['fire'], 'a')

    def test_no_two_playing_controls_share_one_button(self):
        """One physical button, one meaning. 'accelerate' and 'fire' were both
        'a', which is what made the old block internally inconsistent."""
        playing = _run_main()['controls']['playing']
        self.assertTrue(playing, "controls.playing is empty — the assertion below is vacuous")
        pressed = []
        for spec in playing.values():
            pressed.extend(spec if isinstance(spec, list) else [spec])
        self.assertCountEqual(pressed, set(pressed),
                              f"a button is claimed by two controls: {sorted(pressed)}")

    def test_playing_controls_match_the_buttons_player_c_handles(self):
        """The manifest and src/player.c must name the same button set — in both
        directions. Values that are neither str nor list are not button specs and
        are skipped: controls['prerace']['cursor_to_start'] is an int, so this
        dict family demonstrably carries non-button values."""
        handled = _buttons_handled_by_player_c()
        self.assertIn('a', handled,
                      "src/player.c parse found no J_A — the helper is broken, "
                      "not the manifest")
        playing = _run_main()['controls']['playing']
        self.assertTrue(playing, "controls.playing is empty — the assertion below is vacuous")

        claimed_by = {}
        for name, spec in playing.items():
            if isinstance(spec, str):
                buttons = [spec]
            elif isinstance(spec, list):
                buttons = spec
            else:
                continue
            for button in buttons:
                claimed_by.setdefault(button, name)

        emitted = set(claimed_by)
        unhandled = {b: claimed_by[b] for b in sorted(emitted - handled)}
        unnamed = sorted(handled - emitted)
        self.assertEqual(emitted, handled,
                         f"controls.playing and src/player.c disagree — "
                         f"emitted but not handled {unhandled}; "
                         f"handled but not emitted {unnamed}")


if __name__ == '__main__':
    unittest.main()
