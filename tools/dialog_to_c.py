#!/usr/bin/env python3
"""JSON → C generator for NPC dialog data.

Usage:
    python3 tools/dialog_to_c.py assets/dialog/npcs.json src/dialog_data.c

Reads assets/dialog/npcs.json and writes src/dialog_data.c with:
  - #pragma bank 255
  - BANKREF(npc_dialogs)
  - static const strings named n{npc_id}_{node_idx} and n{npc_id}_c{node}_{choice}
  - static const DialogNode {slug}_nodes[] for each NPC
  - const NpcDialog npc_dialogs[] table
"""
import json
import os
import re
import sys

MAX_TEXT_LEN  = 63
MAX_NAME_LEN  = 15
MAX_CHOICES   = 3
MAX_NPCS      = 6
DIALOG_END    = "DIALOG_END"

CONFIG_H_PATH = os.path.join(os.path.dirname(__file__), '..', 'src', 'config.h')


def parse_max_npcs(config_text):
    """Return the integer value of MAX_NPCS from config.h text."""
    m = re.search(r'#define\s+MAX_NPCS\s+(\d+)', config_text)
    if not m:
        raise ValueError("MAX_NPCS not found in config.h text")
    return int(m.group(1))


def patch_config_define(config_text, name, new_value):
    """Replace '#define NAME <old>' with '#define NAME <new_value>' in config text.
    Preserves alignment (whitespace between name and value is kept, value replaced).
    Raises ValueError if the define is not found.
    """
    pattern = rf'(#define\s+{re.escape(name)}\s+)\S+'
    new_text, n = re.subn(pattern, rf'\g<1>{new_value}', config_text)
    if n == 0:
        raise ValueError(f"{name} not found in config text")
    return new_text


def validate(data, max_npcs=None):
    """Validate NPC dialog data.

    max_npcs: if provided, len(npcs) must equal exactly this value (enforced by
    generator when config.h is available). If None, only an upper-bound check
    against the module-level MAX_NPCS constant is applied (used by unit tests
    with partial fixtures).
    """
    npcs = data["npcs"]
    if max_npcs is not None:
        if len(npcs) != max_npcs:
            raise ValueError(
                f"NPC count mismatch: got {len(npcs)}, expected {max_npcs} "
                f"(MAX_NPCS={max_npcs} in config.h)")
    elif len(npcs) > MAX_NPCS:
        raise ValueError(f"Too many NPCs: {len(npcs)} > {MAX_NPCS} (MAX_NPCS={MAX_NPCS})")
    for npc in npcs:
        npc_id = npc["id"]
        name   = npc["name"]
        if len(name) > MAX_NAME_LEN:
            raise ValueError(f"NPC {npc_id} name '{name}' exceeds {MAX_NAME_LEN} chars")
        num_nodes = len(npc["nodes"])
        for node in npc["nodes"]:
            idx     = node["idx"]
            text    = node["text"]
            choices = node["choices"]
            nexts   = node["next"]
            if len(text) > MAX_TEXT_LEN:
                raise ValueError(
                    f"NPC {npc_id} node {idx} text length {len(text)} > {MAX_TEXT_LEN}")
            if len(choices) > MAX_CHOICES:
                raise ValueError(
                    f"NPC {npc_id} node {idx} has {len(choices)} choices > {MAX_CHOICES}")
            if choices:
                # Choice node: nexts must have one entry per choice
                if len(nexts) != len(choices):
                    raise ValueError(
                        f"NPC {npc_id} node {idx}: choices length {len(choices)} != "
                        f"next length {len(nexts)}")
            else:
                # Narration node: nexts must have exactly 1 entry
                if len(nexts) != 1:
                    raise ValueError(
                        f"NPC {npc_id} node {idx}: narration node must have exactly 1 next, "
                        f"got {len(nexts)}")
            for n in nexts:
                if n == "END":
                    continue
                if not isinstance(n, int) or n < 0 or n >= num_nodes:
                    raise ValueError(
                        f"NPC {npc_id} node {idx}: next ref {n!r} out of range "
                        f"(0..{num_nodes-1})")


def _next_val(n):
    return DIALOG_END if n == "END" else str(n)


def _pad3(val, width=11):
    """Right-pad a value to width for column alignment."""
    return val.ljust(width)


