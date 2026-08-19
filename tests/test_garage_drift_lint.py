#!/usr/bin/env python3
"""Tests for tools/garage_drift_lint.py"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import garage_drift_lint as lint


CONFIG = (
    '#ifndef CONFIG_H\n'
    '#define CONFIG_H\n'
    '\n'
    '/* a comment mentioning #define NOT_A_DEFINE */\n'
    '#define MAX_NPCS     8\n'
    '#define GEAR1_MAX_SPEED        2u\n'
    '#define MAX_RACERS           (MAX_ENEMY_RACERS + 1u)  /* player + enemies */\n'
    '  #define INDENTED_ONE 3\n'
    '\n'
    '#endif\n'
)

NAMES = ['CONFIG_H', 'MAX_NPCS', 'GEAR1_MAX_SPEED', 'MAX_RACERS', 'INDENTED_ONE']


class TestFindDefines(unittest.TestCase):
    def test_finds_every_name_in_header_order(self):
        self.assertEqual(lint.find_defines(CONFIG), NAMES)

    def test_ignores_a_define_word_inside_a_comment(self):
        self.assertNotIn('NOT_A_DEFINE', lint.find_defines(CONFIG))

    def test_takes_the_name_not_the_value(self):
        self.assertNotIn('8', lint.find_defines(CONFIG))



def write_tunables(path, names_to_classes):
    entries = {
        name: {'class': cls, 'reason': 'test fixture'}
        for name, cls in names_to_classes.items()
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'_shape': 'test fixture', 'entries': entries}, f)


class TestLoadClassified(unittest.TestCase):
    def test_returns_every_entry_name(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'tunables.json')
            write_tunables(p, {'CONFIG_H': 'marker', 'MAX_NPCS': 'structural'})
            self.assertEqual(lint.load_classified(p), {'CONFIG_H', 'MAX_NPCS'})

    def test_every_class_counts_as_classified(self):
        """R4 says "neither tunable nor structural", but the schema has four
        classes and Garage's own check treats any entry as classified. A
        literal reading would fail on CONFIG_H, a marker.
        """
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'tunables.json')
            write_tunables(p, {
                'A': 'tunable', 'B': 'structural', 'C': 'derived', 'D': 'marker',
            })
            self.assertEqual(lint.load_classified(p), {'A', 'B', 'C', 'D'})


TUNABLES = os.path.join('tools', 'garage', 'tunables.json')


def make_garage(parent, dirname):
    """A directory that looks like a Garage checkout: it holds the
    classification file at the expected relative path.
    """
    root = os.path.join(parent, dirname)
    os.makedirs(os.path.join(root, 'tools', 'garage'), exist_ok=True)
    write_tunables(os.path.join(root, TUNABLES), {'CONFIG_H': 'marker'})
    return root


class TestFindGarageCheckout(unittest.TestCase):
    def test_finds_a_sibling_whose_remote_matches(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, 'nuke-raider')
            os.makedirs(repo)
            garage = make_garage(d, 'nuke-raider-garage')
            found = lint.find_garage_checkout(
                repo,
                remote_reader=lambda p: 'https://github.com/X/nuke-raiders-garage.git',
            )
            self.assertEqual(found, garage)

    def test_dirname_does_not_have_to_match_the_repo_name(self):
        """The checkout on the author's machine is 'nuke-raider-garage' while
        the repository is 'nuke-raiders-garage'. Matching on the remote and
        not on the directory name is what makes the check actually run.
        """
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, 'nuke-raider')
            os.makedirs(repo)
            garage = make_garage(d, 'some-other-name')
            found = lint.find_garage_checkout(
                repo, remote_reader=lambda p: 'git@github.com:X/nuke-raiders-garage.git',
            )
            self.assertEqual(found, garage)

    def test_returns_none_when_no_sibling_holds_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, 'nuke-raider')
            os.makedirs(repo)
            os.makedirs(os.path.join(d, 'unrelated'))
            self.assertIsNone(
                lint.find_garage_checkout(repo, remote_reader=lambda p: 'x/nuke-raiders-garage')
            )

    def test_returns_none_when_the_remote_does_not_match(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, 'nuke-raider')
            os.makedirs(repo)
            make_garage(d, 'nuke-raider-garage')
            self.assertIsNone(
                lint.find_garage_checkout(repo, remote_reader=lambda p: 'git@github.com:X/other.git')
            )

    def test_returns_none_when_the_sibling_is_not_a_git_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            repo = os.path.join(d, 'nuke-raider')
            os.makedirs(repo)
            make_garage(d, 'nuke-raider-garage')
            self.assertIsNone(lint.find_garage_checkout(repo, remote_reader=lambda p: None))

    def test_does_not_consider_the_repository_itself(self):
        """A repo that somehow holds the file must not match itself."""
        with tempfile.TemporaryDirectory() as d:
            repo = make_garage(d, 'nuke-raider')
            self.assertIsNone(
                lint.find_garage_checkout(repo, remote_reader=lambda p: 'x/nuke-raiders-garage')
            )

    def test_the_default_remote_reader_returns_none_outside_a_checkout(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(lint.git_remote(d))


def make_repo(parent, config_text):
    root = os.path.join(parent, 'nuke-raider')
    os.makedirs(os.path.join(root, 'src'), exist_ok=True)
    with open(os.path.join(root, 'src', 'config.h'), 'w', encoding='utf-8') as f:
        f.write(config_text)
    return root


def run_capturing(**kwargs):
    """Run the check, returning (exit_code, stdout). Captured because a
    passing suite must never print the word FAIL.
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = lint.run(**kwargs)
    return code, buf.getvalue()


