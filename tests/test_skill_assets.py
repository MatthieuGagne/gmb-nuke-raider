"""Structural checks on the authored skills — R5 of issue #729.

omp loads a skill from its SKILL.md frontmatter, reading `name` and
`description`. If a future edit drops or renames either key, omp silently stops
loading the skill. This test pins both keys so that break is caught by the tool
suite rather than at dispatch time.
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, ".claude", "skills")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def split_frontmatter(text):
    """Return (frontmatter_dict, body); tolerate absent frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            fm = {}
            for line in lines[1:i]:
                if ':' in line:
                    key, _, value = line.partition(':')
                    fm[key.strip()] = value.strip()
            return fm, '\n'.join(lines[i + 1:]).lstrip('\n')
    return {}, text


class TestSkills(unittest.TestCase):
    def test_every_skill_frontmatter_has_omp_loadable_keys(self):
        skill_dirs = sorted(
            d for d in os.listdir(SKILLS)
            if os.path.isdir(os.path.join(SKILLS, d)))
        self.assertTrue(skill_dirs, 'no skills under .claude/skills/')
        for name in skill_dirs:
            path = os.path.join(SKILLS, name, "SKILL.md")
            self.assertTrue(os.path.isfile(path), "missing SKILL.md for %s" % name)
            text = read(path)
            fm, body = split_frontmatter(text)
            self.assertEqual(fm.get("name"), name,
                             "%s: frontmatter `name` must equal the directory name" % path)
            self.assertTrue(fm.get("description"),
                            "%s: frontmatter `description` is required for omp loading" % path)
            self.assertTrue(body.strip(), "%s: empty body" % path)


if __name__ == "__main__":
    unittest.main()
