#!/usr/bin/env python3
"""Opcode drift tests (#590 AC9)."""

import os
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import debug_protocol as dp  # noqa: E402


# The frozen wire. A renumbered opcode breaks this list, which is the point (#590 R14).
GOLDEN = {
    'add_scrap': 1, 'unlock_field': 2, 'set_option': 3, 'damage': 4, 'heal': 5,
    'force_state': 6, 'spawn_turret': 7, 'despawn_turret': 8,
    'spawn_racer': 9, 'spawn_patrol': 10,
}

SRC = os.path.join(dp.REPO_ROOT, 'src')
DEBUG_C = os.path.join(SRC, 'debug.c')


class TestOpcodesAreAppendOnly(unittest.TestCase):
    def test_every_golden_opcode_keeps_its_number(self):
        for name, opcode in GOLDEN.items():
            with self.subTest(command=name):
                self.assertIn(name, dp.commands())
                self.assertEqual(dp.commands()[name]['opcode'], opcode)

    def test_no_opcode_is_used_twice(self):
        codes = [c['opcode'] for c in dp.commands().values()]
        self.assertEqual(len(codes), len(set(codes)))

    def test_a_new_command_takes_the_next_free_number(self):
        """Append-only: a command outside GOLDEN must number above every golden one."""
        highest = max(GOLDEN.values())
        for name, spec in dp.commands().items():
            if name not in GOLDEN:
                with self.subTest(command=name):
                    self.assertGreater(spec['opcode'], highest)

    def test_opcode_zero_is_never_a_command(self):
        self.assertNotIn(0, [c['opcode'] for c in dp.commands().values()])

    def test_every_command_has_named_arguments(self):
        for name in dp.commands():
            with self.subTest(command=name):
                self.assertIn(name, dp.ARG_NAMES)


class TestCTableMatchesTheDefFile(unittest.TestCase):
    """AC9: a test must fail when the C table and debug_cmds.def disagree.

    The check runs the real preprocessor over src/debug.c and reads the table SDCC would
    compile. A hand-written table, a dropped entry or a reordered field all fail here; a
    string search for the include filename would catch none of them.
    """

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(DEBUG_C):
            raise unittest.SkipTest('src/debug.c does not exist yet')
        cls.gcc = shutil.which('gcc')
        if cls.gcc is None:
            raise unittest.SkipTest('gcc is not on PATH')

    def _expanded(self):
        out = subprocess.run(
            [self.gcc, '-E', '-P', '-DDEBUG_MAILBOX',
             '-I', SRC, '-I', os.path.join(dp.REPO_ROOT, 'tests', 'mocks'), DEBUG_C],
            capture_output=True, text=True, check=False)
        if out.returncode != 0:
            self.skipTest(f'preprocessing src/debug.c failed: {out.stderr.strip()[:300]}')
        return out.stdout

    def test_the_compiled_table_holds_every_def_entry_in_order(self):
        text = re.sub(r'\s+', '', self._expanded())
        m = re.search(r'dbg_cmd_table\[\]=\{(.*?)\};', text)
        self.assertIsNotNone(m, 'no dbg_cmd_table initializer in the preprocessed source')
        rows = re.findall(r'\{(\d+),(\d+),(\d+),(\d+)\}', m.group(1))
        want = [(str(s['opcode']), str(s['argc']), str(s['arg0_max']), str(s['arg1_max']))
                for s in dp.commands().values()]
        self.assertEqual([tuple(r) for r in rows], want)

    def test_the_compiled_enum_holds_every_def_entry(self):
        text = re.sub(r'\s+', '', self._expanded())
        for name, spec in dp.commands().items():
            with self.subTest(command=name):
                self.assertIn(f'DBG_OP_{name.upper()}=({spec["opcode"]})', text)


class TestOutcomeMessages(unittest.TestCase):
    def setUp(self):
        if not dp.has_mailbox():
            self.skipTest('src/debug.h has no mailbox contract yet')

    def test_every_outcome_code_in_the_header_has_a_message(self):
        """R21: Python owns every message, so a new C code without one is a defect."""
        for name in dp.outcomes():
            with self.subTest(outcome=name):
                self.assertIn(name, dp.OUTCOME_MESSAGES)

    def test_no_message_names_an_outcome_the_header_dropped(self):
        for name in dp.OUTCOME_MESSAGES:
            with self.subTest(outcome=name):
                self.assertIn(name, dp.outcomes())

    def test_every_refusal_short_name_resolves(self):
        for short in dp.REFUSAL_NAMES:
            with self.subTest(refusal=short):
                self.assertIsInstance(dp.refusal_code(short), int)

    def test_an_unknown_refusal_names_the_known_ones(self):
        with self.assertRaises(dp.ProtocolError) as cm:
            dp.refusal_code('exploded')
        self.assertIn('locked', str(cm.exception))

    def test_describe_outcome_names_the_code_and_the_detail(self):
        text = dp.describe_outcome(dp.outcomes()['DBG_OUT_LOCKED'], detail=2)
        self.assertIn('DBG_OUT_LOCKED', text)
        self.assertIn('detail=2', text)


