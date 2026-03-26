#!/usr/bin/env python3
"""Curses TUI dialog node editor for Junk Runner NPC dialog trees.

Usage:
    python3 tools/dialog_editor.py [assets/dialog/npcs.json]

Layout:
    ┌─────────────────┬──────────────────────────────────────────┐
    │ NPC List        │ Node Tree                                │
    │ [0] MECHANIC  * │ [0] Roads. Parts. Sharp... (41/63)       │
    │ [1] TRADER      │     ┌────────────┐                       │
    │ ...             │     │Roads. Parts│  (12-char wrap preview)│
    │                 │     │. Sharp. Rac│                       │
    │                 │     │er. Grease. │                       │
    │                 │     │Caps.       │                       │
    │                 │     └────────────┘                       │
    │                 │     next → [1]                          │
    │                 │ [1] What's on your mind? (20/63)        │
    │                 │     choices: [The races] → 2            │
    │                 │              [Supplies]  → 3            │
    └─────────────────┴──────────────────────────────────────────┘
    [s]ave  [g]en  [e]dit  [a]dd  [d]el  [n]ext  [c]hoice  [r]ename  [q]uit

Keys:
    TAB     — switch pane focus (NPC list ↔ node tree)
    j / ↓   — move cursor down
    k / ↑   — move cursor up
    e       — edit current node text (or rename NPC when in NPC pane)
    a       — add node (at end) / add NPC (blocked at MAX_NPCS=6)
    d       — delete current node (with automatic ref renumbering)
    n       — set next pointer for current node (prompt for index or END)
    c       — add/remove choice slot on current node (clamped 0–3)
    r       — rename current NPC
    s       — save JSON (blocked if any node text ≥ 63 chars)
    g       — save JSON + run generator
    q       — quit (prompts if unsaved changes)
"""
import curses
import json
import os
import subprocess
import sys
import textwrap

MAX_TEXT_LEN = 63
MAX_CHOICES  = 3
WARN_LEN     = 54   # yellow warning threshold
LEFT_W       = 20   # NPC pane width
WRAP_W       = 12   # dialog box inner width (mirrors DIALOG_INNER_W)
WRAP_ROWS    = 5    # dialog box inner height (rows 2-6)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_JSON = os.path.join(SCRIPT_DIR, '..', 'assets', 'dialog', 'npcs.json')
GENERATOR    = os.path.join(SCRIPT_DIR, 'dialog_to_c.py')
OUT_C        = os.path.join(SCRIPT_DIR, '..', 'src', 'dialog_data.c')
CONFIG_H     = os.path.join(SCRIPT_DIR, '..', 'src', 'config.h')
HUBS_JSON    = os.path.join(SCRIPT_DIR, '..', 'assets', 'dialog', 'hubs.json')
HUB_OUT_C    = os.path.join(SCRIPT_DIR, '..', 'src', 'hub_data.c')


def read_max_npcs_from_config(config_path=CONFIG_H):
    """Read MAX_NPCS value from src/config.h at runtime."""
    try:
        with open(config_path) as f:
            text = f.read()
        sys.path.insert(0, os.path.dirname(__file__))
        import dialog_to_c as _conv
        return _conv.parse_max_npcs(text)
    except Exception:
        return 6  # safe fallback


# ── Data helpers ─────────────────────────────────────────────────────────────

def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(data, path):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')


def wrap_preview(text, width=WRAP_W, rows=WRAP_ROWS):
    """Return list of at most `rows` lines, each ≤ `width` chars.
    Mirrors render_wrapped in state_hub.c: character-level wrapping at word
    boundaries (falls back to hard wrap on long words).
    """
    lines = []
    words = text.split()
    current = ""
    for word in words:
        if not current:
            current = word[:width]
        elif len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            lines.append(current)
            current = word[:width]
        if len(lines) >= rows:
            break
    if current and len(lines) < rows:
        lines.append(current)
    return lines[:rows]


