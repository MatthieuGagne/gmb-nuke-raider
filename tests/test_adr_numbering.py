#!/usr/bin/env python3
"""ADR sequence numbers must be unique.

Two concurrent branches can each scan docs/adr/, each correctly allocate the
next free number, and still collide: the filenames differ, so git reports no
conflict and master quietly carries two ADR 0002s (#441, 2026-07-26). Nothing
else in this repository can notice that — this test is the mechanism.
"""
import os
import re
import unittest
from collections import defaultdict

ADR_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs', 'adr')
ADR_NAME = re.compile(r'^(\d{4})-[a-z0-9-]+\.md$')


def adr_files(directory=ADR_DIR):
    """Return sorted ADR filenames in *directory*; non-ADR names are ignored."""
    if not os.path.isdir(directory):
        return []
    return sorted(n for n in os.listdir(directory) if ADR_NAME.match(n))


def duplicate_numbers(names):
    """Return {number: [filenames]} for every number claimed more than once."""
    by_number = defaultdict(list)
    for name in names:
        by_number[ADR_NAME.match(name).group(1)].append(name)
    return {n: sorted(f) for n, f in by_number.items() if len(f) > 1}


class DuplicateDetectionTests(unittest.TestCase):
    def test_reports_both_colliding_files(self):
        self.assertEqual(
            duplicate_numbers(['0002-a.md', '0002-b.md', '0003-c.md']),
            {'0002': ['0002-a.md', '0002-b.md']})

    def test_unique_numbers_report_nothing(self):
        self.assertEqual(duplicate_numbers(['0001-a.md', '0002-b.md']), {})

    def test_three_way_collision_reports_all_three(self):
        dupes = duplicate_numbers(['0004-a.md', '0004-b.md', '0004-c.md'])
        self.assertEqual(len(dupes['0004']), 3)


class RepositoryAdrTests(unittest.TestCase):
    def test_adr_directory_is_not_empty(self):
        # Without this, a path typo would make the collision check vacuous —
        # exactly the failure mode this issue is about.
        self.assertTrue(adr_files(), 'no ADRs found at %s' % ADR_DIR)

    def test_no_duplicate_sequence_numbers(self):
        dupes = duplicate_numbers(adr_files())
        detail = '; '.join('%s claimed by %s' % (n, ', '.join(f))
                           for n, f in sorted(dupes.items()))
        self.assertEqual(dupes, {}, 'ADR number collision: ' + detail)


if __name__ == '__main__':
    unittest.main()
