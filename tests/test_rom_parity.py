"""Game Boy ROM banks must match in game data but differ in debug infrastructure.

Until #590, the debug ROM and release ROM held identical bytes (#588 AC2),
because DEBUG=1 changed linkage only. This test was a whole-ROM SHA256 comparison.

#590 adds a reserved stack (#590 R12, which affects bank 0) and src/debug.c (which
adds code to bank 30 in the debug ROM only, and whose two BANKED entry points —
debug_mailbox_start/debug_mailbox_poll — cost a HOME-bank trampoline). These
changes end the byte-identity, deliberately.

AC11's original invariant was literal byte-identity for banks 1, 2 and 3. That is
unachievable the moment a module with BANKED entry points joins the link: SDCC
gives every BANKED function a small HOME-bank trampoline, which shifts the address
of every HOME routine placed after it in the link, and banked (bank 1-3) code
calls HOME routines with an absolute 16-bit operand. So an absolute call/jump into
a shifted HOME address flips its 2-byte operand between the release and debug
ROMs, even though the calling code itself — and the routine it calls — are both
byte-identical. Confirmed on this codebase: the only new HOME symbol the debug ROM
gains is the trampoline for debug.c's two BANKED functions, and every differing
byte in banks 1-3 is one half of a shifted call-target operand (verified by symbol
table cross-reference, e.g. `_sfx_play` moves from 0x12AB to 0x151F, `_state_pop`
from 0x15E1 to 0x1397, and the calling opcode immediately before each shifted
operand is unchanged).

AC11's *intent* — the debug ROM is the same game — is still fully testable without
byte-identity. What must hold for banks 1, 2 and 3: every differing byte lies in a
maximal 2-byte run, immediately preceded by an SM83 absolute call/jump opcode, and
both the release and the debug 16-bit operand resolve to a HOME address (< 0x4000).
A run longer than 2 bytes, an opcode that isn't a call/jump, or an operand landing
outside HOME would all mean real code moved or changed — not a relocation. A total
differing-byte budget across the three banks caps how much "benign" relocation is
tolerated, so a real code change cannot hide inside a pile of legitimate ones.

Bank 0 will always differ: it holds the reserved stack, and (once BANKED entry
points exist) the HOME trampoline table. Bank 30 is asserted in a later task
(Task 5), once main.c actually calls into it — right now it would be all-filler
in the release ROM and near-empty in the debug ROM, which proves nothing.

The test skips when either ROM is absent, because `make test-tools` also runs
from the pre-commit hook before any ROM has been built.
"""
import hashlib
import os
import struct
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE_ROM = os.path.join(_ROOT, 'build', 'nuke-raider.gb')
DEBUG_ROM = os.path.join(_ROOT, 'build', 'debug', 'nuke-raider.gb')

BANK_SIZE = 0x4000  # 16 KB per bank
COMPARED_BANKS = (1, 2, 3)  # Game data banks only
HOME_BANK_LIMIT = 0x4000  # Addresses below this are HOME (bank 0), always mapped

# SM83 opcodes that take an absolute 16-bit call/jump operand: CALL nn, JP nn, and
# their four condition-coded forms each (NZ/Z/NC/C).
ABSOLUTE_CALL_JUMP_OPCODES = {
    0xC2, 0xC3, 0xC4, 0xCA, 0xCC, 0xCD, 0xD2, 0xD4, 0xDA, 0xDC,
}

# How many differing bytes across banks 1-3 are tolerated as HOME-address
# relocations before a failure is raised. Today it is 32 (16 bank-1 relocations
# is the largest single-bank run of the three); the cap leaves headroom for
# small future growth in HOME-bank call sites without hiding a real regression.
MAX_TOTAL_DIFF_BYTES = 64


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


