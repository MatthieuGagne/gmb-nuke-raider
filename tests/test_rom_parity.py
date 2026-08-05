"""The debug ROM and the release ROM must hold the same bytes (#588 AC2).

DEBUG=1 changes linkage only: DBG_STATIC stops hiding module data so the
symbol table grows, and nothing else changes. The two .gb files are therefore
identical, and this test is what turns that claim into a check.

PRD-3 (#590) adds src/debug.c, which puts code in the debug ROM only. It ends
this test deliberately and says so in its own pull request (epic #592 R5).

The test skips when either ROM is absent, because `make test-tools` also runs
from the pre-commit hook, where no ROM has been built.
"""
import hashlib
import os
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE_ROM = os.path.join(_ROOT, 'build', 'nuke-raider.gb')
DEBUG_ROM = os.path.join(_ROOT, 'build', 'debug', 'nuke-raider.gb')


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(65536), b''):
            h.update(block)
    return h.hexdigest()


class TestRomParity(unittest.TestCase):
    def test_debug_rom_matches_release_rom(self):
        for path in (RELEASE_ROM, DEBUG_ROM):
            if not os.path.isfile(path):
                raise unittest.SkipTest('not built: %s' % path)
        self.assertEqual(_sha256(RELEASE_ROM), _sha256(DEBUG_ROM),
                         'DEBUG=1 added or removed code; it must change '
                         'linkage only (#588 AC2)')
