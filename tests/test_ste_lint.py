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


if __name__ == '__main__':
    unittest.main()
