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
import sys

MAX_TEXT_LEN  = 63
MAX_NAME_LEN  = 15
MAX_CHOICES   = 3
MAX_NPCS      = 6
DIALOG_END    = "DIALOG_END"


def validate(data):
    npcs = data["npcs"]
    if len(npcs) > MAX_NPCS:
        raise ValueError(f"Too many NPCs: {len(npcs)} > {MAX_NPCS} (MAX_NPCS=6)")
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


def generate_c(data):
    validate(data)
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


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <npcs.json> <dialog_data.c>", file=sys.stderr)
        sys.exit(1)
    json_path, out_path = sys.argv[1], sys.argv[2]
    with open(json_path) as f:
        data = json.load(f)
    out = generate_c(data)
    with open(out_path, "w") as f:
        f.write(out)
    print(f"Written: {out_path}")


if __name__ == "__main__":
    main()
