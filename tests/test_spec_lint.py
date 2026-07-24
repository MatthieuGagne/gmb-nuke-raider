"""Tests for tools/spec_lint.py"""
import json
import os
import subprocess
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import spec_lint

FIXTURES = os.path.join(os.path.dirname(__file__), 'fixtures')
SCRIPT = os.path.join(os.path.dirname(__file__), '..', 'tools', 'spec_lint.py')


def _fixture(name):
    with open(os.path.join(FIXTURES, name), encoding='utf-8') as fh:
        return fh.read()


class TestSectionPresence(unittest.TestCase):
    def test_valid_fixture_passes(self):
        result = spec_lint.lint(_fixture('spec_valid.md'))
        self.assertTrue(result['valid'])
        self.assertEqual(result['errors'], [])

    def test_valid_fixture_all_sections_present(self):
        result = spec_lint.lint(_fixture('spec_valid.md'))
        for name in ('Goal', 'Requirements', 'Acceptance Criteria',
                     'Out of Scope', 'Files Impacted'):
            self.assertTrue(result['sections'][name], name)

    def test_missing_section_is_reported(self):
        result = spec_lint.lint(_fixture('spec_missing_section.md'))
        self.assertFalse(result['valid'])
        self.assertFalse(result['sections']['Out of Scope'])
        self.assertTrue(any('Out of Scope' in e for e in result['errors']))

    def test_empty_section_is_reported(self):
        result = spec_lint.lint(_fixture('spec_empty_criteria.md'))
        self.assertFalse(result['valid'])
        self.assertFalse(result['sections']['Acceptance Criteria'])
        self.assertTrue(any('Acceptance Criteria' in e for e in result['errors']))

    def test_comment_only_section_is_empty(self):
        body = (
            "## Goal\ng\n\n## Requirements\n- R1: x\n\n"
            "## Acceptance Criteria\n<!-- fill me in -->\n\n"
            "## Out of Scope\n- none\n\n## Files Impacted\n- `src/a.c` — x\n"
        )
        result = spec_lint.lint(body)
        self.assertFalse(result['sections']['Acceptance Criteria'])
        self.assertTrue(any('Acceptance Criteria' in e for e in result['errors']))

    def test_comment_plus_content_section_not_empty(self):
        body = (
            "## Goal\ng\n\n## Requirements\n- R1: x\n\n"
            "## Acceptance Criteria\n<!-- note -->\n- [ ] AC1: x\n\n"
            "## Out of Scope\n- none\n\n## Files Impacted\n- `src/a.c` — x\n"
        )
        result = spec_lint.lint(body)
        self.assertTrue(result['sections']['Acceptance Criteria'])


class TestMinimumEntries(unittest.TestCase):
    _NO_REQ_LINES = (
        "## Goal\ng\n\n## Requirements\nsome prose but no R lines\n\n"
        "## Acceptance Criteria\n- [ ] AC1: x\n\n## Out of Scope\n- none\n\n"
        "## Files Impacted\n- `src/a.c` — x\n"
    )
    _NO_CHECKBOX = (
        "## Goal\ng\n\n## Requirements\n- R1: x\n\n"
        "## Acceptance Criteria\n- just a bullet, no checkbox\n\n"
        "## Out of Scope\n- none\n\n## Files Impacted\n- `src/a.c` — x\n"
    )
    _NO_FILE_ENTRY = (
        "## Goal\ng\n\n## Requirements\n- R1: x\n\n"
        "## Acceptance Criteria\n- [ ] AC1: x\n\n## Out of Scope\n- none\n\n"
        "## Files Impacted\n\n"
    )

    def test_requires_at_least_one_R_line(self):
        result = spec_lint.lint(self._NO_REQ_LINES)
        self.assertFalse(result['valid'])
        self.assertTrue(any('requirement' in e.lower() for e in result['errors']))

    def test_requires_at_least_one_checkbox(self):
        result = spec_lint.lint(self._NO_CHECKBOX)
        self.assertFalse(result['valid'])
        self.assertTrue(any('checkbox' in e.lower() for e in result['errors']))

    def test_requires_at_least_one_impacted_entry(self):
        # Files Impacted heading present but body empty -> caught as empty section.
        result = spec_lint.lint(self._NO_FILE_ENTRY)
        self.assertFalse(result['valid'])
        self.assertTrue(any('Files Impacted' in e for e in result['errors']))

    def test_valid_fixture_still_passes(self):
        self.assertTrue(spec_lint.lint(_fixture('spec_valid.md'))['valid'])


if __name__ == '__main__':
    unittest.main()
