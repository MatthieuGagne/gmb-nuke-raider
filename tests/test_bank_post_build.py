"""Tests for tools/bank_post_build.py"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import bank_post_build

SOURCE_PATH = os.path.join(os.path.dirname(__file__), '..', 'tools',
                           'bank_post_build.py')


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_repo(d, noi='', makefile='CFLAGS := -autobank\n', manifest=None,
              src_files=None, rom_code=0x04):
    """Create a minimal repo layout in temp dir d.

    `rom_code` is the cartridge header ROM-size code (0x04 = 32 banks, matching
    the real build). Pass rom_code=None to omit the ROM entirely — the case
    where capacity is undeterminable and both checks must defer.

    The default Makefile no longer carries -Wm-ya: nothing reads it any more,
    and a fixture that still declared a bank count would imply the checker
    cares. Only test_the_makefile_no_longer_influences_any_result passes a
    -Wm-ya Makefile now, and its whole point is that the value is inert.
    """
    os.makedirs(os.path.join(d, 'build'), exist_ok=True)
    os.makedirs(os.path.join(d, 'src'), exist_ok=True)

    with open(os.path.join(d, 'build', 'nuke-raider.noi'), 'w') as f:
        f.write(noi)

    with open(os.path.join(d, 'Makefile'), 'w') as f:
        f.write(makefile)

    if rom_code is not None:
        write_rom(d, code=rom_code)

    m = manifest if manifest is not None else {}
    with open(os.path.join(d, 'bank-manifest.json'), 'w') as f:
        json.dump(m, f)

    for filename, content in (src_files or {}).items():
        with open(os.path.join(d, 'src', filename), 'w') as f:
            f.write(content)


def write_rom(d, code=0x04, length=0x150):
    """Write a stub ROM into d/build whose header byte 0x148 carries *code*.

    Only the header matters to the checker, so the body is zero-filled: a real
    512 KB ROM in every test would cost disk for no added signal. `length` is a
    parameter so the truncated-header case can be exercised.
    """
    os.makedirs(os.path.join(d, 'build'), exist_ok=True)
    path = os.path.join(d, 'build', 'nuke-raider.gb')
    data = bytearray(length)
    if length > bank_post_build.ROM_SIZE_OFFSET:
        data[bank_post_build.ROM_SIZE_OFFSET] = code
    with open(path, 'wb') as fh:
        fh.write(bytes(data))
    return path


# ── Capacity source: the cartridge header ──────────────────────────────────────

class TestRomCapacity(unittest.TestCase):
    """The bound comes from the ROM the build actually produced (#487 R1)."""

    def test_every_size_code_makebin_emits_maps_to_a_bank_count(self):
        expected = {0x00: 2, 0x01: 4, 0x02: 8, 0x03: 16, 0x04: 32,
                    0x05: 64, 0x06: 128, 0x07: 256, 0x08: 512}
        for code, banks in expected.items():
            with self.subTest(code=code):
                with tempfile.TemporaryDirectory() as d:
                    path = write_rom(d, code=code)
                    self.assertEqual(bank_post_build._read_rom_capacity(path),
                                     banks)

    def test_this_projects_real_header_reads_as_32_banks(self):
        """0x148=0x04 is what build/nuke-raider.gb actually carries — 512 KB
        auto-sized by makebin, the number -Wm-ya32 only coincides with."""
        with tempfile.TemporaryDirectory() as d:
            path = write_rom(d, code=0x04)
            self.assertEqual(bank_post_build._read_rom_capacity(path), 32)

    def test_missing_rom_defers(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'build', 'nuke-raider.gb')
            self.assertIsNone(bank_post_build._read_rom_capacity(path))

    def test_truncated_rom_defers(self):
        """A file too short to contain the header cannot answer the question."""
        with tempfile.TemporaryDirectory() as d:
            path = write_rom(d, code=0x04, length=0x100)
            self.assertIsNone(bank_post_build._read_rom_capacity(path))

    def test_unmapped_size_code_defers_rather_than_guessing(self):
        """0x52 is a legacy code makebin never emits. R3 forbids inventing a
        bound, so an unrecognised code must defer, not fall back to a default."""
        with tempfile.TemporaryDirectory() as d:
            path = write_rom(d, code=0x52)
            self.assertIsNone(bank_post_build._read_rom_capacity(path))

    def test_capacity_is_never_zero_or_one(self):
        """Task 2 deletes the old `declared=0 must defer` regression test, and
        it is only safe to delete because this holds: the smallest code maps to
        2 banks, so a non-None capacity is always >= 2 and the `limit = 0` case
        that test guarded is unreachable from this source."""
        for code in range(0x00, bank_post_build.ROM_SIZE_CODE_MAX + 1):
            with self.subTest(code=code):
                with tempfile.TemporaryDirectory() as d:
                    path = write_rom(d, code=code)
                    self.assertGreaterEqual(
                        bank_post_build._read_rom_capacity(path), 2)

    def test_no_hardcoded_bank_count_fallback_in_the_function(self):
        """R3 has no behavioural hole once the three defer tests above pass, so
        this pins the shape instead: inside _read_rom_capacity every non-derived
        return is None. Scoped to the function body — a whole-file regex would
        match `return 2 << code` (the derivation) and fail on correct code."""
        with open(SOURCE_PATH, encoding='utf-8') as fh:
            src = fh.read()
        body = src[src.index('def _read_rom_capacity'):]
        body = body[:body.index('\ndef ', 1)]
        self.assertEqual(body.count('return None'), 3)
        self.assertNotRegex(body, r'return\s+(?!2\s*<<)\d+\b')


ROMUSAGE_HEALTHY = """\
Bank         Range                Size     Used  Used%     Free  Free%
--------     ----------------  -------  -------  -----  -------  -----
ROM_0        0x0000 -> 0x3FFF    16384     9488    58%     6896    42%
ROM_1        0x4000 -> 0x7FFF    16384    14745    90%     1639    10%
ROM_2        0x4000 -> 0x7FFF    16384      788     5%    15596    95%
"""

ROMUSAGE_BANK1_WARN = """\
ROM_0        0x0000 -> 0x3FFF    16384     9488    58%     6896    42%
ROM_1        0x4000 -> 0x7FFF    16384    15728    96%      656     4%
"""

ROMUSAGE_BANK1_FULL = """\
ROM_0        0x0000 -> 0x3FFF    16384     9488    58%     6896    42%
ROM_1        0x4000 -> 0x7FFF    16384    16384   100%        0     0%
"""

ROMUSAGE_BANK1_FAIL = """\
ROM_0        0x0000 -> 0x3FFF    16384     9488    58%     6896    42%
ROM_1        0x4000 -> 0x7FFF    16384    16500   101%        0     0%
"""

ROMUSAGE_OTHER_WARN = """\
ROM_0        0x0000 -> 0x3FFF    16384     9488    58%     6896    42%
ROM_2        0x4000 -> 0x7FFF    16384    13926    85%     2458    15%
"""


class TestRomusageBudget(unittest.TestCase):

    def test_healthy_all_pass(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        statuses = {r[0]: r[2] for r in result['bank_results']}
        self.assertEqual(statuses[0], 'PASS')
        self.assertEqual(statuses[1], 'PASS')
        self.assertEqual(statuses[2], 'PASS')

    def test_bank1_at_90_is_pass(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        statuses = {r[0]: r[2] for r in result['bank_results']}
        self.assertEqual(statuses[1], 'PASS')  # exactly 90% is PASS, >90% is WARN

    def test_bank1_warn_above_90(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_BANK1_WARN)
        statuses = {r[0]: r[2] for r in result['bank_results']}
        self.assertEqual(statuses[1], 'WARN')

    # A bank that rounds to 100% but still links is WARN, not FAIL (43491d8):
    # romusage runs after the linker, so a genuine overflow has already failed
    # the build. WARN keeps the signal without blocking the post-build gate.

    def test_bank1_warn_at_100(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_BANK1_FULL)
        statuses = {r[0]: r[2] for r in result['bank_results']}
        self.assertEqual(statuses[1], 'WARN')

    def test_bank1_warn_above_100(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_BANK1_FAIL)
        statuses = {r[0]: r[2] for r in result['bank_results']}
        self.assertEqual(statuses[1], 'WARN')

    def test_other_bank_warn_above_80(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_OTHER_WARN)
        statuses = {r[0]: r[2] for r in result['bank_results']}
        self.assertEqual(statuses[2], 'WARN')


# ── Check 2: state symbols ─────────────────────────────────────────────────────

NOI_STATES_OK = """\
DEF _state_playing 0x17638
DEF _state_title 0x176A0
DEF _state_hub 0xBAB
"""

NOI_STATE_BANK3 = """\
DEF _state_playing 0x17638
DEF _state_title 0x34100
"""

NOI_STATE_BANK31 = """\
DEF _state_playing 0x17638
DEF _state_title 0x1F0000
"""

NOI_STATE_BANK32 = """\
DEF _state_playing 0x17638
DEF _state_title 0x200000
"""

NOI_STATE_BANK16 = """\
DEF _state_playing 0x17638
DEF _state_title 0x100000
"""

NOI_STATE_IN_BANK2 = """\
DEF _state_playing 0x17638
DEF _state_results 0x24100
"""

NOI_STATE_BANK0 = """\
DEF _state_hub 0xBAB
"""

# Banks 2 and 3: where autobank actually places state code on today's build.
NOI_STATE_BANKS_2_AND_3 = """\
DEF _state_playing 0x24100
DEF _state_title 0x34100
DEF _state_hub 0xBAB
"""


class TestStateSymbols(unittest.TestCase):

    def test_state_symbols_in_bank1_ok(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATES_OK)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(result['bad_state_symbols'], [])

    def test_state_symbol_in_bank3_is_now_ok(self):
        """Bank 3 was the reported FAIL (#461). invoke() dispatch is bank-agnostic,
        so bank 3 is as safe as bank 2 — the old ceiling was a snapshot, not a rule."""
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_BANK3)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(result['bad_state_symbols'], [])

    def test_sram_makefile_does_not_flag_a_healthy_rom(self):
        """AC1, the regression that motivates #487. A ROM with 32 real banks and
        state code in banks 1-3 is healthy. Under the old -Wm-ya-derived bound,
        the roadmap's `-Wm-ya1` shrank capacity to 1 bank and flagged every state
        symbol above bank 0 while check 4 FAILed on the same coincidence. Neither
        check may react to the Makefile at all now."""
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_BANKS_2_AND_3,
                      makefile='CFLAGS := -Wm-yt1b -Wm-ya1\n', rom_code=0x04)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(result['bad_state_symbols'], [])
        self.assertEqual(result['capacity_status'], 'PASS')
        self.assertEqual(result['rom_capacity'], 32)
        self.assertEqual(bank_post_build.overall_status(result), 'PASS')

    def test_the_makefile_no_longer_influences_any_result(self):
        """R2 in one assertion: identical repos differing only in their Makefile
        must produce identical results — including a Makefile with no -Wm-ya at
        all. This is what makes it impossible to fix one check and leave the
        other reading the flag."""
        results = []
        for makefile in ('CFLAGS := -Wm-ya1\n', 'CFLAGS := -Wm-ya32\n',
                         'CFLAGS := -autobank\n'):
            with tempfile.TemporaryDirectory() as d:
                make_repo(d, noi=NOI_STATE_BANKS_2_AND_3, makefile=makefile)
                results.append(bank_post_build.check(
                    d, romusage_output=ROMUSAGE_HEALTHY))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])

    def test_state_symbol_at_highest_real_bank_ok(self):
        """AC2, lower side: 32 banks means banks 0..31, so bank 31 is legal."""
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_BANK31, rom_code=0x04)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(result['bad_state_symbols'], [])

    def test_state_symbol_beyond_real_capacity_fails(self):
        """AC2, upper side: bank 32 on a 32-bank cart does not exist."""
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_BANK32, rom_code=0x04)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        bad = result['bad_state_symbols']
        self.assertEqual(len(bad), 1)
        self.assertIn('_state_title', bad[0][0])

    def test_bound_follows_the_cartridge_not_a_constant(self):
        """The same symbol that passes on a 32-bank cart must FAIL on a 16-bank
        one. This is what proves the bound is derived rather than hardcoded."""
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_BANK16, rom_code=0x03)   # 16 banks
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(len(result['bad_state_symbols']), 1)

        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_BANK16, rom_code=0x04)   # 32 banks
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(result['bad_state_symbols'], [])

    def test_no_rom_defers_both_checks(self):
        """R3: with no ROM there is no capacity, so both checks defer rather
        than inventing a bound. Replaces the old no--Wm-ya deferral case."""
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_BANK32, rom_code=None)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(result['bad_state_symbols'], [])
        self.assertEqual(result['capacity_status'], 'SKIP')
        self.assertIsNone(result['rom_capacity'])
        self.assertEqual(bank_post_build.overall_status(result), 'PASS')

    def test_unreadable_size_code_defers_both_checks(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_BANK32, rom_code=0x52)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(result['bad_state_symbols'], [])
        self.assertEqual(result['capacity_status'], 'SKIP')

    def test_state_check_is_the_only_signal_when_romusage_is_unavailable(self):
        """The non-redundancy case, and the exact condition that hid #461 for
        months. With no romusage output there are no banks, so the check-4 half
        returns PASS and the .noi-derived state check is the only capacity signal
        left. Reading capacity from the ROM header rather than the bank table is
        what keeps this case answerable at all.
        """
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_BANK32, rom_code=0x04)
            result = bank_post_build.check(d, romusage_output='')
        self.assertEqual(result['capacity_status'], 'PASS')
        self.assertEqual(len(result['bad_state_symbols']), 1)
        self.assertEqual(bank_post_build.overall_status(result), 'FAIL')

    def test_state_symbol_in_bank2_ok(self):
        """State symbols in bank 2 are allowed — invoke() uses .bank field for safe dispatch."""
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_IN_BANK2)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(result['bad_state_symbols'], [])

    def test_state_symbol_in_bank0_ok(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_BANK0)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(result['bad_state_symbols'], [])


