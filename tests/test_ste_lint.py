"""Tests for tools/ste_lint.py (#517)."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import ste_lint  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

GLOSSARY = """# Glossary

**Run issue**:
The GitHub issue that renders one Run.
_Avoid_: status issue, dashboard issue, tracking issue — and never the **spec
issue**, which is the issue the run is working on

**Published copy**:
The rendering of a run on GitHub.
_Avoid_: the dashboard, the mirror, the remote state
"""


def banned():
    return ste_lint.parse_glossary(GLOSSARY)


class GlossaryTests(unittest.TestCase):
    def test_reads_every_avoid_entry(self):
        words = [w for w, _ in banned()]
        self.assertIn('dashboard issue', words)
        self.assertIn('the dashboard', words)

    def test_drops_the_prose_after_an_em_dash(self):
        """`_Avoid_: a, b — and never X` bans a and b, not the sentence."""
        words = [w for w, _ in banned()]
        self.assertIn('tracking issue', words)
        for w in words:
            self.assertNotIn('never', w)

    def test_carries_the_term_that_bans_each_word(self):
        pairs = dict(banned())
        self.assertEqual(pairs['the dashboard'], 'Published copy')


class BannedSynonymTests(unittest.TestCase):
    def test_reports_a_banned_word_with_its_term(self):
        found = ste_lint.scan_text('d.md', 'We read the dashboard daily.\n', banned())
        hits = [f for f in found if f.rule == ste_lint.RULE_BANNED]
        self.assertEqual(len(hits), 1)
        self.assertIn('the dashboard', hits[0].message)
        self.assertIn('Published copy', hits[0].message)

    def test_ignores_a_banned_word_inside_a_fenced_block(self):
        text = 'Fine prose.\n\n```\nthe dashboard\n```\n'
        hits = [f for f in ste_lint.scan_text('d.md', text, banned())
                if f.rule == ste_lint.RULE_BANNED]
        self.assertEqual(hits, [])


class RuleTests(unittest.TestCase):
    def rules(self, text):
        return [f.rule for f in ste_lint.scan_text('d.md', text, [])]

    def test_long_description_sentence(self):
        text = 'The ' + 'word ' * 30 + 'ends here.\n'
        self.assertIn(ste_lint.RULE_LONG_DESCRIPTION, self.rules(text))

    def test_short_description_sentence_is_clean(self):
        self.assertEqual(self.rules('The run is short.\n'), [])

    def test_long_instruction_sentence_uses_the_20_word_cap(self):
        text = 'Run the ' + 'thing ' * 20 + 'now.\n'
        self.assertIn(ste_lint.RULE_LONG_INSTRUCTION, self.rules(text))

    def test_passive_voice(self):
        self.assertIn(ste_lint.RULE_PASSIVE,
                      self.rules('The body was rendered by the tool.\n'))

    def test_present_perfect_tense(self):
        self.assertIn(ste_lint.RULE_PERFECT_TENSE,
                      self.rules('The tool has printed the report.\n'))

    def test_noun_cluster_of_four_words(self):
        # `noun_cluster` resets on any IMPERATIVES member, and both `check` and
        # `run` are in that set — so an example built from them measures 3, not
        # 5, and silently proves nothing. This one measures 5.
        self.assertIn(ste_lint.RULE_NOUN_CLUSTER,
                      self.rules('The factory issue body budget table grew.\n'))

    def test_multiple_instructions_in_one_sentence(self):
        self.assertIn(ste_lint.RULE_MULTI_INSTRUCTION,
                      self.rules('Run the build, and commit the result.\n'))

    def test_long_paragraph(self):
        text = ' '.join('Line %d is here.' % i for i in range(8)) + '\n'
        self.assertIn(ste_lint.RULE_LONG_PARAGRAPH, self.rules(text))


class ExitCodeTests(unittest.TestCase):
    """AC3 and AC4."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)
        return path

    def run_main(self, argv):
        # `--root ROOT` is not optional: without it `load_glossary` reads
        # ./CONTEXT.md, so the banned list is empty whenever the tests run from
        # anywhere but the repository root, and AC4 fails with 0 != 1.
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = ste_lint.main(argv + ['--root', ROOT])
        return code, buf.getvalue()

    def test_a_forty_word_passive_sentence_prints_and_exits_zero(self):
        """AC3."""
        sentence = ('The body ' + 'of the record ' * 12
                    + 'was rendered by the publisher.\n')
        path = self.write('long.md', sentence)
        code, out = self.run_main([path])
        self.assertEqual(code, 0)
        self.assertIn(ste_lint.RULE_PASSIVE, out)
        self.assertIn(ste_lint.RULE_LONG_DESCRIPTION, out)

    def test_a_banned_word_exits_one_and_names_the_term(self):
        """AC4."""
        path = self.write('banned.md', 'Open the dashboard first.\n')
        code, out = self.run_main([path])
        self.assertEqual(code, 1)
        self.assertIn('dashboard', out)
        self.assertIn('Published copy', out)

    def test_a_clean_file_exits_zero_and_prints_nothing(self):
        path = self.write('clean.md', 'The tool is small.\n')
        code, out = self.run_main([path])
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), '')

    def test_the_capture_harness_actually_captures(self):
        """Guards the whole class: a `_report` that binds sys.stdout at import
        time prints past redirect_stdout, and every assertIn above then passes
        or fails against a permanently empty string."""
        path = self.write('probe.md', 'Open the dashboard first.\n')
        _code, out = self.run_main([path])
        self.assertTrue(out.strip(), 'redirect_stdout captured nothing')


