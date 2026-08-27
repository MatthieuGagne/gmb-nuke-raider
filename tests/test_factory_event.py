"""Tests for tools/factory_event.py — the event-append CLI (#437)."""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', 'tools'))
import factory_event
import factory_run


class ParseFieldTest(unittest.TestCase):
    def test_plain_string_stays_a_string(self):
        self.assertEqual(factory_event.parse_field('result=pass'),
                         ('result', 'pass'))

    def test_json_true_becomes_a_bool(self):
        self.assertEqual(factory_event.parse_field('blocking=true'),
                         ('blocking', True))

    def test_json_number_becomes_an_int(self):
        self.assertEqual(factory_event.parse_field('count=3'), ('count', 3))

    def test_prose_with_spaces_stays_a_string(self):
        key, value = factory_event.parse_field('text=Widened the rule to bank 3')
        self.assertEqual(key, 'text')
        self.assertEqual(value, 'Widened the rule to bank 3')

    def test_splits_on_the_first_equals_only(self):
        self.assertEqual(factory_event.parse_field('text=a=b'), ('text', 'a=b'))

    def test_missing_equals_is_an_error(self):
        with self.assertRaises(ValueError):
            factory_event.parse_field('noequals')

    def test_empty_key_is_an_error(self):
        with self.assertRaises(ValueError):
            factory_event.parse_field('=value')


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.registry = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(factory_run.set_clock, None)

    def _journal(self, issue=461):
        path = factory_run.journal_path(issue, self.registry)
        with open(path, encoding='utf-8') as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def test_appends_a_stage_event(self):
        code = factory_event.main(['--issue', '461', '--kind', 'stage',
                                   '--field', 'stage=BUILD',
                                   '--registry', self.registry])
        self.assertEqual(code, 0)
        events = self._journal()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['kind'], 'stage')
        self.assertEqual(events[0]['stage'], 'BUILD')
        self.assertEqual(events[0]['issue'], 461)

    def test_attempt_is_recorded_on_the_event(self):
        factory_event.main(['--issue', '461', '--kind', 'retry',
                            '--field', 'stage=BUILD', '--attempt', '2',
                            '--registry', self.registry])
        self.assertEqual(self._journal()[0]['attempt'], 2)

    def test_unknown_kind_is_misuse(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = factory_event.main(['--issue', '461', '--kind', 'nope',
                                       '--registry', self.registry])
        self.assertEqual(code, 2)
        self.assertIn('nope', err.getvalue())

    def test_malformed_field_is_misuse(self):
        with redirect_stderr(io.StringIO()):
            code = factory_event.main(['--issue', '461', '--kind', 'decision',
                                       '--field', 'noequals',
                                       '--registry', self.registry])
        self.assertEqual(code, 2)

    def test_bad_now_is_misuse(self):
        with redirect_stderr(io.StringIO()):
            code = factory_event.main(['--issue', '461', '--kind', 'stage',
                                       '--field', 'stage=GATE',
                                       '--now', 'not-a-timestamp',
                                       '--registry', self.registry])
        self.assertEqual(code, 2)

    def test_json_prints_the_written_event(self):
        out = io.StringIO()
        with redirect_stdout(out):
            factory_event.main(['--issue', '461', '--kind', 'gate',
                                '--field', 'stage=GATE',
                                '--field', 'gate=spec-lint',
                                '--field', 'result=pass',
                                '--registry', self.registry, '--json'])
        printed = json.loads(out.getvalue())
        self.assertEqual(printed['gate'], 'spec-lint')
        self.assertEqual(printed['result'], 'pass')

    def test_render_field_is_refused(self):
        with redirect_stderr(io.StringIO()):
            code = factory_event.main(['--issue', '461', '--kind', 'stage',
                                       '--field', 'render=true',
                                       '--registry', self.registry])
        self.assertEqual(code, 2)

    def test_lane_flag_lands_on_the_event(self):
        code = factory_event.main(['--issue', '461', '--kind', 'start',
                                   '--lane', 'gauntlet',
                                   '--registry', self.registry])
        self.assertEqual(code, 0)
        self.assertEqual(self._journal()[0]['lane'], 'gauntlet')

    def test_lane_flag_reaches_the_run_state(self):
        factory_event.main(['--issue', '461', '--kind', 'start',
                            '--lane', 'gauntlet',
                            '--registry', self.registry])
        state = factory_run.load_state(461, self.registry)
        self.assertEqual(state['lane'], 'gauntlet')

    def test_the_default_run_is_the_factory_lane(self):
        """R1: the default is `factory`, and it costs the journal nothing --
        an omitted --lane writes no lane key at all."""
        factory_event.main(['--issue', '461', '--kind', 'start',
                            '--field', 'stage=GATE',
                            '--registry', self.registry])
        self.assertNotIn('lane', self._journal()[0])
        self.assertEqual(factory_run.load_state(461, self.registry)['lane'],
                         'factory')

    def test_unknown_lane_is_misuse(self):
        """R2: refused the way an unknown --kind is refused."""
        err = io.StringIO()
        with redirect_stderr(err):
            code = factory_event.main(['--issue', '461', '--kind', 'start',
                                       '--lane', 'sideshow',
                                       '--registry', self.registry])
        self.assertEqual(code, 2)
        self.assertIn('sideshow', err.getvalue())
        self.assertIn('gauntlet', err.getvalue())

    def test_an_unknown_lane_writes_nothing(self):
        """The refusal happens before the journal is touched, so a rejected
        run leaves no half-written event behind."""
        with redirect_stderr(io.StringIO()):
            factory_event.main(['--issue', '461', '--kind', 'start',
                                '--lane', 'sideshow',
                                '--registry', self.registry])
        self.assertFalse(os.path.exists(
            factory_run.journal_path(461, self.registry)))

    def test_an_unknown_lane_passed_as_a_field_is_refused_too(self):
        """--field is the same door; validating only the flag would leave a
        bypass that writes an unknown lane straight into state."""
        err = io.StringIO()
        with redirect_stderr(err):
            code = factory_event.main(['--issue', '461', '--kind', 'start',
                                       '--field', 'lane=sideshow',
                                       '--registry', self.registry])
        self.assertEqual(code, 2)
        self.assertIn('sideshow', err.getvalue())

    def test_a_known_lane_passed_as_a_field_is_accepted(self):
        code = factory_event.main(['--issue', '461', '--kind', 'start',
                                   '--field', 'lane=gauntlet',
                                   '--registry', self.registry])
        self.assertEqual(code, 0)
        self.assertEqual(factory_run.load_state(461, self.registry)['lane'],
                         'gauntlet')


if __name__ == '__main__':
    unittest.main()
