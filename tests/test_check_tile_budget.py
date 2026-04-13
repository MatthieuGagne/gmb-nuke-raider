"""Tests for tools/check_tile_budget.py"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import check_tile_budget


def make_src(d, files):
    """Write a dict of filename→content into d/src/."""
    src = os.path.join(d, 'src')
    os.makedirs(src, exist_ok=True)
    for name, content in files.items():
        with open(os.path.join(src, name), 'w') as f:
            f.write(content)


class TestParsecounts(unittest.TestCase):
    def test_reads_count_from_single_file(self):
        with tempfile.TemporaryDirectory() as d:
            make_src(d, {'foo.c': 'const uint8_t player_tile_data_count = 16u;\n'})
            counts = check_tile_budget._parse_counts(os.path.join(d, 'src'))
            self.assertEqual(counts['player_tile_data_count'], 16)

    def test_reads_counts_across_multiple_files(self):
        with tempfile.TemporaryDirectory() as d:
            make_src(d, {
                'a.c': 'const uint8_t player_tile_data_count = 16u;\n',
                'b.c': 'const uint8_t bullet_tile_data_count = 1u;\n',
            })
            counts = check_tile_budget._parse_counts(os.path.join(d, 'src'))
            self.assertEqual(counts['player_tile_data_count'], 16)
            self.assertEqual(counts['bullet_tile_data_count'], 1)

    def test_missing_symbol_not_in_dict(self):
        with tempfile.TemporaryDirectory() as d:
            make_src(d, {'a.c': '/* no counts here */\n'})
            counts = check_tile_budget._parse_counts(os.path.join(d, 'src'))
            self.assertNotIn('player_tile_data_count', counts)


class TestCheckState(unittest.TestCase):
    def test_pass_under_budget(self):
        counts = {
            'player_tile_data_count': 16,
            'bullet_tile_data_count':  1,
            'turret_tile_data_count':  2,
            'track_tile_data_count':   9,
        }
        r = check_tile_budget._check_state(
            counts, 'playing', check_tile_budget.STATE_MANIFESTS['playing'])
        self.assertEqual(r['status'], 'PASS')
        self.assertEqual(r['sprite_used'], 19)
        self.assertEqual(r['bg_used'], 9)

    def test_fail_sprite_exceeds_budget(self):
        # 65 sprite tiles > SPRITE_BUDGET (64)
        counts = {
            'player_tile_data_count': 65,
            'bullet_tile_data_count':  0,
            'turret_tile_data_count':  0,
            'track_tile_data_count':   0,
        }
        r = check_tile_budget._check_state(
            counts, 'playing', check_tile_budget.STATE_MANIFESTS['playing'])
        self.assertEqual(r['status'], 'FAIL')

    def test_fail_bg_exceeds_budget(self):
        # 113 BG tiles > BG_BUDGET (112)
        counts = {
            'dialog_arrow_tile_data_count':   0,
            'npc_drifter_portrait_count':    57,
            'npc_mechanic_portrait_count':   56,
            'npc_trader_portrait_count':      0,
            'dialog_border_tiles_count':      0,
        }
        r = check_tile_budget._check_state(
            counts, 'hub', check_tile_budget.STATE_MANIFESTS['hub'])
        self.assertEqual(r['status'], 'FAIL')

    def test_missing_symbol_treated_as_zero(self):
        # no symbols present — all default to 0 → PASS
        r = check_tile_budget._check_state(
            {}, 'playing', check_tile_budget.STATE_MANIFESTS['playing'])
        self.assertEqual(r['status'], 'PASS')
        self.assertEqual(r['sprite_used'], 0)

    def test_exact_budget_boundary_passes(self):
        # sprite_used == SPRITE_BUDGET → PASS (not strictly greater than)
        counts = {
            'player_tile_data_count': 64,
            'bullet_tile_data_count':  0,
            'turret_tile_data_count':  0,
            'track_tile_data_count':   0,
        }
        r = check_tile_budget._check_state(
            counts, 'playing', check_tile_budget.STATE_MANIFESTS['playing'])
        self.assertEqual(r['status'], 'PASS')


class TestCheckIntegration(unittest.TestCase):
    def test_all_states_pass_with_real_counts(self):
        """Uses actual src/ directory — verifies current codebase is under budget."""
        repo_root = os.path.join(os.path.dirname(__file__), '..')
        results = check_tile_budget.check(repo_root)
        for r in results:
            self.assertEqual(r['status'], 'PASS',
                msg=f"State '{r['state']}' exceeds budget: "
                    f"sprite={r['sprite_used']}/{check_tile_budget.SPRITE_BUDGET}, "
                    f"bg={r['bg_used']}/{check_tile_budget.BG_BUDGET}")

    def test_fail_when_oversized_asset_injected(self):
        """Acceptance criterion: budget check fails when a state exceeds its region."""
        with tempfile.TemporaryDirectory() as d:
            # Copy the real src/ structure but override player to 65 tiles
            make_src(d, {
                'fake_player.c': 'const uint8_t player_tile_data_count = 65u;\n',
                'fake_bullet.c': 'const uint8_t bullet_tile_data_count = 1u;\n',
                'fake_turret.c': 'const uint8_t turret_tile_data_count = 2u;\n',
                'fake_track.c':  'const uint8_t track_tile_data_count = 9u;\n',
            })
            results = check_tile_budget.check(d)
            playing = next(r for r in results if r['state'] == 'playing')
            self.assertEqual(playing['status'], 'FAIL')
