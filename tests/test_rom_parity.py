"""Game Boy ROM banks must match in game data but differ in debug infrastructure.

Until #590, the debug ROM and release ROM held identical bytes (#588 AC2),
because DEBUG=1 changed linkage only. This test was a whole-ROM SHA256 comparison.

#590 adds a reserved stack (#590 R12, which affects bank 0) and later adds
src/debug.c (which adds code to bank 30 in the debug ROM only). These changes
end the byte-identity, deliberately.

What must still match: every bank that holds game data — banks 1, 2, and 3.
Bank 0 will differ because the reserved stack lives there. Bank 30 is asserted
in a later task, once src/debug.c exists.

The test skips when either ROM is absent, because `make test-tools` also runs
from the pre-commit hook before any ROM has been built.
"""
import hashlib
import os
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE_ROM = os.path.join(_ROOT, 'build', 'nuke-raider.gb')
DEBUG_ROM = os.path.join(_ROOT, 'build', 'debug', 'nuke-raider.gb')

BANK_SIZE = 0x4000  # 16 KB per bank
COMPARED_BANKS = (1, 2, 3)  # Game data banks only


def _sha256(data):
    """Compute SHA256 of binary data."""
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _bank(path, n):
    """Read bank n from a ROM file."""
    with open(path, 'rb') as f:
        f.seek(n * BANK_SIZE)
        return f.read(BANK_SIZE)


class RomParityTestBase(unittest.TestCase):
    """Base class to ensure both ROMs exist before running tests."""

    @classmethod
    def setUpClass(cls):
        """Verify both ROMs are built before running any test in this class."""
        for path in (RELEASE_ROM, DEBUG_ROM):
            if not os.path.isfile(path):
                raise unittest.SkipTest('not built: %s' % path)


class TestGameDataBankParity(RomParityTestBase):
    def test_the_game_data_banks_hold_the_same_bytes(self):
        """Banks 1, 2, 3 must be identical between release and debug ROMs."""
        for bank_num in COMPARED_BANKS:
            with self.subTest(bank=bank_num):
                release_bank = _bank(RELEASE_ROM, bank_num)
                debug_bank = _bank(DEBUG_ROM, bank_num)
                self.assertEqual(
                    _sha256(release_bank), _sha256(debug_bank),
                    f'bank {bank_num} differs between release and debug ROMs'
                )

    def test_bank_zero_differs_because_the_reserved_stack_lives_there(self):
        """Bank 0 must differ: it holds the reserved stack (#590 R12).

        This test is a control. If this fails (bank 0 is identical), the
        parity test above has no meaning — it would pass on identical ROMs
        and prove nothing about the intentional differences.
        """
        release_bank0 = _bank(RELEASE_ROM, 0)
        debug_bank0 = _bank(DEBUG_ROM, 0)
        self.assertNotEqual(
            _sha256(release_bank0), _sha256(debug_bank0),
            'bank 0 must differ: reserved stack is in debug ROM only'
        )


# Bank 30 comparison arrives with src/debug.c in a later task.