# ── Check 3: __bank_ symbols ───────────────────────────────────────────────────

NOI_BANK_SYMS_OK = """\
DEF ___bank_npc_mechanic_portrait 0x2
DEF ___bank_track_tile_data 0x1
"""

NOI_BANK_SYMS_MISMATCH = """\
DEF ___bank_npc_mechanic_portrait 0x1
"""

MANIFEST_PINNED = {
    'src/npc_mechanic_portrait.c': {'bank': 2, 'reason': 'pinned'},
    'src/track_tiles.c': {'bank': 255, 'reason': 'autobank'},
}

SRC_PORTRAIT = "/* npc portrait */\nvolatile uint8_t __at(2) __bank_npc_mechanic_portrait;\n"
SRC_TRACK = "#pragma bank 255\nvolatile uint8_t __at(1) __bank_track_tile_data;\n"


class TestBankSymbols(unittest.TestCase):

    def test_pinned_bank_matches_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_BANK_SYMS_OK, manifest=MANIFEST_PINNED,
                      src_files={'npc_mechanic_portrait.c': SRC_PORTRAIT,
                                 'track_tiles.c': SRC_TRACK})
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(result['bank_sym_errors'], [])

    def test_pinned_bank_mismatch_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_BANK_SYMS_MISMATCH, manifest=MANIFEST_PINNED,
                      src_files={'npc_mechanic_portrait.c': SRC_PORTRAIT})
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(len(result['bank_sym_errors']), 1)
        self.assertIn('npc_mechanic_portrait', result['bank_sym_errors'][0])

    def test_autobank_255_skipped(self):
        """Autobank (bank=255) symbols are not cross-checked — bank is assigned at link time."""
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_BANK_SYMS_OK, manifest=MANIFEST_PINNED,
                      src_files={'npc_mechanic_portrait.c': SRC_PORTRAIT,
                                 'track_tiles.c': SRC_TRACK})
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(result['bank_sym_errors'], [])