class CliTests(unittest.TestCase):
    def test_module_runs_as_a_script(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, 'tools', 'ste_lint.py'), '--help'],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0)
        self.assertIn('--all', proc.stdout)
        self.assertIn('--issue', proc.stdout)


class DiscoveryTests(unittest.TestCase):
    """R12 and AC7."""

    TRACKED = [
        'CLAUDE.md',
        'CONTEXT.md',
        'CLAUDE.local.md',
        'Makefile',
        'docs/dev-workflow.md',
        'docs/STORY_BIBLE.md',
        'docs/game/game-design.md',
        'docs/plans/2026-04-04-turret-fire-and-disappear.md',
        '.claude/skills/factory/SKILL.md',
        '.claude/skills/simplified-technical-english/SKILL.md',
        '.claude/agents/gbdk-expert.md',
        '.claude/skill-overlays/writing-plans.md',
        'tests/fixtures/factory/expected_pr_body.md',
        'tests/fixtures/factory/other.md',
        'src/main.c',
    ]

    def found(self):
        return ste_lint.discover('.', tracked=self.TRACKED)

    def test_includes_the_documented_set(self):
        for path in ('CLAUDE.md', 'CONTEXT.md', 'docs/dev-workflow.md',
                     'docs/plans/2026-04-04-turret-fire-and-disappear.md',
                     '.claude/skills/factory/SKILL.md',
                     '.claude/agents/gbdk-expert.md',
                     'tests/fixtures/factory/expected_pr_body.md'):
            self.assertIn(path, self.found())

    def test_excludes_the_story_bible(self):
        """AC7."""
        self.assertNotIn('docs/STORY_BIBLE.md', self.found())

    def test_excludes_game_docs_local_claude_overlays_and_the_vendored_skill(self):
        for path in ('docs/game/game-design.md', 'CLAUDE.local.md',
                     '.claude/skill-overlays/writing-plans.md',
                     '.claude/skills/simplified-technical-english/SKILL.md'):
            self.assertNotIn(path, self.found())

    def test_excludes_non_markdown_and_unlisted_markdown(self):
        self.assertNotIn('src/main.c', self.found())
        self.assertNotIn('Makefile', self.found())
        self.assertNotIn('tests/fixtures/factory/other.md', self.found())

    def test_is_sorted_and_deduplicated(self):
        found = self.found()
        self.assertEqual(found, sorted(set(found)))

    def test_the_real_repository_set_is_non_empty_and_excludes_the_bible(self):
        real = ste_lint.discover(ROOT)
        self.assertIn('CONTEXT.md', real)
        self.assertNotIn('docs/STORY_BIBLE.md', real)


