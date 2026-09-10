"""Tests for tools/sync_agents.py."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import sync_agents

ROOT = os.path.join(os.path.dirname(__file__), '..')
SRC_DIR = os.path.join(ROOT, '.claude', 'agents')

AGENTS = ['emulicious-debug', 'gb-c-optimizer', 'gbdk-expert', 'map-expert',
          'music-expert', 'pyboy-debug', 'sprite-expert']


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _fixture(model, tools, color):
    return (
        "---\n"
        "name: demo\n"
        'description: "a: demo agent with a colon"\n'
        "model: %s\n"
        "tools: %s\n"
        "color: %s\n"
        "---\n"
        "> **Model tier:** %s\n"
        "\n"
        "Body text, verbatim.\n"
    ) % (model, tools, color, model)


class RenderTests(unittest.TestCase):
    def test_opus_maps_to_default_and_color_is_dropped(self):
        rendered = sync_agents.render(_fixture('opus', 'Read, Write', 'cyan'))
        self.assertIn('model: "@default"', rendered)
        self.assertNotIn('color:', rendered)

    def test_sonnet_maps_to_smol(self):
        rendered = sync_agents.render(_fixture('sonnet', 'Read', 'orange'))
        self.assertIn('model: "@smol"', rendered)

    def test_tool_translation_and_drop(self):
        rendered = sync_agents.render(_fixture(
            'opus',
            'Read, Write, Edit, Grep, Glob, Bash, PowerShell, WebFetch, '
            'Skill, TodoWrite',
            'cyan'))
        self.assertIn('tools: read, write, edit, grep, glob, bash', rendered)
        # Scoped to the frontmatter block: the appended omp adjustments
        # legitimately name the Skill and PowerShell tools in order to tell the
        # omp subagent what to do instead of using them.
        frontmatter = rendered.split('---')[1]
        for dropped in ('PowerShell', 'WebFetch', 'Skill', 'TodoWrite'):
            self.assertNotIn(dropped, frontmatter)

    def test_description_and_body_are_verbatim(self):
        rendered = sync_agents.render(_fixture('sonnet', 'Read, WebSearch', 'x'))
        self.assertIn('description: "a: demo agent with a colon"', rendered)
        self.assertIn('> **Model tier:** sonnet', rendered)
        self.assertIn('Body text, verbatim.', rendered)

    def test_body_gains_the_omp_adjustment_block_exactly_once(self):
        rendered = sync_agents.render(_fixture('opus', 'Read, Skill', 'cyan'))
        self.assertEqual(rendered.count(sync_agents.OMP_ADJUSTMENT_HEADING), 1)
        self.assertTrue(rendered.endswith(sync_agents.OMP_ADJUSTMENTS))
        # It must actually re-map the three Claude-Code-only assumptions.
        self.assertIn('.claude/skills/<name>/SKILL.md', rendered)
        self.assertIn('pwsh', rendered)
        self.assertIn("Ignore the body's `tools:` frontmatter line", rendered)

    def test_every_canonical_agent_mirror_carries_the_adjustments(self):
        for name in AGENTS:
            rendered = sync_agents.render(
                _read(os.path.join(SRC_DIR, '%s.md' % name)))
            self.assertEqual(
                rendered.count(sync_agents.OMP_ADJUSTMENT_HEADING), 1, name)

    def test_websearch_maps_to_web_search(self):
        rendered = sync_agents.render(_fixture('sonnet', 'Read, WebSearch', 'x'))
        self.assertIn('web_search', rendered)
        self.assertNotIn('WebSearch', rendered)


class CanonicalTranslationTests(unittest.TestCase):
    """The seven real agents translate to exactly the frontmatter omp needs (AC2)."""

    EXPECTED_MODEL = {
        'emulicious-debug': '@default',
        'gb-c-optimizer': '@smol',
        'gbdk-expert': '@default',
        'map-expert': '@default',
        'music-expert': '@default',
        'pyboy-debug': '@default',
        'sprite-expert': '@smol',
    }
    EXPECTED_TOOLS = {
        'emulicious-debug': 'read, edit, grep, glob, bash',
        'gb-c-optimizer': 'read, grep, glob, edit, bash',
        'gbdk-expert': 'read, write, edit, grep, glob, bash',
        'map-expert': 'read, write, edit, grep, glob, bash',
        'music-expert': 'read, write, edit, grep, glob, bash',
        'pyboy-debug': 'read, write, bash, grep, glob',
        'sprite-expert': 'read, write, edit, grep, glob, bash',
    }

    def _rendered(self, name):
        return sync_agents.render(_read(os.path.join(SRC_DIR, '%s.md' % name)))

    def test_every_agent_has_required_frontmatter(self):
        for name in AGENTS:
            rendered = self._rendered(name)
            self.assertIn('name: %s' % name, rendered, name)
            self.assertRegex(rendered, r'(?m)^description: ', name)
            self.assertRegex(rendered, r'(?m)^model: ', name)
            self.assertRegex(rendered, r'(?m)^tools: ', name)

    def test_every_agent_model_is_translated(self):
        for name, model in self.EXPECTED_MODEL.items():
            self.assertIn('model: "%s"' % model, self._rendered(name), name)

    def test_every_agent_tools_are_translated(self):
        for name, tools in self.EXPECTED_TOOLS.items():
            self.assertIn('tools: %s' % tools, self._rendered(name), name)

    def test_no_agent_keeps_color_or_claude_only_tools(self):
        # Scoped to the frontmatter block: the verbatim body legitimately names
        # Skill/PowerShell, so a body-wide scan would fail on correct output.
        for name in AGENTS:
            frontmatter = self._rendered(name).split("---")[1]
            self.assertNotIn('color:', frontmatter, name)
            for banned in ('PowerShell', 'WebFetch', 'Skill', 'TodoWrite'):
                self.assertNotIn(banned, frontmatter, name)


class MirrorTests(unittest.TestCase):
    def test_mirror_creates_updates_and_removes(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, '.claude', 'agents')
            dst = os.path.join(d, '.omp', 'agents')
            os.makedirs(src)
            a = os.path.join(src, 'a.md')
            with open(a, 'w', encoding='utf-8') as fh:
                fh.write("---\nname: a\nmodel: sonnet\ntools: Read\n---\nbody a\n")
            b = os.path.join(src, 'b.md')
            with open(b, 'w', encoding='utf-8') as fh:
                fh.write("---\nname: b\nmodel: opus\ntools: Read, Write\n---\nbody b\n")
            self.assertEqual(sorted(sync_agents.sync(d)), ['a.md', 'b.md'])
            self.assertEqual(
                _read(os.path.join(dst, 'a.md')),
                '---\nname: a\nmodel: "@smol"\ntools: read\n---\nbody a\n\n'
                + sync_agents.OMP_ADJUSTMENTS)
            os.remove(a)  # canonical deleted -> mirror removed
            sync_agents.sync(d)
            self.assertFalse(os.path.isfile(os.path.join(dst, 'a.md')))
            self.assertTrue(os.path.isfile(os.path.join(dst, 'b.md')))

    def test_mirror_ignores_references_directory(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, '.claude', 'agents')
            refs = os.path.join(src, 'references')
            os.makedirs(refs)
            with open(os.path.join(src, 'x.md'), 'w', encoding='utf-8') as fh:
                fh.write("---\nname: x\nmodel: sonnet\ntools: Read\n---\nbody\n")
            with open(os.path.join(refs, 'ref.md'), 'w', encoding='utf-8') as fh:
                fh.write("not an agent\n")
            sync_agents.sync(d)
            self.assertEqual(sorted(os.listdir(os.path.join(d, '.omp', 'agents'))), ['x.md'])

    def test_mirror_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, '.claude', 'agents')
            os.makedirs(src)
            with open(os.path.join(src, 'x.md'), 'w', encoding='utf-8') as fh:
                fh.write("---\nname: x\nmodel: opus\ntools: Read\n---\nbody\n")
            sync_agents.sync(d)
            dst_file = os.path.join(d, '.omp', 'agents', 'x.md')
            first = _read(dst_file)
            sync_agents.sync(d)
            self.assertEqual(_read(dst_file), first)  # byte-identical after 2nd run

    def test_mirror_rewrites_crlf_to_lf(self):
        # A Windows checkout can put CRLF bytes on disk; the sync must rewrite
        # them to LF rather than skip (the read-back must not translate \r\n).
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, '.claude', 'agents')
            os.makedirs(src)
            with open(os.path.join(src, 'x.md'), 'w', encoding='utf-8') as fh:
                fh.write("---\nname: x\nmodel: opus\ntools: Read\n---\nbody\n")
            sync_agents.sync(d)
            dst_file = os.path.join(d, '.omp', 'agents', 'x.md')
            with open(dst_file, 'w', encoding='utf-8', newline='') as fh:
                fh.write(_read(dst_file).replace('\n', '\r\n'))
            sync_agents.sync(d)
            with open(dst_file, 'rb') as fh:
                self.assertNotIn(b'\r\n', fh.read())


class ParityTests(unittest.TestCase):
    """AC1/AC3: on a synced tree the on-disk mirror matches what sync would write.

    Runs against the real repo tree, so it fails exactly when .omp/agents/
    drifts from .claude/agents/ — the state the pre-commit hook's sync step
    exists to prevent.
    """

    def test_omp_mirror_matches_canonical_sources(self):
        expected = {}
        for name in sorted(os.listdir(SRC_DIR)):
            if name.endswith('.md'):
                expected[name] = sync_agents.render(_read(os.path.join(SRC_DIR, name)))
        self.assertTrue(expected, 'no canonical agents under .claude/agents/')
        actual = {}
        dst = os.path.join(ROOT, '.omp', 'agents')
        if os.path.isdir(dst):
            for name in sorted(os.listdir(dst)):
                if name.endswith('.md'):
                    actual[name] = _read(os.path.join(dst, name))
        self.assertEqual(actual, expected)


class HookWiringTests(unittest.TestCase):
    """R3: the pre-commit hook syncs and stages before the test suite."""

    def test_hook_runs_sync_before_the_discovery_command(self):
        hook = _read(os.path.join(ROOT, '.githooks', 'pre-commit'))
        sync_idx = hook.index('tools/sync_agents.py')
        discovery = "-m unittest discover -s tests -p 'test_*.py'"
        self.assertLess(sync_idx, hook.index(discovery))

    def test_hook_stages_the_omp_mirror(self):
        self.assertIn('git add .omp/agents/',
                      _read(os.path.join(ROOT, '.githooks', 'pre-commit')))


if __name__ == '__main__':
    unittest.main()
