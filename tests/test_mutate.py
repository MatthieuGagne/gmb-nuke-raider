"""Tests for tools/mutate.py"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

HAVE_LIZARD = importlib.util.find_spec('lizard') is not None

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import mutate

ROOT = os.path.join(os.path.dirname(__file__), '..')


class MaskSourceTests(unittest.TestCase):
    def test_line_comment_is_blanked(self):
        masked = mutate.mask_source('a < b; // x < y\n')
        self.assertIn('a < b;', masked)
        self.assertNotIn('x < y', masked)

    def test_block_comment_is_blanked_across_lines(self):
        masked = mutate.mask_source('/* x < y\nstill < here */ a < b;\n')
        self.assertEqual(masked.count('<'), 1)

    def test_string_and_char_literals_are_blanked(self):
        masked = mutate.mask_source('printf("a < b %c", \'<\');\n')
        self.assertNotIn('<', masked)

    def test_escaped_quote_does_not_end_string(self):
        masked = mutate.mask_source('s = "a\\"b < c";\nx < y;\n')
        self.assertEqual(masked.count('<'), 1)

    def test_preprocessor_line_is_blanked(self):
        masked = mutate.mask_source('#define LIMIT 10\nx = 10;\n')
        self.assertNotIn('LIMIT', masked)
        self.assertIn('10;', masked)

    def test_mask_preserves_length_and_newlines(self):
        src = 'a; // c\n#include <x.h>\nb;\n'
        masked = mutate.mask_source(src)
        self.assertEqual(len(masked), len(src))
        self.assertEqual(masked.count('\n'), src.count('\n'))

    def test_stray_apostrophe_still_preserves_newlines(self):
        src = "c = a';\nx < y;\n"
        masked = mutate.mask_source(src)
        self.assertEqual(len(masked), len(src))
        self.assertEqual(masked.count('\n'), src.count('\n'))


class OperatorTests(unittest.TestCase):
    def _mutants(self, line):
        return mutate.iter_line_mutants(mutate.mask_source(line), line)

    def _ops(self, line):
        return [(f['op'], f['original'], f['mutated'])
                for f in self._mutants(line)]

    def test_comparison_flip(self):
        self.assertIn(('comparison', '<', '>='), self._ops('if (a < b) {'))

    def test_equality_flip(self):
        self.assertIn(('comparison', '==', '!='), self._ops('x = a == b;'))

    def test_arrow_operator_is_not_a_comparison(self):
        line = 'v = p->field;'
        self.assertFalse(any(f['op'] == 'comparison'
                             for f in self._mutants(line)))

    def test_shift_is_not_a_comparison(self):
        line = 'v = a << 2;'
        self.assertFalse(any(f['op'] == 'comparison'
                             for f in self._mutants(line)))

    def test_arithmetic_swap(self):
        self.assertIn(('arithmetic', '+', '-'), self._ops('c = a + b;'))

    def test_increment_is_not_arithmetic(self):
        line = 'i++;'
        self.assertFalse(any(f['op'] == 'arithmetic'
                             for f in self._mutants(line)))

    def test_unary_minus_is_not_arithmetic(self):
        line = 'v = -1;'
        self.assertFalse(any(f['op'] == 'arithmetic'
                             for f in self._mutants(line)))

    def test_pointer_declaration_is_not_arithmetic(self):
        line = 'int *p = q;'
        self.assertFalse(any(f['op'] == 'arithmetic'
                             for f in self._mutants(line)))

    def test_typedef_pointer_declaration_is_not_arithmetic(self):
        line = 'uint8_t *p = q;'
        self.assertFalse(any(f['op'] == 'arithmetic'
                             for f in self._mutants(line)))

    def test_multiplication_is_still_arithmetic(self):
        self.assertIn(('arithmetic', '*', '/'), self._ops('c = a * b;'))

    def test_constant_perturbation(self):
        self.assertIn(('constant', '10', '11'), self._ops('if (v > 10) {'))

    def test_hex_literal_is_untouched(self):
        line = 'v = 0x1F;'
        self.assertFalse(any(f['op'] == 'constant'
                             for f in self._mutants(line)))

    def test_return_value_substitution(self):
        self.assertIn(('return', 'v', '0'), self._ops('    return v;'))

    def test_return_zero_becomes_one(self):
        self.assertIn(('return', '0', '1'), self._ops('    return 0;'))

    def test_void_return_is_untouched(self):
        line = '    return;'
        self.assertFalse(any(f['op'] == 'return'
                             for f in self._mutants(line)))

    def test_condition_negation_wraps_whole_condition(self):
        self.assertIn(('negate-condition', 'a && (b || c)', '!(a && (b || c))'),
                      self._ops('if (a && (b || c)) {'))

    def test_no_mutants_inside_comment(self):
        self.assertEqual(self._mutants('// if (a < b) return 1;'), [])

    def test_deterministic_column_order(self):
        cols = [f['col'] for f in self._mutants('if (a < b + 2) return 1;')]
        self.assertEqual(cols, sorted(cols))


class ScopeTests(unittest.TestCase):
    SRC = (
        'int clamp(int v) {\n'
        '    if (v > 10) return 10;\n'
        '    return v;\n'
        '}\n'
        '\n'
        'int twice(int v) {\n'
        '    return v * 2;\n'
        '}\n'
    )

    @unittest.skipUnless(HAVE_LIZARD, 'lizard not installed')
    def test_whole_file_scope_covers_all_functions(self):
        spans = mutate.touched_functions('x.c', self.SRC, None)
        self.assertEqual(len(spans), 2)

    @unittest.skipUnless(HAVE_LIZARD, 'lizard not installed')
    def test_changed_lines_select_only_touched_function(self):
        spans = mutate.touched_functions('x.c', self.SRC, {7})
        self.assertEqual(len(spans), 1)
        start, end = spans[0]
        self.assertLessEqual(start, 7)
        self.assertGreaterEqual(end, 7)

    def test_exempt_list_is_reused_from_crap_score(self):
        self.assertIn('src/main.c', mutate.EXEMPT_FILES)
        self.assertGreater(len(mutate.EXEMPT_FILES), 20)

    @unittest.skipUnless(HAVE_LIZARD, 'lizard not installed')
    def test_generate_candidates_orders_and_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'src'))
            path = os.path.join(tmp, 'src', 'calc.c')
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(self.SRC)
            cands = mutate.generate_candidates(tmp, {'src/calc.c': None})
        self.assertTrue(cands)
        self.assertTrue(all(c['file'] == 'src/calc.c' for c in cands))
        keys = [(c['line'], c['col'], c['op']) for c in cands]
        self.assertEqual(keys, sorted(keys))


class ApplyMutantTests(unittest.TestCase):
    def test_apply_replaces_only_the_fragment(self):
        text = 'int f(void) {\n    return 10;\n}\n'
        mutant = {'file': 'x.c', 'line': 2, 'col': 11, 'op': 'constant',
                  'original': '10', 'mutated': '11'}
        self.assertEqual(mutate.apply_mutant(text, mutant),
                         'int f(void) {\n    return 11;\n}\n')

    def test_apply_roundtrip_with_generated_column(self):
        text = 'int f(int v) {\n    if (v > 3) return 1;\n    return 0;\n}\n'
        masked = mutate.mask_source(text)
        line2 = text.splitlines()[1]
        masked2 = masked.splitlines()[1]
        frag = [f for f in mutate.iter_line_mutants(masked2, line2)
                if f['op'] == 'comparison'][0]
        frag.update({'file': 'x.c', 'line': 2})
        mutated = mutate.apply_mutant(text, frag)
        self.assertIn('v <= 3', mutated)


class FakeRun(object):
    """Scripted runner. Records every command; answers by predicate."""

    def __init__(self, failing_binaries=(), failing_compiles=()):
        self.commands = []
        self.failing_binaries = set(failing_binaries)
        self.failing_compiles = set(failing_compiles)

    def __call__(self, cmd, cwd, timeout):
        self.commands.append(list(cmd))
        if cmd[0] == 'gcc':
            src = next((a for a in cmd if a.endswith('.c')), '')
            if os.path.basename(src) in self.failing_compiles:
                return 1, 'error: scripted compile failure'
            return 0, ''
        name = os.path.basename(cmd[0]).replace('.exe', '')
        return (1, 'FAIL') if name in self.failing_binaries else (0, 'OK')

    def compiles_of(self, basename):
        return [c for c in self.commands
                if c[:2] == ['gcc', '-c']
                and any(os.path.basename(a) == basename for a in c)]


def _fixture_project(tmp, extra_test=None):
    """Two-module miniature project matching the engine's expectations."""
    src = os.path.join(tmp, 'src')
    tst = os.path.join(tmp, 'tests')
    os.makedirs(src)
    os.makedirs(tst)
    with open(os.path.join(src, 'calc.c'), 'w', encoding='utf-8') as fh:
        fh.write('int clamp(int v) {\n'
                 '    if (v > 10) { return 10; }\n'
                 '    return v;\n'
                 '}\n')
    with open(os.path.join(src, 'other.c'), 'w', encoding='utf-8') as fh:
        fh.write('int other_id(int v) { return v; }\n')
    with open(os.path.join(tst, 'test_calc.c'), 'w',
              encoding='utf-8') as fh:
        fh.write(extra_test or (
            'extern int clamp(int);\n'
            'int main(void) {\n'
            '    if (clamp(5) != 5) { return 1; }\n'
            '    if (clamp(11) != 10) { return 1; }\n'
            '    if (clamp(10) != 10) { return 1; }\n'
            '    if (clamp(-3) != -3) { return 1; }\n'
            '    return 0;\n'
            '}\n'))
    with open(os.path.join(tst, 'test_other.c'), 'w',
              encoding='utf-8') as fh:
        fh.write('extern int other_id(int);\n'
                 'int main(void) { return other_id(7) == 7 ? 0 : 1; }\n')
    return mutate.Project(tmp, [], ['src/calc.c', 'src/other.c'],
                          ['tests/test_calc.c', 'tests/test_other.c'], [],
                          os.path.join(tmp, 'build', 'mutation'))