class TestCommitByte(unittest.TestCase):
    def setUp(self):
        if not dp.has_mailbox():
            self.skipTest('src/debug.h has no mailbox contract yet')

    def test_the_fold_matches_the_seed(self):
        # DBG_MB_SEED is fixed at 0x5A (the mailbox wire contract, #590 R7). opcode=5, arg0=9,
        # arg1=2 is not degenerate (unlike 3^2^1==0) so the fold actually moves the result:
        #   0x5A = 0101 1010
        # ^    5 = 0000 0101  ->  0101 1111 = 0x5F
        # ^    9 = 0000 1001  ->  0101 0110 = 0x56
        # ^    2 = 0000 0010  ->  0101 0100 = 0x54 = 84
        # This literal was worked out by hand, not by re-evaluating commit_byte's own
        # expression, so a broken operator inside commit_byte (e.g. `|` or `+` swapped in for
        # `^`) changes the result and this assertion catches it.
        self.assertEqual(dp.commit_byte(5, 9, 2), 84)

    def test_a_changed_argument_changes_the_fold(self):
        self.assertNotEqual(dp.commit_byte(3, 2, 1), dp.commit_byte(3, 2, 0))

    def test_the_addresses_match_the_fixed_wire_layout(self):
        # The wire is fixed at DBG_MB_BASE = 0xDF70, nine consecutive bytes (#590 R7).
        self.assertEqual(dp.base(), 0xDF70)
        self.assertEqual(dp.addresses(), {
            'ready':   0xDF70,
            'opcode':  0xDF71,
            'arg0':    0xDF72,
            'arg1':    0xDF73,
            'commit':  0xDF74,
            'outcome': 0xDF75,
            'detail':  0xDF76,
            'epoch':   0xDF77,
            'torn':    0xDF78,
        })


class TestOffsetsMatchTheHeader(unittest.TestCase):
    """Closes the hole under the old offsets/addresses test: OFFSETS is hand-maintained Python
    and nothing checked it against src/debug.h's DBG_MB_OFF_* defines. Skips until the header
    carries the mailbox contract, then starts biting the moment it does."""

    def setUp(self):
        if not dp.has_mailbox():
            self.skipTest('src/debug.h has no mailbox contract yet')

    def test_every_offset_matches_its_header_define(self):
        for key, value in dp.OFFSETS.items():
            with self.subTest(field=key):
                header_name = 'DBG_MB_OFF_' + key.upper()
                self.assertIn(header_name, dp.mailbox())
                self.assertEqual(dp.mailbox()[header_name], value)

    def test_the_two_field_sets_cover_each_other_exactly(self):
        header_fields = {name[len('DBG_MB_OFF_'):].lower()
                          for name in dp.mailbox() if name.startswith('DBG_MB_OFF_')}
        self.assertEqual(header_fields, set(dp.OFFSETS))


class TestPack(unittest.TestCase):
    def test_add_scrap_splits_a_16_bit_amount_low_byte_first(self):
        self.assertEqual(dp.pack('add_scrap', {'amount': 0x0102}), (1, 0x02, 0x01))

    def test_set_option_resolves_both_names(self):
        self.assertEqual(dp.pack('set_option', {'field': 'weapon1', 'option': 'laser'}),
                         (3, 2, 1))

    def test_force_state_resolves_the_state_and_the_mode(self):
        self.assertEqual(dp.pack('force_state', {'state': 'playing', 'mode': 'push'}),
                         (6, 4, 0))

    def test_an_unknown_command_names_the_known_ones(self):
        with self.assertRaises(dp.ProtocolError) as cm:
            dp.pack('teleport', {})
        self.assertIn('set_option', str(cm.exception))

    def test_an_unknown_argument_name_is_refused(self):
        with self.assertRaises(dp.ProtocolError) as cm:
            dp.pack('damage', {'hp': 5})
        self.assertIn('amount', str(cm.exception))

    def test_a_missing_argument_is_refused(self):
        with self.assertRaises(dp.ProtocolError):
            dp.pack('set_option', {'field': 'weapon1'})

    def test_an_out_of_range_argument_is_refused_before_the_wire(self):
        with self.assertRaises(dp.ProtocolError) as cm:
            dp.pack('despawn_turret', {'slot': 8})
        self.assertIn('0..7', str(cm.exception))

    def test_an_unknown_option_name_names_the_known_ones(self):
        with self.assertRaises(dp.ProtocolError) as cm:
            dp.pack('set_option', {'field': 'weapon1', 'option': 'railgun'})
        self.assertIn('cannon', str(cm.exception))

    def test_a_numeric_field_outside_the_range_raises_protocol_error(self):
        """Not IndexError: the caller reports this, it must not crash the load."""
        with self.assertRaises(dp.ProtocolError):
            dp.pack('set_option', {'field': 9, 'option': 0})

    def test_a_non_numeric_amount_is_a_protocol_error_not_a_value_error(self):
        """add_scrap path: int('not-a-number') raises ValueError if not caught (review Finding 1)."""
        with self.assertRaises(dp.ProtocolError) as cm:
            dp.pack('add_scrap', {'amount': 'not-a-number'})
        self.assertIn('amount', str(cm.exception))

    def test_a_none_amount_is_a_protocol_error_not_a_type_error(self):
        """add_scrap path: int(None) raises TypeError if not caught (review Finding 1)."""
        with self.assertRaises(dp.ProtocolError) as cm:
            dp.pack('add_scrap', {'amount': None})
        self.assertIn('amount', str(cm.exception))

    def test_a_non_numeric_generic_argument_is_a_protocol_error_not_a_value_error(self):
        """Generic path (not add_scrap/unlock_field/set_option/force_state) hits `int(args[n])`
        directly; despawn_turret exercises it (review Finding 1)."""
        with self.assertRaises(dp.ProtocolError) as cm:
            dp.pack('despawn_turret', {'slot': 'abc'})
        self.assertIn('slot', str(cm.exception))

    def test_a_none_generic_argument_is_a_protocol_error_not_a_type_error(self):
        with self.assertRaises(dp.ProtocolError) as cm:
            dp.pack('despawn_turret', {'slot': None})
        self.assertIn('slot', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
