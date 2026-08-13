"""Game Boy ROM banks must match in game data but differ in debug infrastructure.

Until #590, the debug ROM and release ROM held identical bytes (#588 AC2),
because DEBUG=1 changed linkage only. This test was a whole-ROM SHA256 comparison.

#590 adds a reserved stack (#590 R12, which affects bank 0) and src/debug.c (which
adds code to bank 30 in the debug ROM only). That first change already ends the
byte-identity deliberately: bank 0 must differ.

For banks 1-3 the intent is narrower — the debug ROM is the same game, just with a
BANKED trampoline table that has grown. Whenever a BANKED function gains a new
cross-bank caller, SDCC gives it a small HOME-bank trampoline, and every HOME
routine placed after it shifts address. Banked (bank 1-3) code holds absolute
16-bit operands into HOME (call targets, jump targets, and the two-instruction
`LD A,(nn)` / `LD rr,nn` preamble SDCC emits at a call site's first-ever target,
which loads the callee's bank number and the trampoline's HOME address). Any of
those operands can shift, and a shifted operand flips some of its bytes between
the release and debug ROMs even though the instruction itself — opcode and
all — is untouched.

Two earlier invariants for banks 1-3 both turned out to be too narrow, and #590
Task 4 is what broke each of them:

  1. **Byte-identity** (pre-#590). Dead the moment any BANKED function gains a
     new cross-bank caller — that alone costs a HOME trampoline.
  2. **Every differing run is exactly 2 bytes, preceded by an absolute call/jump
     opcode, under a fixed total-byte budget** (#590 Tasks 2-3). This held by
     accident: Task 3's relocations all happened to change both bytes of their
     operand. Run length is not a property of "is this a relocation" — it is a
     property of whether the *high* byte of the operand happens to change too
     (0x12AB -> 0x15AB touches one byte; 0x12AB -> 0x131F touches two). And a
     fixed byte budget conflates "how many bytes moved" with "how many call
     sites reference something that moved" — a property of the game's call
     graph, not of whether any code actually changed. Task 4 wires six
     previously-uncalled BANKED functions into a new debug-only caller
     (`src/debug.c`), each needing its own first-ever trampoline; that alone
     produced 429 differing bytes (252/95/82 across banks 1/2/3), all of them
     legitimate relocations, none of them a fixed byte cap anticipated.

The invariant below asserts the actual claim — every differing byte belongs to
an unchanged instruction whose absolute operand moved to another HOME address —
without assuming run length or bounding a byte count that scales with the call
graph instead of with real change:

  1. **Every differing byte is part of a relocated absolute operand.** For a
     differing offset `i`, some alignment `p` in `{i, i-1}` must have an
     unchanged opcode byte at `p-1` and both 16-bit little-endian values at
     `(p, p+1)` — one from each ROM — must be HOME addresses (< 0x4000). No
     opcode whitelist: "the opcode is unchanged" is what proves it's the same
     instruction, and it covers `CALL nn`, `JP nn`, `LD A,(nn)`, `LD rr,nn`,
     and anything else with a 16-bit absolute operand.
  2. **The relocation mapping is a consistent function.** Every
     `(release_target, debug_target)` pair found while explaining a differing
     byte is collected; if one release address maps to two different debug
     addresses, that is a code change wearing a relocation's clothes, not a
     relocation.
  3. **The number of distinct relocated targets is capped.** This replaces the
     byte budget: it measures how much of HOME actually moved, which should
     stay small, rather than how many call sites reference the part that
     moved.

Bank 30 is asserted in a later task (Task 5), once main.c actually calls into
it — right now it would be all-filler in the release ROM and near-empty in the
debug ROM, which proves nothing.

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
HOME_BANK_LIMIT = 0x4000  # Addresses below this are HOME (bank 0), always mapped

# How many distinct HOME addresses may appear relocated across banks 1-3. This
# measures how much of HOME moved (a property of the debug ROM's trampoline
# table), not how many call sites reference something that moved (a property
# of the game's call graph, which scales with feature count regardless of
# whether anything is actually wrong). Today it is 40; the cap leaves headroom
# for a handful more debug-only cross-bank call sites without hiding a real
# regression, where "real regression" means a release address that resolves
# to two different debug addresses (see check 2) or a differing byte that
# cannot be explained by any relocation at all (see check 1) — either of
# those fails long before this cap is reached.
MAX_DISTINCT_RELOCATED_TARGETS = 128


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


def _relocation_at(release_bank, debug_bank, p):
    """Test whether a 2-byte absolute operand starting at offset `p` is a valid
    HOME-address relocation: the byte immediately before it (the opcode) is
    unchanged, and both ROMs' little-endian 16-bit value at (p, p+1) resolves
    to a HOME address (< HOME_BANK_LIMIT).

    Returns (release_target, debug_target) if valid, else None.
    """
    if p < 1 or p + 1 >= len(release_bank):
        return None
    if release_bank[p - 1] != debug_bank[p - 1]:
        return None
    rel_target = release_bank[p] | (release_bank[p + 1] << 8)
    dbg_target = debug_bank[p] | (debug_bank[p + 1] << 8)
    if rel_target >= HOME_BANK_LIMIT or dbg_target >= HOME_BANK_LIMIT:
        return None
    return (rel_target, dbg_target)


def _classify_bank_diff(release_bank, debug_bank):
    """Classify every differing byte between release_bank and debug_bank.

    A differing byte at offset `i` may be either half of a 2-byte absolute
    operand: the low byte (operand starts at `p = i`) or the high byte
    (operand starts at `p = i - 1`). Either alignment that satisfies
    `_relocation_at` explains the byte.

    Returns (unexplained_offsets, relocations):
      - unexplained_offsets: differing byte offsets with no valid relocation
        alignment — these mean real code changed, not merely moved.
      - relocations: list of (offset, release_target, debug_target) for every
        differing byte that IS explained by a relocation.
    """
    unexplained = []
    relocations = []
    for i in range(len(release_bank)):
        if release_bank[i] == debug_bank[i]:
            continue
        found = _relocation_at(release_bank, debug_bank, i)
        if found is None:
            found = _relocation_at(release_bank, debug_bank, i - 1)
        if found is None:
            unexplained.append(i)
        else:
            relocations.append((i, found[0], found[1]))
    return unexplained, relocations


def _aggregate_relocations(all_relocations):
    """Fold a list of (bank, offset, release_target, debug_target) relocation
    events into a release_target -> debug_target mapping, and report any
    conflict where one release address resolves to two different debug
    addresses.

    Returns (mapping, conflicts):
      - mapping: dict release_target -> (debug_target, bank, offset) of the
        first sighting.
      - conflicts: list of (release_target, first_debug_target, first_bank,
        first_offset, other_debug_target, other_bank, other_offset).
    """
    mapping = {}
    conflicts = []
    for bank_num, off, rel_t, dbg_t in all_relocations:
        if rel_t in mapping:
            prev_dbg, prev_bank, prev_off = mapping[rel_t]
            if prev_dbg != dbg_t:
                conflicts.append(
                    (rel_t, prev_dbg, prev_bank, prev_off, dbg_t, bank_num, off)
                )
        else:
            mapping[rel_t] = (dbg_t, bank_num, off)
    return mapping, conflicts


class RomParityTestBase(unittest.TestCase):
    """Base class to ensure both ROMs exist before running tests."""

    @classmethod
    def setUpClass(cls):
        """Verify both ROMs are built before running any test in this class."""
        for path in (RELEASE_ROM, DEBUG_ROM):
            if not os.path.isfile(path):
                raise unittest.SkipTest('not built: %s' % path)


class TestGameDataBankParity(RomParityTestBase):
    def test_the_game_data_banks_differ_only_in_relocated_operands(self):
        """Banks 1, 2, 3 must differ only where an absolute operand moved to
        another HOME address — never in an instruction's opcode, and never in
        a way that maps one release address to two different debug addresses.
        """
        all_unexplained = []          # [(bank, offset), ...]
        all_relocations = []          # [(bank, offset, release_target, debug_target), ...]

        for bank_num in COMPARED_BANKS:
            release_bank = _bank(RELEASE_ROM, bank_num)
            debug_bank = _bank(DEBUG_ROM, bank_num)
            unexplained, relocations = _classify_bank_diff(release_bank, debug_bank)
            all_unexplained.extend((bank_num, off) for off in unexplained)
            all_relocations.extend(
                (bank_num, off, rel_t, dbg_t) for off, rel_t, dbg_t in relocations
            )

        # Check 1: every differing byte is part of a relocated absolute operand.
        if all_unexplained:
            bank_num, off = all_unexplained[0]
            msg = (
                f'{len(all_unexplained)} differing byte(s) across banks 1-3 are not '
                f'part of any relocated absolute operand (no alignment has both an '
                f'unchanged opcode byte and two HOME-address operand halves) — real '
                f'code changed. First unexplained: bank {bank_num}, offset {off:#06x}'
            )
        else:
            msg = ''
        self.assertEqual(all_unexplained, [], msg)

        # Check 2: the relocation mapping is a consistent function — one release
        # address must never resolve to two different debug addresses.
        mapping, conflicts = _aggregate_relocations(all_relocations)

        if conflicts:
            rel_t, prev_dbg, prev_bank, prev_off, dbg_t, bank_num, off = conflicts[0]
            msg = (
                f'{len(conflicts)} relocation conflict(s) found — release address '
                f'{rel_t:#06x} maps to debug address {prev_dbg:#06x} at bank '
                f'{prev_bank} offset {prev_off:#06x}, but to {dbg_t:#06x} at bank '
                f'{bank_num} offset {off:#06x}. One release address cannot relocate '
                f'to two different debug addresses — this is a code change wearing '
                f'a relocation\'s clothes'
            )
        else:
            msg = ''
        self.assertEqual(conflicts, [], msg)

        # Check 3: the number of distinct relocated HOME targets is capped — this
        # measures how much of HOME moved, not how many call sites reference it.
        self.assertLessEqual(
            len(mapping), MAX_DISTINCT_RELOCATED_TARGETS,
            f'{len(mapping)} distinct HOME targets relocated across banks 1-3, '
            f'which exceeds the {MAX_DISTINCT_RELOCATED_TARGETS}-target cap — a '
            f'real code change may be hiding among what looks like benign '
            f'relocation'
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
