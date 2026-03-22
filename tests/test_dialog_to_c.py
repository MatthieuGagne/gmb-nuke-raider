#!/usr/bin/env python3
"""Unit tests for tools/dialog_to_c.py

Run: PYTHONPATH=. python3 -m unittest tests.test_dialog_to_c -v
"""
import sys, os, json, textwrap, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import dialog_to_c as conv


# ── Minimal valid JSON fixtures ──────────────────────────────────────────────

def _one_npc(name="NPC0", nodes=None):
    if nodes is None:
        nodes = [{"idx": 0, "text": "Hello.", "choices": [], "next": ["END"]}]
    return {"npcs": [{"id": 0, "name": name, "nodes": nodes}]}


def _two_node_npc():
    return {"npcs": [{"id": 0, "name": "MECHANIC", "nodes": [
        {"idx": 0, "text": "Hi there.", "choices": ["Yes", "No"], "next": [1, "END"]},
        {"idx": 1, "text": "Goodbye.",  "choices": [],            "next": ["END"]},
    ]}]}


# ── Validation tests ─────────────────────────────────────────────────────────

class TestValidation(unittest.TestCase):

    # 1 — text length limit
    def test_text_over_63_chars_raises(self):
        data = _one_npc(nodes=[{"idx":0,"text":"A"*64,"choices":[],"next":["END"]}])
        with self.assertRaises(ValueError) as cm:
            conv.validate(data)
        self.assertIn("63", str(cm.exception))

    # 2 — text at exactly 63 chars is OK
    def test_text_at_63_chars_ok(self):
        data = _one_npc(nodes=[{"idx":0,"text":"A"*63,"choices":[],"next":["END"]}])
        conv.validate(data)  # must not raise

    # 3 — NPC name too long
    def test_npc_name_over_15_chars_raises(self):
        data = _one_npc(name="A"*16)
        with self.assertRaises(ValueError) as cm:
            conv.validate(data)
        self.assertIn("15", str(cm.exception))

    # 4 — NPC name at 15 chars is OK
    def test_npc_name_at_15_chars_ok(self):
        data = _one_npc(name="A"*15)
        conv.validate(data)

    # 5 — too many choices per node
    def test_four_choices_raises(self):
        data = _one_npc(nodes=[{"idx":0,"text":"Hi","choices":["a","b","c","d"],"next":[1,2,3,4]}])
        with self.assertRaises(ValueError) as cm:
            conv.validate(data)
        self.assertIn("3", str(cm.exception))

    # 6 — 3 choices is OK
    def test_three_choices_ok(self):
        data = _one_npc(nodes=[{"idx":0,"text":"Hi","choices":["a","b","c"],"next":["END","END","END"]}])
        conv.validate(data)

    # 7 — too many NPCs
    def test_seven_npcs_raises(self):
        data = {"npcs": [{"id": i, "name": f"NPC{i}", "nodes": [
            {"idx":0,"text":"Hi","choices":[],"next":["END"]}
        ]} for i in range(7)]}
        with self.assertRaises(ValueError) as cm:
            conv.validate(data)
        self.assertIn("6", str(cm.exception))

    # 8 — exactly 6 NPCs is OK
    def test_six_npcs_ok(self):
        data = {"npcs": [{"id": i, "name": f"NPC{i}", "nodes": [
            {"idx":0,"text":"Hi","choices":[],"next":["END"]}
        ]} for i in range(6)]}
        conv.validate(data)

    # 9 — next ref out of range
    def test_next_ref_out_of_range_raises(self):
        data = _one_npc(nodes=[{"idx":0,"text":"Hi","choices":[],"next":[99]}])
        with self.assertRaises(ValueError) as cm:
            conv.validate(data)
        self.assertIn("99", str(cm.exception))

    # 10 — choices/next length mismatch
    def test_choices_next_mismatch_raises(self):
        data = _one_npc(nodes=[{"idx":0,"text":"Hi","choices":["A"],"next":[1,"END"]}])
        with self.assertRaises(ValueError):
            conv.validate(data)


# ── Emission tests ────────────────────────────────────────────────────────────

class TestEmission(unittest.TestCase):

    def _emit(self, data):
        return conv.generate_c(data)

    # 11 — GENERATED header present
    def test_generated_header_present(self):
        out = self._emit(_one_npc())
        self.assertIn("// GENERATED", out)

    # 12 — pragma bank 255
    def test_pragma_bank_255(self):
        out = self._emit(_one_npc())
        self.assertIn("#pragma bank 255", out)

    # 13 — BANKREF present
    def test_bankref_npc_dialogs(self):
        out = self._emit(_one_npc())
        self.assertIn("BANKREF(npc_dialogs)", out)

    # 14 — text variable naming: n{npc_id}_{node_idx}
    def test_text_var_naming(self):
        out = self._emit(_two_node_npc())
        self.assertIn('static const char n0_0[]', out)
        self.assertIn('static const char n0_1[]', out)

    # 15 — choice label naming: n{npc_id}_c{node}_{choice}
    def test_choice_var_naming(self):
        out = self._emit(_two_node_npc())
        self.assertIn('static const char n0_c0_0[]', out)  # choice 0 of node 0
        self.assertIn('static const char n0_c0_1[]', out)  # choice 1 of node 0

    # 16 — nodes array uses slug
    def test_nodes_array_name(self):
        out = self._emit(_two_node_npc())
        self.assertIn("mechanic_nodes[]", out)

    # 17 — NPC name const uses slug
    def test_npc_name_const(self):
        out = self._emit(_two_node_npc())
        self.assertIn('static const char npc_name_mechanic[]', out)
        self.assertIn('"MECHANIC"', out)

    # 18 — DIALOG_END (0xFF) emitted for "END" sentinel
    def test_end_sentinel_emitted(self):
        out = self._emit(_one_npc())
        self.assertIn("DIALOG_END", out)

    # 19 — narration node: next[0] is target, next[1..2] are DIALOG_END
    def test_narration_node_layout(self):
        out = self._emit(_one_npc())
        # node with choices=[] and next=["END"] should have NULL choice ptrs
        self.assertIn("{NULL,   NULL,   NULL}", out)
        self.assertIn("{DIALOG_END, DIALOG_END, DIALOG_END}", out)

    # 20 — choice node: correct num_choices and next array
    def test_choice_node_layout(self):
        out = self._emit(_two_node_npc())
        # node 0 has 2 choices → next = {1, DIALOG_END, DIALOG_END}
        self.assertIn("2,", out)   # num_choices = 2
        self.assertIn("{1,", out)

    # 21 — npc_dialogs table emitted with correct num_nodes
    def test_npc_dialogs_table(self):
        out = self._emit(_two_node_npc())
        self.assertIn("npc_dialogs[]", out)
        self.assertIn("mechanic_nodes, 2,", out)

    # 22 — deterministic output (call twice, same result)
    def test_deterministic_output(self):
        data = _two_node_npc()
        self.assertEqual(conv.generate_c(data), conv.generate_c(data))


if __name__ == "__main__":
    unittest.main()