def renumber_refs(nodes, deleted_idx):
    """After deleting node at deleted_idx, update all next refs.
    - Refs == deleted_idx → "END"
    - Refs >  deleted_idx → decremented by 1
    """
    for node in nodes:
        new_nexts = []
        for n in node["next"]:
            if n == "END":
                new_nexts.append("END")
            elif n == deleted_idx:
                new_nexts.append("END")
            elif isinstance(n, int) and n > deleted_idx:
                new_nexts.append(n - 1)
            else:
                new_nexts.append(n)
        node["next"] = new_nexts


# ── Hub data helpers ──────────────────────────────────────────────────────────

def unassigned_npcs(npcs, hub_npc_ids):
    """Return list of NPC dicts whose id is NOT in hub_npc_ids."""
    assigned = set(hub_npc_ids)
    return [n for n in npcs if n["id"] not in assigned]


def next_hub_id(hubs):
    """Return the next available hub id (max existing + 1, or 0 if empty)."""
    if not hubs:
        return 0
    return max(h["id"] for h in hubs) + 1


def hub_add_npc(hubs, hub_idx, npc_id):
    """Add npc_id to hubs[hub_idx].npc_ids. Returns (hubs, status_str)."""
    hub = hubs[hub_idx]
    if npc_id in hub["npc_ids"]:
        return hubs, "NPC already in hub"
    hub["npc_ids"].append(npc_id)
    return hubs, f"Added NPC {npc_id} to {hub['name']}"


def hub_remove_npc(hubs, hub_idx, roster_idx):
    """Remove the NPC at roster_idx from hubs[hub_idx].npc_ids.
    Returns (hubs, status_str)."""
    hub = hubs[hub_idx]
    if not hub["npc_ids"]:
        return hubs, "Hub roster is empty"
    if roster_idx < 0 or roster_idx >= len(hub["npc_ids"]):
        return hubs, f"Roster index {roster_idx} out of range"
    npc_id = hub["npc_ids"].pop(roster_idx)
    return hubs, f"Removed NPC {npc_id} from {hub['name']}"


def hub_rename(hubs, hub_idx, new_name):
    """Rename hubs[hub_idx] to new_name (uppercased, max 15 chars).
    Returns (hubs, status_str)."""
    name = new_name.upper()[:15]
    old = hubs[hub_idx]["name"]
    hubs[hub_idx]["name"] = name
    return hubs, f"Renamed '{old}' → '{name}'"


def hub_delete(hubs, hub_idx):
    """Delete hubs[hub_idx]. Returns (new_hubs_list, status_str)."""
    name = hubs[hub_idx]["name"]
    hubs = [h for i, h in enumerate(hubs) if i != hub_idx]
    return hubs, f"Deleted hub '{name}'"


# ── Editor ───────────────────────────────────────────────────────────────────