class EngineFakeRunTests(unittest.TestCase):
    def _project_and_baseline(self, run):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        project = _fixture_project(self.tmp.name)
        baseline = mutate.build_baseline(project, run)
        return project, baseline

    def _mutant(self):
        return {'file': 'src/calc.c', 'line': 2, 'col': 10,
                'op': 'comparison', 'original': '>', 'mutated': '<='}

    def test_own_module_binary_runs_first_and_kill_stops_suite(self):
        # The baseline must be green, so it gets a clean runner; only the
        # mutant phase sees the failing binary.
        project, (lib, sup, bins) = self._project_and_baseline(FakeRun())
        run = FakeRun(failing_binaries={'test_calc'})
        res = mutate.test_mutant(project, lib, sup, bins,
                                 self._mutant(), run)
        self.assertEqual(res['status'], 'killed')
        self.assertEqual(res['killed_by'], 'test_calc')
        self.assertEqual(res['binaries_run'], 1)  # test_other never ran

    def test_survivor_escalates_to_full_suite(self):
        run = FakeRun()
        project, (lib, sup, bins) = self._project_and_baseline(run)
        res = mutate.test_mutant(project, lib, sup, bins,
                                 self._mutant(), run)
        self.assertEqual(res['status'], 'survived')
        self.assertEqual(res['binaries_run'], 2)

    def test_compile_failure_is_invalid_not_killed(self):
        # Baseline compiles with a clean runner; the mutant copy (same
        # basename calc.c, under build/mutation/mutants/) then fails.
        project, (lib, sup, bins) = self._project_and_baseline(FakeRun())
        run = FakeRun(failing_compiles={'calc.c'})
        res = mutate.test_mutant(project, lib, sup, bins,
                                 self._mutant(), run)
        self.assertEqual(res['status'], 'invalid')

    def test_second_mutant_recompiles_only_the_mutated_file(self):
        """AC8 at unit level: the object cache is not rebuilt per mutant."""
        run = FakeRun()
        project, (lib, sup, bins) = self._project_and_baseline(run)
        mutate.test_mutant(project, lib, sup, bins, self._mutant(), run)
        run.commands = []
        mutate.test_mutant(project, lib, sup, bins, self._mutant(), run)
        self.assertEqual(len(run.compiles_of('calc.c')), 1)
        self.assertEqual(len(run.compiles_of('other.c')), 0)
        self.assertEqual(len(run.compiles_of('test_calc.c')), 0)

    def test_red_baseline_raises(self):
        run = FakeRun(failing_binaries={'test_other'})
        with self.assertRaises(mutate.MutationError):
            self._project_and_baseline(run)