def generate_c(data, max_npcs=None):
    validate(data, max_npcs=max_npcs)
    lines = []
    lines.append("// GENERATED — do not edit by hand.")
    lines.append("// Source: assets/dialog/npcs.json")
    lines.append("// Regenerate: make dialog_data  OR  python3 tools/dialog_to_c.py assets/dialog/npcs.json src/dialog_data.c")
    lines.append("#pragma bank 255")
    lines.append('#include <stddef.h>')
    lines.append('#include "dialog_data.h"')
    lines.append('#include "banking.h"')
    lines.append("")

    for npc in data["npcs"]:
        npc_id = npc["id"]
        name   = npc["name"]
        slug   = name.lower()
        nodes  = npc["nodes"]

        lines.append(f"/* --- NPC {npc_id}: {name} --- */")

        # Text strings
        for node in nodes:
            idx  = node["idx"]
            text = node["text"]
            lines.append(f'static const char n{npc_id}_{idx}[] = "{text}";')

        # Choice label strings
        for node in nodes:
            idx     = node["idx"]
            choices = node["choices"]
            for ci, choice in enumerate(choices):
                lines.append(f'static const char n{npc_id}_c{idx}_{ci}[] = "{choice}";')

        # NPC name const
        lines.append(f'static const char npc_name_{slug}[] = "{name}";')
        lines.append("")

        # Node array
        lines.append(f"static const DialogNode {slug}_nodes[] = {{")
        for node in nodes:
            idx     = node["idx"]
            choices = node["choices"]
            nexts   = node["next"]

            # For narration nodes (no choices), format as the original:
            #   {NULL,   NULL,   NULL}
            if not choices:
                choices_str = "{NULL,   NULL,   NULL}"
            else:
                parts = []
                for ci in range(3):
                    if ci < len(choices):
                        parts.append(f"n{npc_id}_c{idx}_{ci}")
                    else:
                        parts.append("NULL")
                choices_str = "{" + ",  ".join(parts) + "}"

            # Build the 3-slot next array, DIALOG_END-padding unused slots
            # Narration nodes: next[0] = target (or DIALOG_END), rest = DIALOG_END
            # Choice nodes: next[i] = per-choice target, rest = DIALOG_END
            next_vals = [DIALOG_END, DIALOG_END, DIALOG_END]
            if not choices:
                # narration — nexts has exactly 1 element
                next_vals[0] = _next_val(nexts[0])
            else:
                for ci, n in enumerate(nexts):
                    next_vals[ci] = _next_val(n)

            next_str = "{" + ", ".join(next_vals) + "}"

            num_choices = len(choices)
            lines.append(
                f"    /* {idx} */ {{ n{npc_id}_{idx}, {num_choices}, "
                f"{choices_str}, {next_str} }},"
            )

        lines.append("};")
        lines.append("")

    # npc_dialogs table
    lines.append("/* --- NPC dialog table (indexed by npc_id) --- */")
    lines.append("BANKREF(npc_dialogs)")
    lines.append("const NpcDialog npc_dialogs[] = {")
    for npc in data["npcs"]:
        npc_id = npc["id"]
        name   = npc["name"]
        slug   = name.lower()
        num_nodes = len(npc["nodes"])
        lines.append(
            f"    {{ {slug}_nodes, {num_nodes}, npc_name_{slug} }}, /* NPC {npc_id}: {name} */"
        )
    lines.append("};")
    lines.append("")
    return "\n".join(lines)


def compute_max_hub_npcs(hubs_data):
    """Return the maximum NPC count across all hubs."""
    return max((len(h["npc_ids"]) for h in hubs_data["hubs"]), default=0)