class BaselineTests(unittest.TestCase):
    """R11 and AC6."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.baseline = os.path.join(self.tmp, 'baseline.json')
        with open(os.path.join(self.tmp, 'CONTEXT.md'), 'w',
                  encoding='utf-8', newline='\n') as fh:
            fh.write(GLOSSARY)
        self.doc = os.path.join(self.tmp, 'doc.md')
        self.write_doc('The body was rendered by the publisher.\n')

    def write_doc(self, text):
        with open(self.doc, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(text)

    def scan(self):
        return ste_lint.scan_file(self.doc, banned(), display='doc.md')

    def test_write_then_suppress_reports_nothing(self):
        ste_lint.write_baseline(self.baseline, self.scan())
        loaded = ste_lint.load_baseline(self.baseline)
        self.assertEqual(ste_lint.suppress(self.scan(), loaded), [])

    def test_a_new_violation_is_reported(self):
        """AC6 — the baseline suppresses only what it recorded."""
        ste_lint.write_baseline(self.baseline, self.scan())
        self.write_doc('The body was rendered by the publisher.\n\n'
                       'The record has printed the report.\n')
        loaded = ste_lint.load_baseline(self.baseline)
        fresh = ste_lint.suppress(self.scan(), loaded)
        self.assertEqual([f.rule for f in fresh], [ste_lint.RULE_PERFECT_TENSE])

    def test_a_repeat_of_a_recorded_violation_is_counted(self):
        ste_lint.write_baseline(self.baseline, self.scan())
        self.write_doc('The body was rendered by the publisher.\n\n'
                       'The body was rendered by the publisher.\n')
        fresh = ste_lint.suppress(self.scan(),
                                  ste_lint.load_baseline(self.baseline))
        self.assertEqual(len(fresh), 1)

    def test_a_banned_hit_is_suppressed_by_the_baseline_too(self):
        """P2 — otherwise --all can never exit 0 on this tree."""
        self.write_doc('Open the dashboard first.\n')
        ste_lint.write_baseline(self.baseline, self.scan())
        fresh = ste_lint.suppress(self.scan(),
                                  ste_lint.load_baseline(self.baseline))
        self.assertEqual(fresh, [])

    def test_a_missing_baseline_suppresses_nothing(self):
        loaded = ste_lint.load_baseline(os.path.join(self.tmp, 'absent.json'))
        self.assertEqual(len(ste_lint.suppress(self.scan(), loaded)),
                         len(self.scan()))

    def test_the_baseline_file_is_deterministic_json(self):
        ste_lint.write_baseline(self.baseline, self.scan())
        first = open(self.baseline, encoding='utf-8', newline='').read()
        ste_lint.write_baseline(self.baseline, self.scan())
        second = open(self.baseline, encoding='utf-8', newline='').read()
        self.assertEqual(first, second)
        self.assertTrue(first.endswith('\n'))
        json.loads(first)


class RunAllTests(unittest.TestCase):
    """AC5 and AC8 against the real tree."""

    def test_all_exits_zero_and_prints_no_rule_finding(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = ste_lint.main(['--all', '--root', ROOT])
        self.assertEqual(code, 0, buf.getvalue())
        for rule in ste_lint.RULES:
            self.assertNotIn(rule, buf.getvalue())
        self.assertNotIn(ste_lint.RULE_BANNED, buf.getvalue())

    def test_the_real_set_is_the_documented_one(self):
        """R12 — a bare `*.md` glob would sweep the whole tree."""
        found = ste_lint.discover(ROOT)
        self.assertIn('CONTEXT.md', found)
        self.assertIn('docs/dev-workflow.md', found)
        for path in found:
            self.assertTrue(
                '/' not in path
                or path.startswith(('docs/', '.claude/skills/',
                                    '.claude/agents/',
                                    'tests/fixtures/factory/expected_')),
                path)

    def test_all_never_exits_nonzero_on_a_fresh_banned_hit(self):
        """P7 — a docs edit that writes one more `step` must not turn CI red."""
        tmp = tempfile.mkdtemp()
        with open(os.path.join(tmp, 'CONTEXT.md'), 'w',
                  encoding='utf-8', newline='\n') as fh:
            fh.write(GLOSSARY)
        os.makedirs(os.path.join(tmp, 'docs'))
        with open(os.path.join(tmp, 'docs', 'x.md'), 'w',
                  encoding='utf-8', newline='\n') as fh:
            fh.write('Open the dashboard now.\n')
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = ste_lint.run_all(tmp, banned(),
                                    baseline_path=os.path.join(tmp, 'none.json'),
                                    tracked=['CONTEXT.md', 'docs/x.md'])
        self.assertEqual(code, 0)
        self.assertIn('the dashboard', buf.getvalue())


if __name__ == '__main__':
    unittest.main()
