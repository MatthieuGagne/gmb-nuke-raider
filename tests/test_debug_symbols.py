"""The debug symbol file holds module data the release one hides (#588 AC3).

Both files are read as text. `.noi` lines look like `DEF _name 0xC247`; the
harness accepts WRAM addresses only, which is why only mutable data matters.

The test skips when either file is absent, because `make test-tools` also runs
from the pre-commit hook, where no ROM has been built.
"""
import os
import re
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE_NOI = os.path.join(_ROOT, 'build', 'nuke-raider.noi')
DEBUG_NOI = os.path.join(_ROOT, 'build', 'debug', 'nuke-raider.noi')

_DEF = re.compile(r'^DEF\s+(_\w+)\s+(0x[0-9A-Fa-f]+)', re.M)

# The three names the spec calls out, plus every mutable file-scope variable in
# src/beam.c. beam.c is the case that made this work necessary: the LASER
# feature (#430) could not be observed by its own evidence scenario.
#
# This list had drifted: `setUp` skips the whole module unless BOTH symbol
# files exist, and CI builds only the release ROM, so nothing here ran there.
# The #582 beam refactor renamed `s_cell_tx`/`s_cell_ty`/`s_cell_count` out of
# existence without anyone noticing. Building the debug ROM for #589's
# evidence run is what finally exercised this test and exposed the drift.
REQUIRED = [
    '_ld_weapon1', '_ld_unlock_mask', '_sm_depth',
    '_beam_tile_base', '_s_equipped', '_s_cooldown', '_s_dmg_window',
    '_s_vis_frames', '_s_dirty', '_s_axis', '_s_x0', '_s_x1', '_s_y0', '_s_y1',
    '_s_lane_px', '_s_step', '_s_nose', '_s_lo_tile', '_s_count',
    '_s_drawn_lo', '_s_drawn_count', '_s_lane_tile', '_s_lane_repair',
    '_s_cast_memo_ok', '_s_cast_nose', '_s_cast_vis_lo', '_s_cast_vis_hi',
    '_s_cast_n', '_s_cast_lo', '_s_cell_buf',
]


def _wram_symbols(path):
    with open(path) as f:
        text = f.read()
    return {name for name, addr in _DEF.findall(text)
            if 0xC000 <= int(addr, 16) & 0xFFFF <= 0xDFFF}


class TestDebugSymbols(unittest.TestCase):
    def setUp(self):
        for path in (RELEASE_NOI, DEBUG_NOI):
            if not os.path.isfile(path):
                raise unittest.SkipTest('not built: %s' % path)

    def test_debug_symbol_file_holds_every_required_name(self):
        symbols = _wram_symbols(DEBUG_NOI)
        missing = [n for n in REQUIRED if n not in symbols]
        self.assertEqual(missing, [], 'missing from the debug .noi: %s' % missing)

    def test_release_symbol_file_holds_none_of_them(self):
        symbols = _wram_symbols(RELEASE_NOI)
        leaked = [n for n in REQUIRED if n in symbols]
        self.assertEqual(leaked, [], 'leaked into the release .noi: %s' % leaked)

    def test_the_release_file_still_holds_the_curated_globals(self):
        """The sweep must not have removed what already worked."""
        symbols = _wram_symbols(RELEASE_NOI)
        for name in ('_px', '_py', '_hp', '_racer_active'):
            self.assertIn(name, symbols)