def _consecutive_runs(offsets):
    """Group a sorted list of distinct integer offsets into maximal consecutive runs.

    Returns a list of (start_offset, run_length) pairs.
    """
    runs = []
    start = prev = None
    for off in offsets:
        if start is None:
            start = prev = off
            continue
        if off == prev + 1:
            prev = off
            continue
        runs.append((start, prev - start + 1))
        start = prev = off
    if start is not None:
        runs.append((start, prev - start + 1))
    return runs


class RomParityTestBase(unittest.TestCase):
    """Base class to ensure both ROMs exist before running tests."""

    @classmethod
    def setUpClass(cls):
        """Verify both ROMs are built before running any test in this class."""
        for path in (RELEASE_ROM, DEBUG_ROM):
            if not os.path.isfile(path):
                raise unittest.SkipTest('not built: %s' % path)


class TestGameDataBankParity(RomParityTestBase):
    def test_the_game_data_banks_differ_only_in_home_bank_relocations(self):
        """Banks 1, 2, 3 must differ only where a BANKED trampoline shifted a HOME
        call/jump target — never in real code.

        Every differing byte must belong to a 2-byte run, immediately preceded by
        an SM83 absolute call/jump opcode, whose release AND debug operand both
        resolve to a HOME address (< 0x4000). The total differing-byte count across
        the three banks must stay within the relocation budget.
        """
        total_diff_bytes = 0
        for bank_num in COMPARED_BANKS:
            with self.subTest(bank=bank_num):
                release_bank = _bank(RELEASE_ROM, bank_num)
                debug_bank = _bank(DEBUG_ROM, bank_num)
                offsets = [
                    i for i in range(len(release_bank))
                    if release_bank[i] != debug_bank[i]
                ]
                total_diff_bytes += len(offsets)
                runs = _consecutive_runs(offsets)

                for start, length in runs:
                    self.assertEqual(
                        length, 2,
                        f'bank {bank_num}: a {length}-byte differing run at offset '
                        f'{start:#06x} is not a 2-byte relocation — real code '
                        f'changed ({len(offsets)} differing bytes found in this bank)'
                    )

                    opcode_offset = start - 1
                    self.assertGreaterEqual(
                        opcode_offset, 0,
                        f'bank {bank_num}: the differing run at offset {start:#06x} '
                        f'has no preceding byte to hold a call/jump opcode'
                    )
                    self.assertEqual(
                        release_bank[opcode_offset], debug_bank[opcode_offset],
                        f'bank {bank_num}: the opcode byte at {opcode_offset:#06x} '
                        f'itself differs between the two ROMs, so the run at '
                        f'{start:#06x} is not a pure operand relocation'
                    )
                    opcode = release_bank[opcode_offset]
                    self.assertIn(
                        opcode, ABSOLUTE_CALL_JUMP_OPCODES,
                        f'bank {bank_num}: the byte before the differing run at '
                        f'{start:#06x} is {opcode:#04x}, not an SM83 absolute '
                        f'call/jump opcode'
                    )

                    rel_target = struct.unpack_from('<H', release_bank, start)[0]
                    dbg_target = struct.unpack_from('<H', debug_bank, start)[0]
                    self.assertLess(
                        rel_target, HOME_BANK_LIMIT,
                        f'bank {bank_num}: release call target {rel_target:#06x} '
                        f'at offset {start:#06x} is not a HOME address — a banked '
                        f'target moved, which is a different, real problem'
                    )
                    self.assertLess(
                        dbg_target, HOME_BANK_LIMIT,
                        f'bank {bank_num}: debug call target {dbg_target:#06x} '
                        f'at offset {start:#06x} is not a HOME address — a banked '
                        f'target moved, which is a different, real problem'
                    )

        self.assertLessEqual(
            total_diff_bytes, MAX_TOTAL_DIFF_BYTES,
            f'{total_diff_bytes} differing bytes found across banks 1-3, which '
            f'exceeds the {MAX_TOTAL_DIFF_BYTES}-byte relocation budget — a real '
            f'code change may be hiding among what looks like benign relocation'
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


# Bank 30 comparison arrives with main.c calling into it, in Task 5.
