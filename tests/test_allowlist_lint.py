"""Tests for tools/allowlist_lint.py — hygiene rules."""
import unittest

from tools.allowlist_lint import (check_hygiene, parse_rule, rule_matches)


def settings(allow, deny=None):
    return {'permissions': {'allow': allow, 'deny': deny or []}}


class ParseRuleTests(unittest.TestCase):
    def test_parses_bash_canonical(self):
        self.assertEqual(parse_rule('Bash(git:*)'), ('Bash', 'git'))

    def test_parses_powershell_canonical(self):
        self.assertEqual(parse_rule('PowerShell(git *)'), ('PowerShell', 'git'))

    def test_rejects_bash_space_form(self):
        self.assertIsNone(parse_rule('Bash(gh issue *)'))

    def test_rejects_powershell_colon_form(self):
        self.assertIsNone(parse_rule('PowerShell(git:*)'))

    def test_rejects_interior_wildcard(self):
        self.assertIsNone(parse_rule('Bash(git *x:*)'))

    def test_non_shell_tool_yields_none_prefix(self):
        self.assertEqual(parse_rule('Read(**)'), ('Read', None))


class RuleMatchesTests(unittest.TestCase):
    def test_exact_command(self):
        self.assertTrue(rule_matches('make', 'make'))

    def test_prefix_at_word_boundary(self):
        self.assertTrue(rule_matches('git', 'git push origin x'))

    def test_does_not_match_longer_word(self):
        self.assertFalse(rule_matches('git', 'github-cli status'))


class HygieneTests(unittest.TestCase):
    def test_clean_list_passes(self):
        self.assertEqual(
            check_hygiene(settings(['Bash(git:*)', 'PowerShell(git *)'])), [])

    def test_rejects_windows_absolute_path(self):
        errs = check_hygiene(settings([r'Bash(java -jar C:\Tools\e.jar:*)']))
        self.assertTrue(any('absolute path' in e for e in errs))

    def test_rejects_unc_absolute_path(self):
        errs = check_hygiene(settings(['Read(//c/Code/nuke-raider/**)']))
        self.assertTrue(any('absolute path' in e for e in errs))

    def test_rejects_non_canonical_form(self):
        errs = check_hygiene(settings(['Bash(gh issue *)']))
        self.assertTrue(any('canonical form' in e for e in errs))

    def test_rejects_wildcard_free_shell_entry(self):
        errs = check_hygiene(settings(['Bash(git status)']))
        self.assertTrue(any('canonical form' in e for e in errs))

    def test_rejects_redundant_entry(self):
        errs = check_hygiene(settings(['Bash(git add:*)', 'Bash(git:*)']))
        self.assertTrue(any('redundant' in e for e in errs))

    def test_does_not_flag_sibling_prefixes(self):
        errs = check_hygiene(settings(['Bash(git:*)', 'Bash(gh:*)']))
        self.assertEqual([e for e in errs if 'redundant' in e], [])

    def test_rejects_unsorted(self):
        errs = check_hygiene(settings(['Bash(make:*)', 'Bash(git:*)']))
        self.assertTrue(any('sorted' in e for e in errs))

    def test_rejects_allow_deny_collision(self):
        errs = check_hygiene(
            settings(['Bash(git push -f:*)'], ['Bash(git push -f:*)']))
        self.assertTrue(any('both allow and deny' in e for e in errs))

    def test_non_shell_entries_exempt_from_canonical_form(self):
        errs = check_hygiene(
            settings(['Read(**)', 'Skill(build)', 'WebSearch']))
        self.assertEqual(errs, [])


class TrackedSettingsTests(unittest.TestCase):
    """The real tracked file must be clean. Turns red in Task 9 until migrated."""

    def test_tracked_settings_pass_hygiene(self):
        from tools.allowlist_lint import load_settings
        self.assertEqual(check_hygiene(load_settings('.claude/settings.json')), [])


class InventoryTests(unittest.TestCase):
    def test_inventory_parses(self):
        from tools.allowlist_lint import load_inventory
        inv = load_inventory('tests/fixtures/factory_commands.txt')
        self.assertGreater(len(inv), 10)
        for tool, command in inv:
            self.assertIn(tool, ('Bash', 'PowerShell'))
            self.assertTrue(command)

    def test_comments_and_blanks_ignored(self):
        import tempfile
        from tools.allowlist_lint import load_inventory
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False,
                                         encoding='utf-8') as fh:
            fh.write('# a comment\n\nBash: make clean\n')
            path = fh.name
        self.assertEqual(load_inventory(path), [('Bash', 'make clean')])


class CoverageTests(unittest.TestCase):
    INV = [('Bash', 'make clean'), ('Bash', 'git fetch origin')]

    def test_covered_inventory_passes(self):
        from tools.allowlist_lint import check_coverage
        s = settings(['Bash(git:*)', 'Bash(make:*)'])
        self.assertEqual(check_coverage(s, self.INV), [])

    def test_missing_rule_fails(self):
        """AC3: removing a rule a fixture command depends on turns this red."""
        from tools.allowlist_lint import check_coverage
        s = settings(['Bash(git:*)'])          # Bash(make:*) removed
        errs = check_coverage(s, self.INV)
        self.assertTrue(any('make clean' in e for e in errs))

    def test_deny_rule_fails_coverage(self):
        from tools.allowlist_lint import check_coverage
        s = settings(['Bash(git:*)'], ['Bash(git fetch:*)'])
        errs = check_coverage(s, [('Bash', 'git fetch origin')])
        self.assertTrue(any('deny rule' in e for e in errs))


class TrackedCoverageTests(unittest.TestCase):
    """The real pairing must pass. Turns green in Task 9."""

    def test_tracked_settings_cover_inventory(self):
        from tools.allowlist_lint import (check_coverage, load_inventory,
                                          load_settings)
        errs = check_coverage(load_settings('.claude/settings.json'),
                              load_inventory('tests/fixtures/factory_commands.txt'))
        self.assertEqual(errs, [])


if __name__ == '__main__':
    unittest.main()