@unittest.skipUnless(
    os.environ.get('NUKE_MUTATE_GCC_TESTS') == '1'
    and shutil.which('gcc'),
    'set NUKE_MUTATE_GCC_TESTS=1 with gcc on PATH (opt-in: ~90 gcc '
    'spawns is too slow for the per-commit pre-commit hook)')
class GccFixtureIntegrationTests(unittest.TestCase):
    """AC1/AC2 shape, end to end against real gcc on a 2-file fixture.

    Env-gated: the pre-commit hook runs the whole discovery on every
    commit and must stay fast; these tests run when a task's verify step
    (and Task 4) sets NUKE_MUTATE_GCC_TESTS=1 explicitly.
    """

    def test_thoroughly_tested_function_yields_zero_survivors(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _fixture_project(tmp)
            lib, sup, bins = mutate.build_baseline(
                project, mutate.run_subprocess)
            cands = mutate.generate_candidates(tmp, {'src/calc.c': None})
            statuses = [mutate.test_mutant(project, lib, sup, bins, m,
                                           mutate.run_subprocess)['status']
                        for m in cands]
            self.assertNotIn('survived', statuses)
            self.assertIn('killed', statuses)

    def test_weak_test_yields_survivor_with_line_and_operator(self):
        weak = ('extern int clamp(int);\n'
                'int main(void) { clamp(5); return 0; }\n')
        with tempfile.TemporaryDirectory() as tmp:
            project = _fixture_project(tmp, extra_test=weak)
            lib, sup, bins = mutate.build_baseline(
                project, mutate.run_subprocess)
            cands = mutate.generate_candidates(tmp, {'src/calc.c': None})
            survivors = [m for m in cands
                         if mutate.test_mutant(project, lib, sup, bins, m,
                                               mutate.run_subprocess
                                               )['status'] == 'survived']
            self.assertTrue(survivors)
            self.assertTrue(all(s['line'] >= 1 and s['op']
                                for s in survivors))

    def test_mutation_never_touches_the_source_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = _fixture_project(tmp)
            src_path = os.path.join(tmp, 'src', 'calc.c')
            with open(src_path, encoding='utf-8') as fh:
                before = fh.read()
            lib, sup, bins = mutate.build_baseline(
                project, mutate.run_subprocess)
            cands = mutate.generate_candidates(tmp, {'src/calc.c': None})
            mutate.test_mutant(project, lib, sup, bins, cands[0],
                               mutate.run_subprocess)
            with open(src_path, encoding='utf-8') as fh:
                self.assertEqual(fh.read(), before)


class ResolveScopeTests(unittest.TestCase):
    def test_exempt_file_is_excluded_with_reason(self):
        scope, skipped = mutate.resolve_scope(['src/main.c'], None, ROOT)
        self.assertEqual(scope, {})
        self.assertEqual(skipped[0]['reason'], 'exempt (R7)')

    def test_non_src_file_is_excluded(self):
        scope, skipped = mutate.resolve_scope(['tools/mutate.py'], None,
                                              ROOT)
        self.assertEqual(scope, {})
        self.assertIn('not a src', skipped[0]['reason'])

    def test_existing_src_file_is_in_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'src'))
            with open(os.path.join(tmp, 'src', 'foo.c'), 'w',
                      encoding='utf-8') as fh:
                fh.write('int f(void) { return 1; }\n')
            scope, skipped = mutate.resolve_scope(['src/foo.c'], None, tmp)
        self.assertEqual(list(scope), ['src/foo.c'])
        self.assertIsNone(scope['src/foo.c'])
        self.assertEqual(skipped, [])


