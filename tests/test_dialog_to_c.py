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


class TestValidateWithExplicitMax(unittest.TestCase):

    # 28 — validate with explicit max_npcs raises on mismatch (too few)
    def test_validate_too_few_npcs_raises(self):
        data = _one_npc()  # 1 NPC
        with self.assertRaises(ValueError) as cm:
            conv.validate(data, max_npcs=3)
        self.assertIn("1", str(cm.exception))
        self.assertIn("3", str(cm.exception))

    # 29 — validate with explicit max_npcs raises on mismatch (too many)
    def test_validate_too_many_npcs_explicit_raises(self):
        data = {"npcs": [{"id": i, "name": f"NPC{i}", "nodes": [
            {"idx": 0, "text": "Hi", "choices": [], "next": ["END"]}
        ]} for i in range(4)]}
        with self.assertRaises(ValueError) as cm:
            conv.validate(data, max_npcs=3)
        self.assertIn("4", str(cm.exception))
        self.assertIn("3", str(cm.exception))

    # 30 — validate with exact match passes
    def test_validate_exact_match_passes(self):
        data = {"npcs": [{"id": i, "name": f"NPC{i}", "nodes": [
            {"idx": 0, "text": "Hi", "choices": [], "next": ["END"]}
        ]} for i in range(3)]}
        conv.validate(data, max_npcs=3)  # must not raise


# ── Hub data generation tests ─────────────────────────────────────────────────

def _npc_stub(npc_id, name):
    return {"id": npc_id, "name": name,
            "nodes": [{"idx": 0, "text": "...", "choices": [], "next": ["END"]}]}


class TestGenerateHubC(unittest.TestCase):

    def _hub_data(self):
        return {
            "hubs": [
                {"id": 0, "name": "RUST TOWN", "npc_ids": [0, 1, 2]}
            ]
        }

    def _npcs_data(self):
        return {"npcs": [
            _npc_stub(0, "MECHANIC"),
            _npc_stub(1, "TRADER"),
            _npc_stub(2, "DRIFTER"),
        ]}

    def _emit(self, hubs=None, npcs=None):
        return conv.generate_hub_c(hubs or self._hub_data(), npcs or self._npcs_data())

    # 31 — GENERATED header present
    def test_hub_generated_header(self):
        out = self._emit()
        self.assertIn("// GENERATED", out)

    # 32 — no #pragma bank (bank 0)
    def test_hub_no_pragma_bank(self):
        out = self._emit()
        self.assertNotIn("#pragma bank", out)

    # 33 — hub name present
    def test_hub_name_emitted(self):
        out = self._emit()
        self.assertIn('"RUST TOWN"', out)

    # 34 — NPC names derived from npcs.json
    def test_hub_npc_names_from_npcs(self):
        out = self._emit()
        self.assertIn('"MECHANIC"', out)
        self.assertIn('"TRADER"', out)
        self.assertIn('"DRIFTER"', out)

    # 35 — npc_dialog_ids contain the npc_ids from hubs.json
    def test_hub_npc_dialog_ids(self):
        out = self._emit()
        # IDs 0, 1, 2 emitted as uint8_t literals
        self.assertIn("0u", out)
        self.assertIn("1u", out)
        self.assertIn("2u", out)

    # 36 — hub_table array emitted
    def test_hub_table_emitted(self):
        out = self._emit()
        self.assertIn("hub_table[]", out)
        self.assertIn("hub_table_count", out)

    # 37 — hub_table_count matches number of hubs
    def test_hub_table_count_correct(self):
        out = self._emit()
        self.assertIn("hub_table_count = 1u", out)

    # 38 — invalid NPC id raises
    def test_hub_invalid_npc_id_raises(self):
        hubs = {"hubs": [{"id": 0, "name": "HUB", "npc_ids": [99]}]}
        with self.assertRaises(ValueError) as cm:
            conv.generate_hub_c(hubs, self._npcs_data())
        self.assertIn("99", str(cm.exception))

    # 39 — compute_max_hub_npcs returns max roster length
    def test_compute_max_hub_npcs(self):
        hubs = {"hubs": [
            {"id": 0, "name": "A", "npc_ids": [0, 1]},
            {"id": 1, "name": "B", "npc_ids": [0, 1, 2]},
        ]}
        self.assertEqual(conv.compute_max_hub_npcs(hubs), 3)

    # 40 — two hubs: both emitted, table has 2 entries
    def test_two_hubs_emitted(self):
        npcs = {"npcs": [_npc_stub(i, f"NPC{i}") for i in range(3)]}
        hubs = {"hubs": [
            {"id": 0, "name": "RUST TOWN", "npc_ids": [0]},
            {"id": 1, "name": "DUST CITY", "npc_ids": [1, 2]},
        ]}
        out = conv.generate_hub_c(hubs, npcs)
        self.assertIn('"RUST TOWN"', out)
        self.assertIn('"DUST CITY"', out)
        self.assertIn("hub_table_count = 2u", out)


# ── config.h helpers ─────────────────────────────────────────────────────────

class TestConfigHelpers(unittest.TestCase):

    _SAMPLE_CONFIG = (
        "#define MAX_NPCS     6\n"
        "#define OTHER        3\n"
        "#define MAX_HUB_NPCS 3u\n"
    )

    # 23 — parse_max_npcs extracts integer value
    def test_parse_max_npcs_returns_value(self):
        self.assertEqual(conv.parse_max_npcs(self._SAMPLE_CONFIG), 6)

    # 24 — parse_max_npcs raises if define is missing
    def test_parse_max_npcs_missing_raises(self):
        with self.assertRaises(ValueError) as cm:
            conv.parse_max_npcs("#define OTHER 3\n")
        self.assertIn("MAX_NPCS", str(cm.exception))

    # 25 — patch_config_define replaces integer value
    def test_patch_config_define_replaces_value(self):
        result = conv.patch_config_define(self._SAMPLE_CONFIG, "MAX_NPCS", 7)
        self.assertIn("#define MAX_NPCS     7", result)
        self.assertNotIn("#define MAX_NPCS     6", result)

    # 26 — patch_config_define leaves other defines untouched
    def test_patch_config_define_leaves_others(self):
        result = conv.patch_config_define(self._SAMPLE_CONFIG, "MAX_NPCS", 7)
        self.assertIn("#define OTHER        3", result)
        self.assertIn("#define MAX_HUB_NPCS 3u", result)

    # 27 — patch_config_define raises if define is missing
    def test_patch_config_define_missing_raises(self):
        with self.assertRaises(ValueError) as cm:
            conv.patch_config_define(self._SAMPLE_CONFIG, "NONEXISTENT", 9)
        self.assertIn("NONEXISTENT", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
