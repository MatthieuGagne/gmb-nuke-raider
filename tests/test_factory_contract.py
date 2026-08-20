"""The factory's contract documents, held to the rules they state.

These are the only tests in the suite that read the skill text itself. They
exist because #654 was a contradiction between two documents that no code path
could catch: SKILL.md claimed every command was wrapped, stages.md wrapped none
of BUILD's, and the run issue silently lost the evidence.

Every check normalizes whitespace before searching. A hard wrap that splits a
phrase across two lines must never fail a correct document — the prose is
re-wrapped freely, the rule is what is pinned.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import factory_run

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_DIR = os.path.join(ROOT, '.claude', 'skills', 'factory')
STAGES_MD = os.path.join(SKILL_DIR, 'references', 'stages.md')
SKILL_MD = os.path.join(SKILL_DIR, 'SKILL.md')
SDD_OVERLAY = os.path.join(ROOT, '.claude', 'skill-overlays',
                           'subagent-driven-development.md')


def read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def flat(text):
    """One space for every whitespace run, so a hard wrap never fails a file."""
    return re.sub(r'\s+', ' ', text)


def section(text, heading, level='## '):
    """The body under an exact ``<level><heading>`` line.

    Ends at the next heading of the same depth **or shallower**. Stopping only
    on *level* would let a trailing ``### `` subsection swallow every ``## ``
    section after it — harmless today, a trap the first time a document is
    reordered.
    """
    stops = tuple('#' * n + ' ' for n in range(1, len(level.strip()) + 1))
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == level + heading:
            rest = lines[i + 1:]
            for j, later in enumerate(rest):
                if later.startswith(stops):
                    return '\n'.join(rest[:j])
            return '\n'.join(rest)
    return None


class TestStagesWrapTheirCommands(unittest.TestCase):
    """#654 R5/AC5: no stage is exempt, and BUILD least of all."""

    def test_every_stage_section_wraps_at_least_one_command(self):
        text = read(STAGES_MD)
        for stage in factory_run.STAGES:
            body = section(text, stage)
            self.assertIsNotNone(body, 'no "## %s" section in %s'
                                 % (stage, STAGES_MD))
            self.assertIn('LOG %s' % stage, flat(body),
                          '%s runs commands the stage log never sees' % stage)

    def test_build_opens_by_logging_the_head_it_starts_from(self):
        """AC1's floor: unconditional, so BUILD.log exists however BUILD ends."""
        body = flat(section(read(STAGES_MD), 'BUILD'))
        self.assertIn('LOG BUILD -- git log --oneline -1', body)

    def test_build_names_both_actors(self):
        """Phrases only the new block carries.

        Asserting the bare words 'controller' and 'implementer' would pass
        today and after any deletion: step 6's #590 anecdote already contains
        both, and survives the rewrite.
        """
        body = flat(section(read(STAGES_MD), 'BUILD'))
        self.assertIn('Who wraps what inside BUILD', body)
        self.assertIn('A dispatched implementer** wraps its own', body)
        self.assertIn('python tools/factory_log.py --stage BUILD --issue <N> --',
                      body)


class TestSkillAndStagesAgree(unittest.TestCase):
    """#654 R5/AC5: one document must not contradict the other."""

    def test_the_rule_does_not_claim_more_than_stages_delivers(self):
        """The exact sentence #654 names as wrong."""
        self.assertNotIn('No stage runs a command directly',
                         flat(read(SKILL_MD)))

    def test_the_rule_names_who_wraps_what(self):
        body = flat(read(SKILL_MD))
        self.assertIn('Who wraps what', body)
        self.assertIn('does not cross a dispatch', body)

    def test_bookkeeping_is_declared_unwrapped(self):
        """stages.md shows factory_event.py bare in every stage; say so.

        Not `assertIn('factory_event.py', ...)`: SKILL.md's '## Recording
        state' section already names that file eight times, so the bare
        substring is green before the edit and proves nothing.
        """
        body = flat(read(SKILL_MD))
        self.assertIn('Registry and publisher bookkeeping', body)
        self.assertIn('The one publisher call that is wrapped is SHIP', body)

    def test_the_bookkeeping_exemption_matches_stages_md(self):
        """AC5, mechanically: the claim is checked, not taken on trust.

        A prose claim about what gets wrapped is exactly what #654 found
        wrong, so this one is verified against the other document instead of
        being read for plausibility.
        """
        wrapped = [line.strip() for line in read(STAGES_MD).splitlines()
                   if 'LOG ' in line and ' -- ' in line]
        self.assertEqual(
            [ln for ln in wrapped if 'factory_event.py' in ln], [])
        self.assertEqual(
            [ln for ln in wrapped if 'factory_status.py' in ln], [])
        publisher = [ln for ln in wrapped if 'factory_publish.py' in ln]
        self.assertEqual(len(publisher), 1, publisher)
        self.assertIn('--open-pr', publisher[0])