class RunMutationTests(unittest.TestCase):
    # Static mutants: keeps these tests lizard-free (test_crap_score.py
    # keeps the suite runnable without lizard; so must this file). Columns
    # verified against the fixture calc.c text.
    CANDS = [
        {'file': 'src/calc.c', 'line': 2, 'col': 10,
         'op': 'comparison', 'original': '>', 'mutated': '<='},
        {'file': 'src/calc.c', 'line': 2, 'col': 12,
         'op': 'constant', 'original': '10', 'mutated': '11'},
        {'file': 'src/calc.c', 'line': 2, 'col': 8,
         'op': 'negate-condition', 'original': 'v > 10',
         'mutated': '!(v > 10)'},
        {'file': 'src/calc.c', 'line': 3, 'col': 11,
         'op': 'return', 'original': 'v', 'mutated': '0'},
    ]

    def _setup(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        project = _fixture_project(tmp.name)
        return project, [dict(c) for c in self.CANDS]

    def test_budget_overflow_is_counted_not_silent(self):
        """AC4: over-budget candidates are reported by count."""
        run = FakeRun()
        project, cands = self._setup()
        report = mutate.run_mutation(project, cands, 2, 600, run)
        self.assertEqual(report['tested'], 2)
        self.assertEqual(report['skipped_over_budget'], len(cands) - 2)

    def test_invalid_mutants_excluded_from_survival_rate(self):
        """AC5: rate uses killed+survived only."""
        project, cands = self._setup()
        run = _BaselineThenMutant(
            FakeRun(), FakeRun(failing_compiles={'calc.c'}))
        report = mutate.run_mutation(project, cands[:3], 3, 600, run)
        self.assertEqual(report['invalid'], 3)
        self.assertIsNone(report['first_pass_survival_rate'])

    def test_timeout_skips_and_reports_remaining(self):
        run = FakeRun()
        project, cands = self._setup()
        state = {'t': 0.0}

        def clock():
            state['t'] += 1.0
            return state['t']

        # With the fixture (2 lib, 0 support, 2 test sources) the baseline
        # makes exactly 8 clock calls after `started`: baseline_start,
        # 2 lib checks, 2 link checks, 2 run checks, baseline_seconds.
        # timeout 8 puts the deadline at t=9, so the baseline finishes in
        # time and the first mutant-loop check (t=10) is past it.
        report = mutate.run_mutation(project, cands, len(cands), 8, run,
                                     clock=clock)
        self.assertEqual(report['tested'], 0)
        self.assertEqual(report['skipped_timeout'], len(cands))

    def test_baseline_overrunning_the_deadline_is_operational_error(self):
        run = FakeRun()
        project, cands = self._setup()
        with self.assertRaises(mutate.MutationError):
            # Deadline t=2 expires on the first baseline check (t=3).
            state = {'t': 0.0}

            def clock():
                state['t'] += 1.0
                return state['t']

            mutate.run_mutation(project, cands, len(cands), 1, run,
                                clock=clock)
        self.assertFalse(os.path.exists(project.mutants_dir()))

    def test_induced_crash_still_removes_mutants_dir(self):
        """AC3: cleanup holds under a crash mid-run, not only happy path."""
        class Boom(Exception):
            pass

        run = FakeRun()
        project, cands = self._setup()

        calls = {'n': 0}
        # 2 lib compiles + (2 test compiles + 2 links) + 2 runs = 8 for
        # the fixture. Fragile by design: if the fixture ever gains
        # support sources, update this arithmetic alongside it.
        baseline_calls = (len(project.lib_sources)
                          + len(project.test_sources) * 2  # compile+link
                          + len(project.test_sources))     # runs

        def crashing_run(cmd, cwd, timeout):
            calls['n'] += 1
            if calls['n'] > baseline_calls + 1:
                raise Boom()
            return run(cmd, cwd, timeout)

        with self.assertRaises(Boom):
            mutate.run_mutation(project, cands, len(cands), 600,
                                crashing_run)
        self.assertFalse(os.path.exists(project.mutants_dir()))


class _BaselineThenMutant(object):
    """Route baseline commands to one FakeRun, mutant-phase to another."""

    def __init__(self, baseline_run, mutant_run):
        self.baseline_run = baseline_run
        self.mutant_run = mutant_run

    def __call__(self, cmd, cwd, timeout):
        text = ' '.join(cmd)
        if os.path.join('build', 'mutation', 'mutants') in text or \
                'mutants' in text:
            return self.mutant_run(cmd, cwd, timeout)
        return self.baseline_run(cmd, cwd, timeout)


class CliTests(unittest.TestCase):
    def _main(self, argv, run):
        import contextlib
        import io
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        _fixture_project(tmp.name)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mutate.main(argv + ['--repo-root', tmp.name], run=run,
                             project_factory=_fixture_project_factory)
        return rc, buf.getvalue()

    @unittest.skipUnless(HAVE_LIZARD, 'lizard not installed')
    def test_all_killed_exits_zero(self):
        # Clean baseline, then every calc.c mutant dies in its own binary.
        run = _BaselineThenMutant(
            FakeRun(), FakeRun(failing_binaries={'test_calc'}))
        rc, out = self._main(['--files', 'src/calc.c'], run)
        self.assertEqual(rc, 0)
        self.assertIn('no survivors', out)

    @unittest.skipUnless(HAVE_LIZARD, 'lizard not installed')
    def test_survivor_exits_one_and_names_site(self):
        rc, out = self._main(['--files', 'src/calc.c'], FakeRun())
        self.assertEqual(rc, 1)
        self.assertIn('SURVIVOR src/calc.c:', out)

    @unittest.skipUnless(HAVE_LIZARD, 'lizard not installed')
    def test_json_shape(self):
        import json as _json
        rc, out = self._main(['--files', 'src/calc.c', '--json'],
                             FakeRun())
        data = _json.loads(out)
        for key in ('budget', 'timeout_seconds', 'candidates', 'tested',
                    'killed', 'survived', 'invalid', 'skipped_over_budget',
                    'skipped_timeout', 'first_pass_survival_rate',
                    'survivors', 'timings', 'files', 'excluded'):
            self.assertIn(key, data)
        self.assertEqual(rc, 1)

    def test_missing_scope_flag_is_usage_error(self):
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                mutate.main([], run=FakeRun())
        self.assertEqual(ctx.exception.code, 2)

    def test_nonpositive_budget_is_usage_error(self):
        rc, _ = self._main(['--files', 'src/calc.c', '--budget', '0'],
                           FakeRun())
        self.assertEqual(rc, 2)

    def test_empty_commit_range_is_usage_error(self):
        rc, _ = self._main(['--commit-range', ''], FakeRun())
        self.assertEqual(rc, 2)

    @unittest.skipUnless(HAVE_LIZARD, 'lizard not installed')
    def test_timed_out_run_exits_two_not_zero(self):
        """R4: an inconclusive (timed-out) run must not read as green."""
        from unittest import mock
        report = {'survived': 0, 'skipped_timeout': 3,
                  'skipped_over_budget': 0, 'tested': 1, 'killed': 1,
                  'invalid': 0, 'candidates': 4, 'budget': 4,
                  'timeout_seconds': 600,
                  'first_pass_survival_rate': 0.0, 'survivors': [],
                  'invalid_mutants': [],
                  'timings': {'baseline_seconds': 0, 'total_seconds': 0,
                              'per_mutant': []}}
        with mock.patch.object(mutate, 'run_mutation',
                               return_value=report):
            rc, _ = self._main(['--files', 'src/calc.c'], FakeRun())
        self.assertEqual(rc, 2)


def _fixture_project_factory(root):
    return mutate.Project(root, [], ['src/calc.c', 'src/other.c'],
                          ['tests/test_calc.c', 'tests/test_other.c'], [],
                          os.path.join(root, 'build', 'mutation'))


if __name__ == '__main__':
    unittest.main()