# ── Check 4: ROM capacity ──────────────────────────────────────────────────────

ROMUSAGE_3_BANKS = """\
ROM_0        0x0000 -> 0x3FFF    16384     9488    58%     6896    42%
ROM_1        0x4000 -> 0x7FFF    16384    14745    90%     1639    10%
ROM_2        0x4000 -> 0x7FFF    16384      788     5%    15596    95%
"""

ROMUSAGE_16_BANKS = """\
ROM_0        0x0000 -> 0x3FFF    16384     9488    58%     6896    42%
ROM_15       0x4000 -> 0x7FFF    16384      100     1%    16284    99%
"""

ROMUSAGE_OVERFLOW_BANKS = """\
ROM_0        0x0000 -> 0x3FFF    16384     9488    58%     6896    42%
ROM_16       0x4000 -> 0x7FFF    16384      100     1%    16284    99%
"""


class TestCapacity(unittest.TestCase):

    def test_highest_bank_below_capacity(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, rom_code=0x03)          # 16 banks
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_3_BANKS)
        self.assertEqual(result['capacity_status'], 'PASS')
        self.assertEqual(result['rom_capacity'], 16)
        self.assertEqual(result['highest_bank'], 2)

    def test_highest_bank_at_limit_is_ok(self):
        """AC2, lower side for check 4: 16 banks means bank 15 is the last valid one."""
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, rom_code=0x03)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_16_BANKS)
        self.assertEqual(result['capacity_status'], 'PASS')

    def test_highest_bank_exceeds_capacity_fail(self):
        """AC2, upper side for check 4."""
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, rom_code=0x03)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_OVERFLOW_BANKS)
        self.assertEqual(result['capacity_status'], 'FAIL')
        self.assertEqual(result['highest_bank'], 16)
        self.assertEqual(result['rom_capacity'], 16)

    def test_no_rom_skips(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, rom_code=None)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_3_BANKS)
        self.assertEqual(result['capacity_status'], 'SKIP')

    def test_report_names_the_capacity_source_truthfully(self):
        """AC3's report requirement, pinned at the unit level: the line must say
        where the number came from, and must not claim the Makefile declared it."""
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATES_OK, rom_code=0x04)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_3_BANKS)
        report = bank_post_build._format_report(result)
        self.assertIn('ROM capacity: OK — 32 banks (cartridge header 0x148)',
                      report)
        self.assertIn('highest bank in use 2', report)
        self.assertNotIn('-Wm-ya', report)
        self.assertNotIn('declared', report)

    def test_skip_report_says_why_it_could_not_tell(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATES_OK, rom_code=None)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_3_BANKS)
        report = bank_post_build._format_report(result)
        self.assertIn('ROM capacity: SKIP', report)
        self.assertIn('cartridge header unreadable', report)
        self.assertNotIn('-Wm-ya', report)