class DialogEditor:
    def __init__(self, stdscr, json_path):
        self.scr      = stdscr
        self.path     = json_path
        self.data     = load_json(json_path)
        self.dirty    = False
        self.focus    = 'npc'   # 'npc' or 'node'
        self.npc_cur  = 0
        self.node_cur = 0
        self.status   = ""
        self.max_npcs = read_max_npcs_from_config()
        self.hubs_path = HUBS_JSON
        self.hubs_data = self._load_hubs()
        self.mode          = 'main_menu'  # 'main_menu' | 'hub_view' | 'npc_view'
        self.hub_cur       = 0
        self.hub_focus     = 'hubs'       # 'hubs' | 'roster' — active pane in hub view
        self.hub_roster_cur = 0           # cursor within selected hub's NPC roster
        self.picker_cur    = 0            # cursor in NPC picker overlay
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_YELLOW, -1)
        curses.init_pair(2, curses.COLOR_RED,    -1)
        curses.init_pair(3, curses.COLOR_GREEN,  -1)

    @property
    def npcs(self):
        return self.data["npcs"]

    @property
    def cur_npc(self):
        return self.npcs[self.npc_cur]

    @property
    def cur_nodes(self):
        return self.cur_npc["nodes"]

    def run(self):
        curses.curs_set(0)
        self.scr.keypad(True)
        while True:
            if self.mode == 'main_menu':
                self._draw_main_menu()
                key = self.scr.getch()
                if not self._handle_main_menu_key(key):
                    break
            elif self.mode == 'hub_view':
                self._draw_hub_view()
                key = self.scr.getch()
                if not self._handle_hub_key(key):
                    break
            else:  # 'npc_view'
                self.draw()
                key = self.scr.getch()
                if not self.handle_key(key):
                    break

    def draw(self):
        self.scr.erase()
        h, w = self.scr.getmaxyx()

        # Left pane: NPC list
        for i, npc in enumerate(self.npcs):
            marker = "*" if (i == self.npc_cur and self.dirty) else " "
            line   = f"[{npc['id']}] {npc['name'][:14]}{marker}"
            attr   = curses.A_REVERSE if (self.focus == 'npc' and i == self.npc_cur) else 0
            if i < h - 2:
                self.scr.addstr(i, 0, line[:LEFT_W - 1].ljust(LEFT_W - 1), attr)

        # Divider
        for row in range(h - 2):
            if row < h:
                self.scr.addstr(row, LEFT_W - 1, "│")

        # Right pane: node tree
        row = 0
        for ni, node in enumerate(self.cur_nodes):
            if row >= h - 2:
                break
            idx     = node["idx"]
            text    = node["text"]
            tlen    = len(text)
            choices = node["choices"]
            nexts   = node["next"]

            # Color for char count
            if tlen >= MAX_TEXT_LEN:
                cnt_attr = curses.color_pair(2) | curses.A_BOLD
            elif tlen >= WARN_LEN:
                cnt_attr = curses.color_pair(1)
            else:
                cnt_attr = 0

            node_attr = curses.A_REVERSE if (self.focus == 'node' and ni == self.node_cur) else 0
            summary   = f"[{idx}] {text[:30]}{'...' if len(text) > 30 else ''}"
            count_str = f" ({tlen}/{MAX_TEXT_LEN})"

            x = LEFT_W
            avail = w - LEFT_W - 1
            if row < h - 2:
                self.scr.addstr(row, x, summary[:avail], node_attr)
                cx = x + min(len(summary), avail)
                if cx < w - 1:
                    self.scr.addstr(row, cx, count_str[:w - cx - 1], cnt_attr)
            row += 1

            # Wrap preview (indented 4 spaces)
            preview_lines = wrap_preview(text)
            if row < h - 2:
                self.scr.addstr(row, x, "    ┌" + "─" * WRAP_W + "┐")
                row += 1
            for pl in preview_lines:
                if row >= h - 2:
                    break
                self.scr.addstr(row, x, f"    │{pl:<{WRAP_W}}│")
                row += 1
            if row < h - 2:
                self.scr.addstr(row, x, "    └" + "─" * WRAP_W + "┘")
                row += 1

            # next / choices
            if not choices:
                nv = nexts[0] if nexts else "END"
                if row < h - 2:
                    self.scr.addstr(row, x, f"    next → [{nv}]")
                    row += 1
            else:
                for ci, (ch, nv) in enumerate(zip(choices, nexts)):
                    if row >= h - 2:
                        break
                    self.scr.addstr(row, x, f"    [{ci}] {ch[:20]} → {nv}")
                    row += 1
            row += 1  # blank line between nodes

        # Status bar
        status = self.status or ("[TAB]pane [j/k]move [e]dit [a]dd [d]el [n]ext [c]hoice [r]ename [s]ave [g]en [b]menu [q]uit")
        if h > 1:
            self.scr.addstr(h - 2, 0, "─" * (w - 1))
        if h > 0:
            self.scr.addstr(h - 1, 0, status[:w - 1])

        self.scr.refresh()
        self.status = ""

    def _draw_main_menu(self):
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        title   = "=== DIALOG EDITOR ==="
        options = [
            "[1] Hubs",
            "[2] NPCs",
            "[q] Quit",
        ]
        row = max(0, h // 2 - len(options))
        cx  = max(0, w // 2 - len(title) // 2)
        self.scr.addstr(row, cx, title)
        for i, opt in enumerate(options):
            ox = max(0, w // 2 - len(opt) // 2)
            self.scr.addstr(row + 2 + i, ox, opt)
        self.scr.refresh()

    def _handle_main_menu_key(self, key):
        ch = chr(key) if 0 < key < 256 else None
        if ch == '1':
            self.mode = 'hub_view'
            self.hub_cur = 0
            self.hub_focus = 'hubs'
            self.hub_roster_cur = 0
        elif ch == '2':
            self.mode = 'npc_view'
        elif ch == 'q':
            return self._quit()
        return True

    def _draw_hub_view(self):
        self.scr.erase()
        h, w = self.scr.getmaxyx()
        hubs  = self.hubs_data.get("hubs", [])

        # Left pane: hub list
        for i, hub in enumerate(hubs):
            is_cur  = (i == self.hub_cur)
            focused = (self.hub_focus == 'hubs' and is_cur)
            attr    = curses.A_REVERSE if focused else (curses.A_BOLD if is_cur else 0)
            line    = f"[{hub['id']}] {hub['name'][:14]}"
            if i < h - 2:
                self.scr.addstr(i, 0, line[:LEFT_W - 1].ljust(LEFT_W - 1), attr)

        # Divider
        for row in range(h - 2):
            self.scr.addstr(row, LEFT_W - 1, "│")

        # Right pane: NPC roster of selected hub
        if hubs and self.hub_cur < len(hubs):
            hub      = hubs[self.hub_cur]
            npc_by_id = {npc["id"]: npc["name"] for npc in self.npcs}
            roster   = hub.get("npc_ids", [])
            header   = f"Hub: {hub['name']}"
            self.scr.addstr(0, LEFT_W, header[:w - LEFT_W - 1])
            for i, npc_id in enumerate(roster):
                is_cur  = (i == self.hub_roster_cur)
                focused = (self.hub_focus == 'roster' and is_cur)
                attr    = curses.A_REVERSE if focused else 0
                name    = npc_by_id.get(npc_id, f"<id={npc_id}>")
                line    = f"  {name[:16]}"
                if i + 1 < h - 2:
                    self.scr.addstr(i + 1, LEFT_W, line[:w - LEFT_W - 1], attr)

        # Status bar
        if self.hub_focus == 'hubs':
            hints = "[TAB]roster [j/k]move [n]newHub [r]rename [D]delete [g]gen [b/Esc]menu"
        else:
            hints = "[TAB]hubs [j/k]move [a]addNPC [d]remove [g]gen [b/Esc]menu"
        status = self.status or hints
        if h > 1:
            self.scr.addstr(h - 2, 0, "─" * (w - 1))
        if h > 0:
            self.scr.addstr(h - 1, 0, status[:w - 1])
        self.scr.refresh()
        self.status = ""

    def _handle_hub_key(self, key):
        ch   = chr(key) if 0 < key < 256 else None
        hubs = self.hubs_data.get("hubs", [])

        # ── Navigation ────────────────────────────────────────────────────────
        if ch == '\t':
            self.hub_focus = 'roster' if self.hub_focus == 'hubs' else 'hubs'
            return True

        if ch in ('j',) or key == curses.KEY_DOWN:
            if self.hub_focus == 'hubs':
                self.hub_cur = min(self.hub_cur + 1, len(hubs) - 1)
                self.hub_roster_cur = 0
            else:
                roster_len = len(hubs[self.hub_cur]["npc_ids"]) if hubs else 0
                self.hub_roster_cur = min(self.hub_roster_cur + 1, max(roster_len - 1, 0))
            return True

        if ch in ('k',) or key == curses.KEY_UP:
            if self.hub_focus == 'hubs':
                self.hub_cur = max(self.hub_cur - 1, 0)
                self.hub_roster_cur = 0
            else:
                self.hub_roster_cur = max(self.hub_roster_cur - 1, 0)
            return True

        # ── Back to main menu ─────────────────────────────────────────────────
        if ch in ('b',) or key == 27:  # Esc = 27
            self.mode = 'main_menu'
            return True

        # ── Hub-list actions (focus = hubs) ───────────────────────────────────
        if self.hub_focus == 'hubs':
            if ch == 'n':
                return self._hub_new(hubs)
            if ch == 'r' and hubs:
                return self._hub_rename_action(hubs)
            if ch == 'D' and hubs:
                return self._hub_delete_action(hubs)

        # ── Roster actions (focus = roster) ───────────────────────────────────
        else:
            if ch == 'a' and hubs:
                return self._hub_picker(hubs)
            if ch == 'd' and hubs:
                return self._hub_remove_action(hubs)

        # ── Shared ────────────────────────────────────────────────────────────
        if ch == 'g':
            self._generate()
            return True
        if ch == 'q':
            return self._quit()

        return True

    def _hub_new(self, hubs):
        name = self._prompt("New hub name:", "")
        if not name:
            return True
        new_hub = {"id": next_hub_id(hubs), "name": name.upper()[:15], "npc_ids": []}
        hubs.append(new_hub)
        self.hubs_data["hubs"] = hubs
        self._save_hubs()
        self.hub_cur = len(hubs) - 1
        self.hub_roster_cur = 0
        self.status = f"Created hub '{new_hub['name']}'"
        return True

    def _hub_rename_action(self, hubs):
        new_name = self._prompt(f"Rename '{hubs[self.hub_cur]['name']}' to:", "")
        if not new_name:
            return True
        self.hubs_data["hubs"], self.status = hub_rename(hubs, self.hub_cur, new_name)
        self._save_hubs()
        return True

    def _hub_delete_action(self, hubs):
        name = hubs[self.hub_cur]["name"]
        confirm = self._prompt(f"Delete hub '{name}'? (y/N):", "N")
        if confirm.lower() != 'y':
            return True
        self.hubs_data["hubs"], self.status = hub_delete(hubs, self.hub_cur)
        self._save_hubs()
        self.hub_cur = max(0, self.hub_cur - 1) if self.hubs_data["hubs"] else 0
        self.hub_roster_cur = 0
        return True

    def _hub_picker(self, hubs):
        """Interactive NPC picker: shows only NPCs not already in this hub.
        j/k to move, Enter to add, Esc to cancel.
        """
        hub        = hubs[self.hub_cur]
        candidates = unassigned_npcs(self.npcs, hub["npc_ids"])
        if not candidates:
            self.status = "All NPCs already in this hub"
            return True

        pick_cur = 0
        while True:
            # Draw picker overlay on top of current hub view
            self._draw_hub_view()
            h, w = self.scr.getmaxyx()
            header = "Add NPC — j/k move, Enter select, Esc cancel"
            self.scr.addstr(0, LEFT_W, header[:w - LEFT_W - 1], curses.A_BOLD)
            for i, npc in enumerate(candidates):
                attr = curses.A_REVERSE if i == pick_cur else 0
                line = f"  [{npc['id']}] {npc['name'][:16]}"
                if i + 1 < h - 2:
                    self.scr.addstr(i + 1, LEFT_W, line[:w - LEFT_W - 1], attr)
            self.scr.refresh()

            key = self.scr.getch()
            ch  = chr(key) if 0 < key < 256 else None

            if ch == 'j' or key == curses.KEY_DOWN:
                pick_cur = min(pick_cur + 1, len(candidates) - 1)
            elif ch == 'k' or key == curses.KEY_UP:
                pick_cur = max(pick_cur - 1, 0)
            elif key in (10, 13, curses.KEY_ENTER):  # Enter
                npc_id = candidates[pick_cur]["id"]
                self.hubs_data["hubs"], self.status = hub_add_npc(hubs, self.hub_cur, npc_id)
                self._save_hubs()
                break
            elif key == 27 or ch == 'b':  # Esc or b = cancel
                self.status = "Cancelled"
                break

        return True

    def _hub_remove_action(self, hubs):
        hub    = hubs[self.hub_cur]
        roster = hub["npc_ids"]
        if not roster:
            self.status = "Hub roster is empty"
            return True
        npc_id   = roster[self.hub_roster_cur]
        npc_name = next((n["name"] for n in self.npcs if n["id"] == npc_id), f"id={npc_id}")
        confirm  = self._prompt(f"Remove '{npc_name}' from hub? (y/N):", "N")
        if confirm.lower() != 'y':
            return True
        self.hubs_data["hubs"], self.status = hub_remove_npc(hubs, self.hub_cur, self.hub_roster_cur)
        self._save_hubs()
        new_len = len(self.hubs_data["hubs"][self.hub_cur]["npc_ids"])
        self.hub_roster_cur = min(self.hub_roster_cur, max(new_len - 1, 0))
        return True

    def handle_key(self, key):
        ch = chr(key) if 0 < key < 256 else None
        if ch == '\t':
            self.focus = 'node' if self.focus == 'npc' else 'npc'
        elif ch in ('j', '\n') or key == curses.KEY_DOWN:
            if self.focus == 'npc':
                self.npc_cur = min(self.npc_cur + 1, len(self.npcs) - 1)
                self.node_cur = 0
            else:
                self.node_cur = min(self.node_cur + 1, len(self.cur_nodes) - 1)
        elif ch == 'k' or key == curses.KEY_UP:
            if self.focus == 'npc':
                self.npc_cur = max(self.npc_cur - 1, 0)
                self.node_cur = 0
            else:
                self.node_cur = max(self.node_cur - 1, 0)
        elif ch == 'e':
            self._edit_text()
        elif ch == 'a':
            self._add()
        elif ch == 'd':
            self._delete()
        elif ch == 'n':
            self._set_next()
        elif ch == 'c':
            self._toggle_choice()
        elif ch == 'r':
            self._rename_npc()
        elif ch == 's':
            self._save()
        elif ch == 'g':
            self._generate()
        elif ch in ('b',) or key == 27:   # Esc or b → main menu
            self.mode = 'main_menu'
        elif ch == 'q':
            return self._quit()
        return True

    def _prompt(self, prompt_str, default=""):
        h, w = self.scr.getmaxyx()
        curses.echo()
        curses.curs_set(1)
        self.scr.addstr(h - 1, 0, (prompt_str + " ")[:w - 1])
        self.scr.clrtoeol()
        buf = self.scr.getstr(h - 1, len(prompt_str) + 1, w - len(prompt_str) - 2)
        curses.noecho()
        curses.curs_set(0)
        result = buf.decode('utf-8', errors='replace').strip()
        return result if result else default

    def _edit_text(self):
        if not self.cur_nodes:
            return
        node  = self.cur_nodes[self.node_cur]
        new_t = self._prompt(f"Text ({len(node['text'])}/{MAX_TEXT_LEN}):", node['text'])
        if len(new_t) >= MAX_TEXT_LEN:
            self.status = f"ERROR: text is {len(new_t)} chars (max {MAX_TEXT_LEN - 1}). Save/gen blocked."
            return
        node['text'] = new_t
        self.dirty = True

    def _add(self):
        if self.focus == 'npc':
            n = len(self.npcs)
            if n >= self.max_npcs:
                wram_each = 2  # uint8_t current_node + uint8_t flags
                new_max = self.max_npcs + 1
                wram_total = new_max * wram_each
                confirm = self._prompt(
                    f"MAX_NPCS is {self.max_npcs} — increase to {new_max}? "
                    f"WRAM: {new_max}×{wram_each}={wram_total}B. (y/N):", "N")
                if confirm.lower() != 'y':
                    return
                # Patch config.h
                try:
                    with open(CONFIG_H) as f:
                        cfg = f.read()
                    import dialog_to_c as _conv
                    new_cfg = _conv.patch_config_define(cfg, "MAX_NPCS", new_max)
                    with open(CONFIG_H, 'w') as f:
                        f.write(new_cfg)
                    self.max_npcs = new_max
                    self.status = f"MAX_NPCS updated to {new_max} in src/config.h"
                except Exception as e:
                    self.status = f"ERROR patching config.h: {e}"
                    return
            name = self._prompt("New NPC name:")
            if not name:
                return
            new_id = max(npc['id'] for npc in self.npcs) + 1
            stub = {"idx": 0, "text": "...", "choices": [], "next": ["END"]}
            self.npcs.append({"id": new_id, "name": name.upper()[:15], "nodes": [stub]})
            self.dirty = True
            return
        else:
            nodes  = self.cur_nodes
            new_idx = len(nodes)
            nodes.append({"idx": new_idx, "text": "...", "choices": [], "next": ["END"]})
            self.node_cur = new_idx
        self.dirty = True

    def _load_hubs(self):
        if os.path.exists(self.hubs_path):
            with open(self.hubs_path) as f:
                return json.load(f)
        return {"hubs": []}

    def _save_hubs(self):
        with open(self.hubs_path, 'w') as f:
            json.dump(self.hubs_data, f, indent=2)
            f.write('\n')

    def _delete(self):
        if self.focus == 'node':
            nodes = self.cur_nodes
            if not nodes:
                return
            di = self.node_cur
            del nodes[di]
            # Re-sequence idx fields
            for i, n in enumerate(nodes):
                n['idx'] = i
            renumber_refs(nodes, di)
            if not nodes:
                # R5: preserve NPC slot as a 1-node stub — never fully empty
                nodes.append({"idx": 0, "text": "...", "choices": [], "next": ["END"]})
                self.node_cur = 0
            else:
                self.node_cur = min(self.node_cur, len(nodes) - 1)
            self.dirty = True

    def _set_next(self):
        if not self.cur_nodes:
            return
        node  = self.cur_nodes[self.node_cur]
        nexts = node["next"]
        if not nexts:
            self.status = "No next slots (add a choice first)"
            return
        slot = 0
        if len(nexts) > 1:
            raw = self._prompt(f"Which slot? (0-{len(nexts)-1}):", "0")
            try:
                slot = int(raw)
            except ValueError:
                return
            if slot < 0 or slot >= len(nexts):
                return
        raw = self._prompt(f"next[{slot}] = (index or END):", str(nexts[slot]))
        if raw.upper() == "END":
            nexts[slot] = "END"
        else:
            try:
                nexts[slot] = int(raw)
            except ValueError:
                self.status = "Invalid value; must be an integer or END"
                return
        self.dirty = True

    def _toggle_choice(self):
        if not self.cur_nodes:
            return
        node    = self.cur_nodes[self.node_cur]
        choices = node["choices"]
        nexts   = node["next"]
        if len(choices) < MAX_CHOICES:
            label = self._prompt("Choice label:")
            if not label:
                return
            choices.append(label)
            nexts.append("END")
        else:
            # Remove last choice
            choices.pop()
            nexts.pop()
            if not choices:
                nexts.append("END")  # narration node always has at least one next
        self.dirty = True

    def _rename_npc(self):
        npc  = self.cur_npc
        name = self._prompt(f"Rename '{npc['name']}' to:", npc['name'])
        if name and len(name) <= 15:
            npc['name'] = name.upper()
            self.dirty = True
        elif name:
            self.status = f"ERROR: name '{name}' exceeds 15 chars"

    def _any_text_too_long(self):
        for npc in self.npcs:
            for node in npc["nodes"]:
                if len(node["text"]) >= MAX_TEXT_LEN:
                    return True
        return False

    def _save(self):
        if self._any_text_too_long():
            self.status = "ERROR: some node text ≥ 63 chars. Fix before saving."
            return
        save_json(self.data, self.path)
        self.dirty = False
        self.status = f"Saved to {self.path}"

    def _generate(self):
        self._save()
        if self.dirty:  # save was blocked
            return
        cmd = [
            sys.executable, GENERATOR, self.path, OUT_C,
            "--hubs-json", self.hubs_path,
            "--hub-out",   HUB_OUT_C,
            "--config-h",  CONFIG_H,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            self.status = f"Generated {OUT_C} + {HUB_OUT_C}"
        else:
            self.status = f"ERROR: {result.stderr[:80]}"

    def _quit(self):
        if self.dirty:
            h, w = self.scr.getmaxyx()
            self.scr.addstr(h - 1, 0, "Unsaved changes. Quit anyway? (y/N): ")
            self.scr.clrtoeol()
            k = self.scr.getch()
            if chr(k) not in ('y', 'Y'):
                return True
        return False


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_JSON
    if not os.path.exists(path):
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)
    curses.wrapper(lambda scr: DialogEditor(scr, path).run())


if __name__ == "__main__":
    main()
