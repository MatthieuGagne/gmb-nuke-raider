#!/usr/bin/env python3
"""Unit tests for dialog_editor.py pure-logic helpers.

Run: PYTHONPATH=. python3 -m pytest tests/test_dialog_editor.py -v
"""
import sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import dialog_editor as ed


class TestUnassignedNpcs(unittest.TestCase):
    """unassigned_npcs(npcs, hub_npc_ids) → list of NPC dicts not in hub."""

    def _npcs(self):
        return [
            {"id": 0, "name": "MECHANIC", "nodes": []},
            {"id": 1, "name": "TRADER",   "nodes": []},
            {"id": 2, "name": "SCOUT",    "nodes": []},
        ]

    def test_all_assigned_returns_empty(self):
        npcs = self._npcs()
        result = ed.unassigned_npcs(npcs, [0, 1, 2])
        self.assertEqual(result, [])

    def test_none_assigned_returns_all(self):
        npcs = self._npcs()
        result = ed.unassigned_npcs(npcs, [])
        self.assertEqual([n["id"] for n in result], [0, 1, 2])

    def test_partial_assignment(self):
        npcs = self._npcs()
        result = ed.unassigned_npcs(npcs, [1])
        self.assertEqual([n["id"] for n in result], [0, 2])

    def test_returns_npc_dicts_not_ids(self):
        npcs = self._npcs()
        result = ed.unassigned_npcs(npcs, [0, 2])
        self.assertEqual(len(result), 1)
        self.assertIn("name", result[0])
        self.assertEqual(result[0]["name"], "TRADER")


class TestNextHubId(unittest.TestCase):
    """next_hub_id(hubs) → int, one above the current max id (or 0 if empty)."""

    def test_empty_hubs_returns_zero(self):
        self.assertEqual(ed.next_hub_id([]), 0)

    def test_single_hub(self):
        self.assertEqual(ed.next_hub_id([{"id": 0}]), 1)

    def test_gap_in_ids(self):
        self.assertEqual(ed.next_hub_id([{"id": 0}, {"id": 3}]), 4)


class TestHubCrud(unittest.TestCase):
    """hub_add_npc / hub_remove_npc / hub_rename / hub_delete operate on
    the hubs list in-place and return a (modified_list, status_str) tuple."""

    def _hubs(self):
        return [
            {"id": 0, "name": "RUST TOWN",  "npc_ids": [0, 1]},
            {"id": 1, "name": "JANKY CITY", "npc_ids": []},
        ]

    # hub_add_npc ─────────────────────────────────────────────────────────
    def test_add_npc_appends_to_roster(self):
        hubs = self._hubs()
        hubs, msg = ed.hub_add_npc(hubs, hub_idx=1, npc_id=2)
        self.assertIn(2, hubs[1]["npc_ids"])
        self.assertIn("added", msg.lower())

    def test_add_npc_already_present_returns_error(self):
        hubs = self._hubs()
        hubs, msg = ed.hub_add_npc(hubs, hub_idx=0, npc_id=1)
        self.assertIn("already", msg.lower())
        self.assertEqual(hubs[0]["npc_ids"].count(1), 1)  # no duplicate

    # hub_remove_npc ──────────────────────────────────────────────────────
    def test_remove_npc_by_roster_index(self):
        hubs = self._hubs()
        hubs, msg = ed.hub_remove_npc(hubs, hub_idx=0, roster_idx=0)
        self.assertNotIn(0, hubs[0]["npc_ids"])
        self.assertIn("removed", msg.lower())

    def test_remove_npc_out_of_range_returns_error(self):
        hubs = self._hubs()
        hubs, msg = ed.hub_remove_npc(hubs, hub_idx=1, roster_idx=0)
        self.assertIn("empty", msg.lower())

    # hub_rename ──────────────────────────────────────────────────────────
    def test_rename_hub(self):
        hubs = self._hubs()
        hubs, msg = ed.hub_rename(hubs, hub_idx=0, new_name="steel city")
        self.assertEqual(hubs[0]["name"], "STEEL CITY")
        self.assertIn("renamed", msg.lower())

    def test_rename_hub_truncates_to_15(self):
        hubs = self._hubs()
        hubs, msg = ed.hub_rename(hubs, hub_idx=0, new_name="A" * 20)
        self.assertEqual(len(hubs[0]["name"]), 15)

    # hub_delete ──────────────────────────────────────────────────────────
    def test_delete_hub_removes_from_list(self):
        hubs = self._hubs()
        hubs, msg = ed.hub_delete(hubs, hub_idx=0)
        self.assertEqual(len(hubs), 1)
        self.assertEqual(hubs[0]["name"], "JANKY CITY")
        self.assertIn("deleted", msg.lower())

    def test_delete_last_hub_leaves_empty_list(self):
        hubs = [{"id": 0, "name": "SOLO", "npc_ids": []}]
        hubs, msg = ed.hub_delete(hubs, hub_idx=0)
        self.assertEqual(hubs, [])


if __name__ == "__main__":
    unittest.main()