# ── Overall exit code ─────────────────────────────────────────────────────────

class TestOverallStatus(unittest.TestCase):

    def test_all_pass_overall_pass(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATES_OK)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(bank_post_build.overall_status(result), 'PASS')

    def test_warn_no_fail_overall_warn(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATES_OK)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_BANK1_WARN)
        self.assertEqual(bank_post_build.overall_status(result), 'WARN')

    # Bank pressure alone never escalates to FAIL (43491d8) — see the
    # TestRomusageBudget notes. Only state-symbol, __bank_ and ROM-capacity
    # problems produce an overall FAIL.

    def test_bank1_full_overall_warn(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATES_OK)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_BANK1_FULL)
        self.assertEqual(bank_post_build.overall_status(result), 'WARN')

    def test_bank1_overflow_overall_warn(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATES_OK)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_BANK1_FAIL)
        self.assertEqual(bank_post_build.overall_status(result), 'WARN')

    def test_state_overflow_overall_fail(self):
        """A state symbol beyond real capacity still drives overall FAIL."""
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_BANK32, rom_code=0x04)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(bank_post_build.overall_status(result), 'FAIL')

    def test_bank_sym_mismatch_overall_fail(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_BANK_SYMS_MISMATCH, manifest=MANIFEST_PINNED,
                      src_files={'npc_mechanic_portrait.c': SRC_PORTRAIT})
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(bank_post_build.overall_status(result), 'FAIL')


