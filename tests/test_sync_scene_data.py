"""Tests for tools/sync_scene_data.py"""
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import sync_scene_data


CONFIG = (
    '#define MAX_SPRITES 32u\n'
    '#define MAX_PROJECTILES 8u\n'
    '#define MAX_ENEMIES 8u\n'
    '#define MAX_ENEMY_RACERS 2u\n'
    '#define MAX_PATROLS 1u\n'
)

HTML = (
    '<html><body><script>\n'
    '/* SCENE_DATA:BEGIN */\n'
    'const SCENE_DATA = {OLD};\n'
    '/* SCENE_DATA:END */\n'
    '</script></body></html>\n'
)


def make_repo(d, html=HTML, config=CONFIG):
    os.makedirs(os.path.join(d, 'src'), exist_ok=True)
    os.makedirs(os.path.join(d, 'docs'), exist_ok=True)
    with open(os.path.join(d, 'src', 'config.h'), 'w') as f:
        f.write(config)
    with open(os.path.join(d, 'docs', 'memory-explained.html'), 'w', newline='') as f:
        f.write(html)


def read_html(d):
    with open(os.path.join(d, 'docs', 'memory-explained.html'), 'r', newline='') as f:
        return f.read()


class TestSync(unittest.TestCase):
    def test_writes_current_model(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            self.assertEqual(sync_scene_data.sync(d), 0)
            out = read_html(d)
            self.assertNotIn('{OLD}', out)
            self.assertIn('"worst_scene": "Playing"', out)
            self.assertIn('"peak": 32', out)
            # markers preserved
            self.assertIn(sync_scene_data.BEGIN, out)
            self.assertIn(sync_scene_data.END, out)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            sync_scene_data.sync(d)
            first = read_html(d)
            self.assertEqual(sync_scene_data.sync(d), 0)
            self.assertEqual(read_html(d), first)

    def test_check_detects_drift_then_clean(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            self.assertEqual(sync_scene_data.sync(d, check=True), 1)  # {OLD} is stale
            sync_scene_data.sync(d)                                   # fix it
            self.assertEqual(sync_scene_data.sync(d, check=True), 0)  # now in sync

    def test_check_does_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d)
            before = read_html(d)
            sync_scene_data.sync(d, check=True)
            self.assertEqual(read_html(d), before)

    def test_missing_markers_errors(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, html='<html><script>const SCENE_DATA={};</script></html>')
            self.assertEqual(sync_scene_data.sync(d), 1)

    def test_preserves_crlf(self):
        with tempfile.TemporaryDirectory() as d:
            make_repo(d, html=HTML.replace('\n', '\r\n'))
            sync_scene_data.sync(d)
            with open(os.path.join(d, 'docs', 'memory-explained.html'), 'rb') as f:
                raw = f.read()
            self.assertIn(b'\r\n', raw)
            self.assertIsNone(re.search(rb'(?<!\r)\n', raw))  # no lone LF


if __name__ == '__main__':
    unittest.main()