class TestRun(unittest.TestCase):
    def test_passes_when_every_define_is_classified(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define MAX_NPCS 8\n')
            t = os.path.join(d, 'tunables.json')
            write_tunables(t, {'CONFIG_H': 'marker', 'MAX_NPCS': 'structural'})
            code, out = run_capturing(repo_root=repo, tunables_path=t)
            self.assertEqual(code, 0, out)
            self.assertIn('OK', out)
            self.assertNotIn('FAIL', out)

    def test_fails_on_an_unclassified_define(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define BRAND_NEW_DIAL 7\n')
            t = os.path.join(d, 'tunables.json')
            write_tunables(t, {'CONFIG_H': 'marker'})
            code, out = run_capturing(repo_root=repo, tunables_path=t)
            self.assertEqual(code, 1)

    def test_the_failure_names_the_define(self):
        """AC4: the failure must name it -- a bare exit code makes the
        author hunt for which of 133 lines is the new one.
        """
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define BRAND_NEW_DIAL 7\n')
            t = os.path.join(d, 'tunables.json')
            write_tunables(t, {'CONFIG_H': 'marker'})
            _, out = run_capturing(repo_root=repo, tunables_path=t)
            self.assertIn('BRAND_NEW_DIAL', out)

    def test_the_failure_says_where_to_fix_it(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define BRAND_NEW_DIAL 7\n')
            t = os.path.join(d, 'tunables.json')
            write_tunables(t, {'CONFIG_H': 'marker'})
            _, out = run_capturing(repo_root=repo, tunables_path=t)
            self.assertIn('tunables.json', out)

    def test_names_every_unclassified_define_not_just_the_first(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define ONE 1\n#define TWO 2\n')
            t = os.path.join(d, 'tunables.json')
            write_tunables(t, {'CONFIG_H': 'marker'})
            _, out = run_capturing(repo_root=repo, tunables_path=t)
            self.assertIn('ONE', out)
            self.assertIn('TWO', out)

    def test_a_stale_entry_is_not_reported(self):
        """The reverse drift -- an entry whose #define is gone -- is Garage's
        to report. Its fix lives in a repository this suite does not own, so
        reporting it here would mean this suite could only go green by
        someone editing elsewhere.
        """
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n')
            t = os.path.join(d, 'tunables.json')
            write_tunables(t, {'CONFIG_H': 'marker', 'DELETED_LONG_AGO': 'tunable'})
            code, out = run_capturing(repo_root=repo, tunables_path=t)
            self.assertEqual(code, 0, out)
            self.assertNotIn('DELETED_LONG_AGO', out)


class TestRunWithoutAGarageCheckout(unittest.TestCase):
    """AC5: green, and it says it did not run."""

    def test_succeeds_when_no_garage_checkout_is_found(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define ANYTHING 1\n')
            code, _ = run_capturing(repo_root=repo)
            self.assertEqual(code, 0)

    def test_says_it_did_not_run(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define ANYTHING 1\n')
            _, out = run_capturing(repo_root=repo)
            self.assertIn('did not run', out)

    def test_stays_quiet_about_failure(self):
        with tempfile.TemporaryDirectory() as d:
            repo = make_repo(d, '#define CONFIG_H\n#define ANYTHING 1\n')
            _, out = run_capturing(repo_root=repo)
            self.assertNotIn('FAIL', out)


class TestAgainstThisRepository(unittest.TestCase):
    """The gate itself. Discovery finds this module, `make test-tools` and
    .githooks/pre-commit both run discovery, so an unclassified #define
    fails the suite at the commit that introduces it (#612 R4).

    It is green two ways: the drift check passes, or no Garage checkout is
    present and the check reports that it did not run.
    """

    def test_config_h_has_not_drifted_from_tunables_json(self):
        code, out = run_capturing()
        self.assertEqual(code, 0, out)


if __name__ == '__main__':
    unittest.main()