class RunRomusageTests(unittest.TestCase):
    """_run_romusage was never exercised, so a hardcoded Linux path stayed
    green for months while `make bank-post-build` could not run at all (#441).
    These tests are the reason that cannot recur."""

    def test_resolves_the_binary_from_path(self):
        seen = {}

        def fake_run(argv, **kwargs):
            seen['argv'] = argv
            return subprocess.CompletedProcess(argv, 0, stdout='out', stderr='')

        with mock.patch('shutil.which', return_value='/somewhere/bin/romusage') as which, \
             mock.patch.object(bank_post_build.subprocess, 'run', fake_run):
            out = bank_post_build._run_romusage('build/nuke-raider.gb')

        which.assert_called_once_with('romusage')
        self.assertEqual(seen['argv'], ['/somewhere/bin/romusage',
                                        'build/nuke-raider.gb', '-a'])
        self.assertEqual(out, 'out')

    def test_missing_binary_raises_an_actionable_error(self):
        with mock.patch('shutil.which', return_value=None):
            with self.assertRaises(FileNotFoundError) as cm:
                bank_post_build._run_romusage('build/nuke-raider.gb')
        self.assertIn('PATH', str(cm.exception))

    def test_source_holds_no_absolute_binary_path(self):
        with open(SOURCE_PATH, encoding='utf-8') as fh:
            src = fh.read()
        self.assertNotRegex(src, r"['\"][A-Za-z]:[\\/]|['\"]/(home|opt|usr)/")

    def test_check_invokes_romusage_when_no_output_is_injected(self):
        # The gap this closes: check()'s romusage_output override was the only
        # path any test ever took.
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            with mock.patch.object(bank_post_build, '_run_romusage',
                                   return_value=ROMUSAGE_HEALTHY) as run:
                bank_post_build.check(d)
            run.assert_called_once()


if __name__ == '__main__':
    unittest.main()
