"""Tests for tools/bank_post_build.py"""
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import bank_post_build


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_repo(d, noi='', makefile='CFLAGS := -Wm-ya16\n', manifest=None, src_files=None):
    """Create a minimal repo layout in temp dir d."""
    os.makedirs(os.path.join(d, 'build'), exist_ok=True)
    os.makedirs(os.path.join(d, 'src'), exist_ok=True)

    with open(os.path.join(d, 'build', 'nuke-raider.noi'), 'w') as f:
        f.write(noi)

    with open(os.path.join(d, 'Makefile'), 'w') as f:
        f.write(makefile)

    m = manifest if manifest is not None else {}
    with open(os.path.join(d, 'bank-manifest.json'), 'w') as f:
        json.dump(m, f)

    for filename, content in (src_files or {}).items():
        with open(os.path.join(d, 'src', filename), 'w') as f:
            f.write(content)


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

    def test_bank1_warn_at_100(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_BANK1_FULL)
        statuses = {r[0]: r[2] for r in result['bank_results']}
        self.assertEqual(statuses[1], 'WARN')

    def test_bank1_fail_above_100(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_BANK1_FAIL)
        statuses = {r[0]: r[2] for r in result['bank_results']}
        self.assertEqual(statuses[1], 'FAIL')

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

NOI_STATE_OVERFLOW = """\
DEF _state_playing 0x17638
DEF _state_title 0x24100
"""


class TestStateSymbols(unittest.TestCase):

    def test_state_symbols_in_bank1_ok(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATES_OK)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(result['bad_state_symbols'], [])

    def test_state_symbol_in_bank2_fail(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_OVERFLOW)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        bad = result['bad_state_symbols']
        self.assertEqual(len(bad), 1)
        self.assertIn('_state_title', bad[0][0])

    def test_state_symbol_in_bank0_ok(self):
        noi = "DEF _state_hub 0xBAB\n"
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=noi)
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


# ── Check 4: -Wm-ya capacity ───────────────────────────────────────────────────

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


class TestWmYaCapacity(unittest.TestCase):

    def test_highest_bank_below_declared(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, makefile='CFLAGS := -Wm-ya16\n')
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_3_BANKS)
        self.assertEqual(result['wm_ya_status'], 'PASS')
        self.assertEqual(result['wm_ya_declared'], 16)
        self.assertEqual(result['wm_ya_highest'], 2)

    def test_highest_bank_at_limit_is_ok(self):
        """Bank 15 is the last valid bank when -Wm-ya16 (banks 0-15)."""
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, makefile='CFLAGS := -Wm-ya16\n')
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_16_BANKS)
        self.assertEqual(result['wm_ya_status'], 'PASS')

    def test_highest_bank_exceeds_declared_fail(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, makefile='CFLAGS := -Wm-ya16\n')
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_OVERFLOW_BANKS)
        self.assertEqual(result['wm_ya_status'], 'FAIL')
        self.assertEqual(result['wm_ya_highest'], 16)
        self.assertEqual(result['wm_ya_declared'], 16)

    def test_no_wm_ya_in_makefile_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, makefile='CFLAGS := -autobank\n')
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_3_BANKS)
        self.assertEqual(result['wm_ya_status'], 'SKIP')


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

    def test_bank1_full_overall_warn(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATES_OK)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_BANK1_FULL)
        self.assertEqual(bank_post_build.overall_status(result), 'WARN')

    def test_bank1_overflow_overall_fail(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATES_OK)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_BANK1_FAIL)
        self.assertEqual(bank_post_build.overall_status(result), 'FAIL')

    def test_state_overflow_overall_fail(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_STATE_OVERFLOW)
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(bank_post_build.overall_status(result), 'FAIL')

    def test_bank_sym_mismatch_overall_fail(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, noi=NOI_BANK_SYMS_MISMATCH, manifest=MANIFEST_PINNED,
                      src_files={'npc_mechanic_portrait.c': SRC_PORTRAIT})
            result = bank_post_build.check(d, romusage_output=ROMUSAGE_HEALTHY)
        self.assertEqual(bank_post_build.overall_status(result), 'FAIL')


if __name__ == '__main__':
    unittest.main()