def generate_hub_c(hubs_data, npcs_data):
    """Generate hub_data.c content from hubs.json + npcs.json.

    hub_data.c lives in bank 0 — no #pragma bank.
    NPC names are looked up from npcs_data by id (per R11).
    Raises ValueError if a hub references a nonexistent NPC id.
    """
    # Build id→name lookup from npcs
    npc_by_id = {npc["id"]: npc["name"] for npc in npcs_data["npcs"]}

    lines = []
    lines.append("// GENERATED — do not edit by hand.")
    lines.append("// Source: assets/dialog/hubs.json + assets/dialog/npcs.json")
    lines.append("// Regenerate: make dialog_data")
    lines.append("// bank 0: always mapped, no pragma needed")
    lines.append('#include <gb/gb.h>')
    lines.append('#include "hub_data.h"')
    lines.append("")

    hub_var_names = []
    for hub in hubs_data["hubs"]:
        hub_id   = hub["id"]
        hub_name = hub["name"]
        npc_ids  = hub["npc_ids"]
        var      = f"hub{hub_id}"
        hub_var_names.append(var)

        # Validate NPC ids
        for npc_id in npc_ids:
            if npc_id not in npc_by_id:
                raise ValueError(
                    f"Hub {hub_id} references NPC id {npc_id} which does not exist in npcs.json")

        lines.append(f"/* --- Hub {hub_id}: {hub_name} --- */")
        lines.append(f'static const char {var}_name[] = "{hub_name}";')
        for i, npc_id in enumerate(npc_ids):
            lines.append(f'static const char {var}_npc{i}_name[] = "{npc_by_id[npc_id]}";')
        lines.append("")

        # HubDef initializer
        num = len(npc_ids)
        npc_names_init = ", ".join(f"{var}_npc{i}_name" for i in range(num))
        npc_ids_init   = ", ".join(f"{npc_id}u" for npc_id in npc_ids)
        lines.append(f"static const HubDef {var} = {{")
        lines.append(f"    {var}_name,")
        lines.append(f"    {num}u,")
        lines.append(f"    {{ {npc_names_init} }},")
        lines.append(f"    {{ {npc_ids_init} }}")
        lines.append("};")
        lines.append("")

    # hub_table
    table_entries = ", ".join(f"&{v}" for v in hub_var_names)
    lines.append(f"const HubDef * const hub_table[] = {{ {table_entries} }};")
    lines.append(f"const uint8_t         hub_table_count = {len(hub_var_names)}u;")
    lines.append("")
    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate C dialog data from JSON sources.")
    parser.add_argument("npcs_json",  help="Path to assets/dialog/npcs.json")
    parser.add_argument("dialog_out", help="Output path for src/dialog_data.c")
    parser.add_argument("--hubs-json",  default=None,
                        help="Path to assets/dialog/hubs.json (enables hub_data.c generation)")
    parser.add_argument("--hub-out",    default=None,
                        help="Output path for src/hub_data.c")
    parser.add_argument("--config-h",   default=None,
                        help="Path to src/config.h (enables MAX_NPCS exact-count validation "
                             "and MAX_HUB_NPCS patching)")
    parser.add_argument("--max-npcs",   type=int, default=None,
                        help="Override MAX_NPCS (instead of reading from config.h)")
    args = parser.parse_args()

    with open(args.npcs_json) as f:
        npcs_data = json.load(f)

    # Determine effective max_npcs
    max_npcs = args.max_npcs
    config_text = None
    if max_npcs is None and args.config_h:
        with open(args.config_h) as f:
            config_text = f.read()
        max_npcs = parse_max_npcs(config_text)

    # Generate dialog_data.c
    out = generate_c(npcs_data, max_npcs=max_npcs)
    with open(args.dialog_out, "w") as f:
        f.write(out)
    print(f"Written: {args.dialog_out}")

    # Generate hub_data.c (if requested)
    if args.hubs_json and args.hub_out:
        with open(args.hubs_json) as f:
            hubs_data = json.load(f)
        hub_out = generate_hub_c(hubs_data, npcs_data)
        with open(args.hub_out, "w") as f:
            f.write(hub_out)
        print(f"Written: {args.hub_out}")

        # Patch MAX_HUB_NPCS in config.h if needed
        if args.config_h and config_text is not None:
            needed = compute_max_hub_npcs(hubs_data)
            m = re.search(r'#define\s+MAX_HUB_NPCS\s+(\d+)', config_text)
            current = int(m.group(1)) if m else 0
            if needed != current:
                new_text = patch_config_define(config_text, "MAX_HUB_NPCS", f"{needed}u")
                with open(args.config_h, "w") as f:
                    f.write(new_text)
                print(f"Patched MAX_HUB_NPCS={needed}u in {args.config_h}")


if __name__ == "__main__":
    main()
