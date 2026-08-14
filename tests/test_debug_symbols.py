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
RELEASE_MAP = os.path.join(_ROOT, 'build', 'nuke-raider.map')
DEBUG_MAP = os.path.join(_ROOT, 'build', 'debug', 'nuke-raider.map')

_DEF = re.compile(r'^DEF\s+(_\w+)\s+(0x[0-9A-Fa-f]+)', re.M)
_ANY_DEF = re.compile(r'^DEF\s+(\S+)\s+(0x[0-9A-Fa-f]+)', re.M)
_MAP_SYM = re.compile(r'([0-9A-Fa-f]{8})\s+(\S+)')

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


def _all_symbols(noi_path):
    """Every DEF name in a .noi, with no address filter and no underscore requirement.

    `_wram_symbols` cannot be used here: it drops everything outside WRAM, which is every
    mailbox symbol (ROM code / ROM data at a bank-30 address), and it drops `.STACK`, which
    has no leading underscore.
    """
    with open(noi_path, encoding='utf-8') as f:
        return {name: int(addr, 16) for name, addr in _ANY_DEF.findall(f.read())}


def _map_symbol(map_path, name):
    """One symbol's address out of a .map file."""
    with open(map_path, encoding='utf-8') as f:
        for addr, sym in _MAP_SYM.findall(f.read()):
            if sym == name:
                return int(addr, 16)
    raise AssertionError(f'{name} not found in {map_path}')


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


class _NeedsBothRoms(unittest.TestCase):
    """Shared skip guard. CI and the commit hook run with no ROM built at all."""

    def setUp(self):
        for path in (RELEASE_NOI, DEBUG_NOI, DEBUG_MAP):
            if not os.path.exists(path):
                self.skipTest(f'{path} does not exist — run `make && make build-debug`')


MAILBOX_PREFIXES = ('_debug_mailbox', '_debug_decide', '_debug_mb_',
                     '_dbg_cmd_table', '_dbg_cmd_count', '_dbg_mb_storage')


class TestTheSeamDoesNotShip(_NeedsBothRoms):
    """AC1: the release symbol file holds no mailbox name."""

    def test_no_mailbox_symbol_reaches_the_release_noi(self):
        leaked = [n for n in _all_symbols(RELEASE_NOI)
                  if any(n.startswith(p) for p in MAILBOX_PREFIXES)]
        self.assertEqual(leaked, [], f'mailbox names in the release ROM: {leaked}')

    def test_the_debug_noi_does_hold_the_mailbox(self):
        """The negative test above proves nothing unless this one passes."""
        names = _all_symbols(DEBUG_NOI)
        for wanted in ('_debug_mailbox_poll', '_debug_mailbox_start', '_debug_decide'):
            with self.subTest(symbol=wanted):
                self.assertIn(wanted, names)


class TestTheReservedStack(_NeedsBothRoms):
    """R12: linker-allocated WRAM must stay below the moved stack pointer."""

    def test_the_debug_rom_heap_end_is_below_the_stack(self):
        self.assertLess(_map_symbol(DEBUG_MAP, 's__HEAP_E'), 0xDF00,
                         'the debug ROM allocates WRAM into the reserved region')

    def test_the_debug_rom_moves_the_stack(self):
        self.assertEqual(_map_symbol(DEBUG_MAP, '.STACK'), 0xDF00)

    def test_the_release_rom_keeps_the_default_stack(self):
        self.assertEqual(_map_symbol(RELEASE_MAP, '.STACK'), 0xE000)
