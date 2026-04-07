#!/usr/bin/env python3
"""Unit tests for balancer.py pure-logic helpers.

Run: PYTHONPATH=. python3 -m unittest tests.test_balancer -v
"""
import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import balancer

SAMPLE_CONFIG = """\
#define GEAR1_MAX_SPEED        2u
#define GEAR1_ACCEL            2u
#define PLAYER_ARMOR     5   /* reduces damage */
#define PLAYER_MAX_HP              100u  /* max HP pool */
#define ENEMY_BULLET_DAMAGE        10u  /* HP damage dealt by an enemy bullet projectile */
"""

class TestParseConfig(unittest.TestCase):
    def test_reads_u_suffix_value(self):
        vals = balancer.parse_config(SAMPLE_CONFIG)
        self.assertEqual(vals['GEAR1_MAX_SPEED'], 2)

    def test_reads_no_suffix_value(self):
        vals = balancer.parse_config(SAMPLE_CONFIG)
        self.assertEqual(vals['PLAYER_ARMOR'], 5)

    def test_reads_value_with_trailing_comment(self):
        vals = balancer.parse_config(SAMPLE_CONFIG)
        self.assertEqual(vals['PLAYER_MAX_HP'], 100)

    def test_reads_enemy_bullet_damage(self):
        vals = balancer.parse_config(SAMPLE_CONFIG)
        self.assertEqual(vals['ENEMY_BULLET_DAMAGE'], 10)


class TestApplyChanges(unittest.TestCase):
    def test_updates_u_suffix_value(self):
        result = balancer.apply_changes(SAMPLE_CONFIG, {'GEAR1_MAX_SPEED': 5})
        self.assertIn('#define GEAR1_MAX_SPEED        5u', result)

    def test_preserves_no_suffix(self):
        result = balancer.apply_changes(SAMPLE_CONFIG, {'PLAYER_ARMOR': 3})
        self.assertIn('#define PLAYER_ARMOR     3   /* reduces damage */', result)

    def test_preserves_trailing_comment(self):
        result = balancer.apply_changes(SAMPLE_CONFIG, {'PLAYER_MAX_HP': 80})
        self.assertIn('#define PLAYER_MAX_HP              80u  /* max HP pool */', result)

    def test_unchanged_lines_preserved(self):
        result = balancer.apply_changes(SAMPLE_CONFIG, {'GEAR1_MAX_SPEED': 5})
        self.assertIn('#define GEAR1_ACCEL            2u', result)

    def test_no_changes_returns_identical(self):
        result = balancer.apply_changes(SAMPLE_CONFIG, {})
        self.assertEqual(result, SAMPLE_CONFIG)


if __name__ == '__main__':
    unittest.main()
