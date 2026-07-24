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


if __name__ == '__main__':
    unittest.main()
