#!/usr/bin/env python3
"""Unit tests for tools/emit_manifest.py"""
import contextlib
import io
import json
import os
import re
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


# #684 — the source files that read buttons in the playing state. state_playing.c
# reads none today; scanning it anyway is what keeps that a checked fact rather
# than an assumption, so a pause or menu button added there cannot leave the
# manifest silently incomplete.
_PLAYING_BUTTON_SOURCES = ('player.c', 'state_playing.c')


def _buttons_handled_by_player_c():
    """Buttons the playing-state button sources actually read, comments stripped.

    Scans every file in _PLAYING_BUTTON_SOURCES (union of matches). Comments are
    stripped from each so a prose mention of a button never counts as a handler.
    A token showing up here means it is *mentioned* in these files — not that the
    code path reading it is reachable."""
    handled = set()
    for filename in _PLAYING_BUTTON_SOURCES:
        with open(_repo('src', filename), encoding='utf-8') as fh:
            code = fh.read()
        code = re.sub(r'/\*.*?\*/', ' ', code, flags=re.DOTALL)
        code = re.sub(r'//[^\n]*', ' ', code)
        handled |= {btn for btn, tok in _BUTTON_TO_J.items()
                    if re.search(r'\b' + tok + r'\b', code)}
    return handled


def _run_main(noi_text="DEF _rs_laps 0xC1A4\nDEF _rs_cp_next 0xC1A8\n", config=None):
    """Run emit_manifest.main() against the repo's real assets and return the
    parsed manifest. The module's only driver, so a broken payload key fails
    here instead of passing silently.

    `config` overrides the src/config.h the emitter reads — #688 uses it to flip
    PLAYER_HANDLING and prove the emitted turn cost tracks the input."""
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
        '--config', config or _repo('src', 'config.h'),
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

    def test_parse_list_reads_a_brace_table(self):
        em = self._em()
        path = self._write_c(
            "#define PLAYER_TURN_FRAMES_TABLE { 8u, 7u, 6u, 5u, 4u, 3u, 2u, 1u }\n")
        self.assertEqual(em.parse_define_list(path, 'PLAYER_TURN_FRAMES_TABLE'),
                         [8, 7, 6, 5, 4, 3, 2, 1])
        os.unlink(path)

    def test_parse_list_missing_returns_none(self):
        em = self._em()
        path = self._write_c("/* no define */\n")
        self.assertIsNone(em.parse_define_list(path, 'MISSING'))
        os.unlink(path)

    def test_parse_list_does_not_match_prefix(self):
        em = self._em()
        path = self._write_c("#define TABLE_EXTRA { 9u }\n")
        self.assertIsNone(em.parse_define_list(path, 'TABLE'))
        os.unlink(path)

    def test_parse_list_missing_file_returns_none(self):
        em = self._em()
        self.assertIsNone(em.parse_define_list('does/not/exist.h', 'TABLE'))

    def test_parse_list_reads_hex_tokens(self):
        """{ 0x08u, 0x07u } is two entries, not four — re.findall(r'\\d+', ...)
        would split each hex literal's digits into separate matches."""
        em = self._em()
        path = self._write_c("#define TABLE { 0x08u, 0x07u }\n")
        self.assertEqual(em.parse_define_list(path, 'TABLE'), [8, 7])
        os.unlink(path)

    def test_parse_list_reads_negative_tokens(self):
        """{ -1, 2 } must keep the sign — a digit-run scan drops it and reads 1."""
        em = self._em()
        path = self._write_c("#define TABLE { -1, 2 }\n")
        self.assertEqual(em.parse_define_list(path, 'TABLE'), [-1, 2])
        os.unlink(path)

    def test_parse_list_ignores_commented_out_entries(self):
        """{ 8u, /* 7u */ 6u } is two live entries — the commented-out one must
        not be counted, or the table's length (and everything it indexes)
        silently shifts."""
        em = self._em()
        path = self._write_c("#define TABLE { 8u, /* 7u */ 6u }\n")
        self.assertEqual(em.parse_define_list(path, 'TABLE'), [8, 6])
        os.unlink(path)

    def test_parse_list_allows_a_trailing_comma(self):
        em = self._em()
        path = self._write_c("#define TABLE { 8u, 7u, }\n")
        self.assertEqual(em.parse_define_list(path, 'TABLE'), [8, 7])
        os.unlink(path)

    def test_parse_list_rejects_a_malformed_token(self):
        em = self._em()
        path = self._write_c("#define TABLE { 8u, seven }\n")
        self.assertIsNone(em.parse_define_list(path, 'TABLE'))
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

    # --- #688: turn latency and the eight-facing input model ---

    def _config_h_text(self):
        with open(_repo('src', 'config.h'), encoding='utf-8') as fh:
            return fh.read()

    def _config_h_handling(self):
        """Read PLAYER_HANDLING straight out of src/config.h, with this test's
        own parser. Calling emit_manifest's parser here would compare the
        emitter to itself and pass no matter what config.h says."""
        return int(re.search(r'#define\s+PLAYER_HANDLING\s+(\d+)',
                             self._config_h_text()).group(1))

    def _config_h_table(self):
        """Read PLAYER_TURN_FRAMES_TABLE with this test's own tokenizer — split
        on ',' and strip a trailing 'u'/'U' suffix per token, deliberately NOT
        emit_manifest.parse_define_list's algorithm. If the oracle and the
        emitter shared one implementation they would always agree, even when
        both are wrong (R5): the oracle has to be able to disagree with the
        emitter for this test to mean anything."""
        body = re.search(r'#define\s+PLAYER_TURN_FRAMES_TABLE\s+\{([^}]*)\}',
                         self._config_h_text()).group(1)
        tokens = [t.strip() for t in body.split(',')]
        tokens = [t for t in tokens if t]
        values = [int(t.rstrip('uU')) for t in tokens]
        self.assertEqual(len(values), 8,
                         "src/config.h:27-38 documents PLAYER_TURN_FRAMES_TABLE "
                         "as an 8-entry table")
        self.assertTrue(all(a > b for a, b in zip(values, values[1:])),
                        "src/config.h:27-38 documents PLAYER_TURN_FRAMES_TABLE "
                        "as strictly decreasing")
        return values

    def _player_c_code(self):
        """src/player.c with comments stripped, so a prose mention never counts
        as an implemented fact — the same discipline
        _buttons_handled_by_player_c() uses."""
        with open(_repo('src', 'player.c'), encoding='utf-8') as fh:
            code = fh.read()
        code = re.sub(r'/\*.*?\*/', ' ', code, flags=re.DOTALL)
        return re.sub(r'//[^\n]*', ' ', code)

    def test_turn_cost_equals_the_config_h_table_entry(self):
        """R1/R5/AC1 — the emitted frames-per-notch is PLAYER_TURN_FRAMES_TABLE
        indexed by PLAYER_HANDLING, not a number typed into the emitter."""
        expected = self._config_h_table()[self._config_h_handling()]
        facing = _run_main()['controls']['playing']['facing']
        self.assertEqual(facing['turn_frames_per_45_deg'], expected)
        self.assertEqual(facing['frames_per_180_deg'], 4 * expected)

    def test_turn_cost_follows_a_changed_player_handling(self):
        """AC3 — flip the input, not read the code. A copy of src/config.h with
        PLAYER_HANDLING moved one step must emit that neighbouring table entry.

        The flip target is derived from the current value, never hardcoded:
        src/config.h:28-32 says the shipped value is a playtesting question, and
        a hardcoded target would collide with it the day it is retuned — failing
        the whole pre-commit suite for a reason unrelated to the emitter.
        PLAYER_TURN_FRAMES_TABLE is strictly decreasing, so adjacent entries
        always differ and the assertion below stays meaningful."""
        table = self._config_h_table()
        flipped_idx = (self._config_h_handling() + 1) % len(table)
        expected = table[flipped_idx]
        self.assertNotEqual(expected, table[self._config_h_handling()],
                            "the flip must change the value or it proves nothing")
        flipped, n = re.subn(r'(#define\s+PLAYER_HANDLING\s+)\d+',
                             r'\g<1>' + str(flipped_idx), self._config_h_text(), count=1)
        self.assertEqual(n, 1, "PLAYER_HANDLING not found in src/config.h")
        f = tempfile.NamedTemporaryFile(mode='w', suffix='.h', delete=False,
                                        encoding='utf-8')
        f.write(flipped)
        f.close()
        try:
            facing = _run_main(config=f.name)['controls']['playing']['facing']
        finally:
            os.unlink(f.name)
        self.assertEqual(facing['turn_frames_per_45_deg'], expected,
                         "flipping PLAYER_HANDLING did not move the emitted value — "
                         "it is not derived from src/config.h")

    def _player_apply_physics_body(self):
        """Just player_apply_physics()'s body. Matching DIR_DX[player_dir]
        against the whole file is not a guard: src/player.c's sprite-rendering
        block indexes the same tables the same way, so a physics function
        rewritten to thrust along the pressed button would still match."""
        code = self._player_c_code()
        m = re.search(r'void\s+player_apply_physics\s*\([^)]*\)[^{]*\{', code)
        self.assertIsNotNone(m, "player_apply_physics() not found in src/player.c — "
                                "the parser is broken, not the manifest")
        # Brace-counted, not a naive `.*?\n}` regex: player_apply_physics() has
        # nested `{ ... }` blocks of its own, so the first `\n}` is an inner
        # block's closer, not the function's.
        i = m.end()
        depth = 1
        while i < len(code) and depth > 0:
            if code[i] == '{':
                depth += 1
            elif code[i] == '}':
                depth -= 1
            i += 1
        self.assertEqual(depth, 0,
                         "unbalanced braces while scanning player_apply_physics() — "
                         "the parser is broken, not the manifest")
        return code[m.end():i - 1]

    def test_thrust_follows_the_current_facing(self):
        """R2/AC2 — the fact #688 exists for: pressing a direction requests a
        facing, it does not thrust that way until the turn completes. Asserted
        against player_apply_physics()'s body only (not the whole file — see
        _player_apply_physics_body): the function must call
        turn_toward_request(buttons) and then index DIR_DX/DIR_DY by
        player_dir, and by NOTHING ELSE — a rewrite that thrusts along the
        pressed button (e.g. DIR_DX[decode_dir(buttons)]) must fail here."""
        body = self._player_apply_physics_body()
        self.assertRegex(body, r'turn_toward_request\s*\(\s*buttons\s*\)')
        self.assertRegex(body, r'DIR_DX\s*\[\s*player_dir\s*\]')
        self.assertRegex(body, r'DIR_DY\s*\[\s*player_dir\s*\]')
        subscripts = set(re.findall(r'DIR_D[XY]\s*\[\s*([^\]]+?)\s*\]', body))
        self.assertEqual(subscripts, {'player_dir'},
                         "DIR_DX/DIR_DY indexed by something other than player_dir "
                         "inside player_apply_physics() — thrust no longer follows "
                         "the car's facing")
        facing = _run_main()['controls']['playing']['facing']
        self.assertIs(facing['thrust_follows_facing'], True)

    def test_facing_count_matches_the_direction_tables(self):
        """R2/AC2 — eight facings is src/player.c's DIR_DX/DIR_DY width, not a
        number typed into the emitter. Narrow the ring in player.c and this fails."""
        code = self._player_c_code()
        widths = [int(w) for w in re.findall(r'DIR_D[XY]\s*\[\s*(\d+)\s*\]\s*=', code)]
        self.assertEqual(len(widths), 2,
                         "DIR_DX/DIR_DY declarations not found — the parser is broken, "
                         "not the manifest")
        self.assertEqual(set(widths), {8}, "the direction tables disagree on width")
        self.assertEqual(_run_main()['controls']['playing']['facing']['count'], widths[0])

    def test_diagonals_match_decode_dir(self):
        """R2/AC2 — the four two-button combos are exactly decode_dir()'s
        two-button branches (src/player.c:338-341), lowercased. Add or remove a
        diagonal in player.c and this fails."""
        combos = re.findall(
            r'\(\s*buttons\s*&\s*J_(\w+)\s*\)\s*&&\s*\(\s*buttons\s*&\s*J_(\w+)\s*\)',
            self._player_c_code())
        self.assertEqual(len(combos), 4,
                         "decode_dir() no longer has four two-button branches — "
                         "the manifest's diagonal set must follow it")
        expected = {frozenset((a.lower(), b.lower())) for a, b in combos}
        playing = _run_main()['controls']['playing']
        diagonals = playing['facing']['diagonals']
        self.assertEqual(len(diagonals), 4)
        emitted = set()
        for name, combo in diagonals.items():
            self.assertEqual(len(combo), 2,
                             f"{name} must be two drive directions held together")
            for button in combo:
                self.assertIn(button, playing['drive'],
                              f"{name} names {button!r}, which is not a drive direction")
            emitted.add(frozenset(combo))
        self.assertEqual(emitted, expected,
                         "controls.playing.facing.diagonals and decode_dir() disagree")

    # --- #694: the held-button turn rule and the facing ring order ---

    def _c_function_body(self, name):
        """Body of one src/player.c function, brace-counted, comments stripped.
        Same discipline as _player_apply_physics_body: matching a pattern
        against the whole file is not a guard, because another function could
        satisfy it."""
        code = self._player_c_code()
        m = re.search(r'void\s+' + re.escape(name) + r'\s*\([^)]*\)[^{;]*\{', code)
        self.assertIsNotNone(m, f"{name}() not found in src/player.c — "
                                "the parser is broken, not the manifest")
        i = m.end()
        depth = 1
        while i < len(code) and depth > 0:
            if code[i] == '{':
                depth += 1
            elif code[i] == '}':
                depth -= 1
            i += 1
        self.assertEqual(depth, 0,
                         f"unbalanced braces while scanning {name}() — "
                         "the parser is broken, not the manifest")
        return code[m.end():i - 1]

    def test_turn_advances_only_while_held(self):
        """R1/R6/AC1/AC4 — a turn advances only while a drive direction is
        HELD: turn_toward_request() opens with an early return when no D-pad
        bit is set, so a consumer that taps a direction and waits gets zero
        rotation. The flag is asserted against that guard, not just emitted:
        delete the guard in src/player.c and this test fails."""
        body = self._c_function_body('turn_toward_request')
        guard = re.search(
            r'if\s*\(\s*!\s*\(\s*buttons\s*&\s*\(\s*J_UP\s*\|\s*J_DOWN\s*\|\s*'
            r'J_LEFT\s*\|\s*J_RIGHT\s*\)\s*\)\s*\)\s*\{(.*?)\}',
            body, re.DOTALL)
        self.assertIsNotNone(guard,
                             "turn_toward_request() no longer guards on a held "
                             "D-pad direction — the manifest's held-button flag "
                             "must follow src/player.c")
        self.assertRegex(guard.group(1), r'\breturn\s*;',
                         "the no-direction guard no longer returns early — a "
                         "turn would advance without a held direction")
        facing = _run_main()['controls']['playing']['facing']
        self.assertIs(facing['turn_advances_only_while_held'], True)

    def _dir_table(self, name):
        """DIR_DX or DIR_DY initializer values, parsed with this test's own
        tokenizer — deliberately NOT emit_manifest machinery. The emitted ring
        is a literal, so this oracle reading src/player.c is what lets the two
        disagree (the R5 discipline #688's tests established)."""
        m = re.search(r'\b' + re.escape(name) + r'\s*\[\s*8\s*\]\s*=\s*\{([^}]*)\}',
                      self._player_c_code())
        self.assertIsNotNone(m, f"{name}[8] not found in src/player.c — "
                                "narrowed, renamed, or the parser is broken")
        values = [int(t.strip()) for t in m.group(1).split(',') if t.strip()]
        self.assertEqual(len(values), 8, f"{name} is not 8 entries wide")
        return values

    def test_ring_order_matches_the_direction_tables(self):
        """R2/R5/AC2/AC3 — entry n of the emitted ring is the direction
        DIR_DX[n]/DIR_DY[n] point, labelled with the names the manifest
        already uses (drive buttons, diagonals keys). Reorder the tables in
        src/player.c and this fails; narrow them and _dir_table fails."""
        dxs = self._dir_table('DIR_DX')
        dys = self._dir_table('DIR_DY')
        expected = []
        for dx, dy in zip(dxs, dys):
            vert = {-1: 'up', 0: '', 1: 'down'}[dy]
            horiz = {-1: 'left', 0: '', 1: 'right'}[dx]
            self.assertTrue(vert or horiz,
                            "a zero-vector ring entry is not a direction")
            expected.append(vert + '_' + horiz if vert and horiz else vert + horiz)
        facing = _run_main()['controls']['playing']['facing']
        self.assertEqual(facing['ring'], expected,
                         "controls.playing.facing.ring and DIR_DX/DIR_DY disagree")
        self.assertEqual(len(facing['ring']), facing['count'],
                         "ring length and count disagree inside one facing block")
        diagonal_labels = {n for n in facing['ring'] if '_' in n}
        self.assertEqual(diagonal_labels, set(facing['diagonals']),
                         "ring diagonal labels and the diagonals block disagree")

    def test_the_screenshot_skill_names_the_facing_fields(self):
        """#694 — the file that tells an agent what the manifest holds must name
        the facing block and its fields, spelled exactly as emitted. Misspell a
        key in the bullet (or rename one in the emitter) and this fails."""
        with open(_repo('.claude', 'skills', 'screenshot', 'SKILL.md'),
                  encoding='utf-8') as fh:
            lines = fh.readlines()
        starts = [i for i, ln in enumerate(lines)
                  if ln.lstrip().startswith('- `controls`')]
        self.assertEqual(len(starts), 1,
                         "the screenshot skill's `controls` bullet was not found "
                         "exactly once — the parser is broken, or the file moved")
        # Join the bullet with any wrapped continuation lines: a reflow with no
        # content change must not turn this test red (#694 M2).
        start = starts[0]
        end = start + 1
        while end < len(lines) and lines[end].strip() \
                and not lines[end].lstrip().startswith('- '):
            end += 1
        bullet = ' '.join(ln.strip() for ln in lines[start:end])
        self.assertIn('playing.facing', bullet)
        facing = _run_main()['controls']['playing']['facing']
        for key in ('ring', 'turn_frames_per_45_deg', 'turn_advances_only_while_held'):
            self.assertIn('`' + key + '`', bullet,
                          f"the bullet does not name {key}")
            self.assertIn(key, facing,
                          f"the bullet names {key}, which the manifest does not emit")

    def test_the_facing_block_is_not_a_button_spec(self):
        """R3 — the new value is a dict. A bare string would be read as a
        one-button spec by test_playing_controls_match_the_buttons_player_c_handles
        and would break the emitted-vs-handled equality."""
        facing = _run_main()['controls']['playing']['facing']
        self.assertIsInstance(facing, dict)

    def test_no_two_playing_controls_share_one_button(self):
        """One physical button, one meaning. 'accelerate' and 'fire' were both
        'a', which is what made the old block internally inconsistent."""
        playing = _run_main()['controls']['playing']
        self.assertTrue(playing, "controls.playing is empty — the assertion below is vacuous")
        pressed = []
        for spec in playing.values():
            if isinstance(spec, str):
                pressed.append(spec)
            elif isinstance(spec, list):
                pressed.extend(spec)
            # anything else is not a button spec — controls['playing']['facing']
            # is a dict, exactly as controls['prerace']['cursor_to_start'] is an int
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
