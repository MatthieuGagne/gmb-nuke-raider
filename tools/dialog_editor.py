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

MAX_NPCS     = 6
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
        status = self.status or ("[TAB]pane [j/k]move [e]dit [a]dd [d]el [n]ext [c]hoice [r]ename [s]ave [g]en [q]uit")
        if h > 1:
            self.scr.addstr(h - 2, 0, "─" * (w - 1))
        if h > 0:
            self.scr.addstr(h - 1, 0, status[:w - 1])

        self.scr.refresh()
        self.status = ""

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
            if len(self.npcs) >= MAX_NPCS:
                self.status = f"ERROR: already at MAX_NPCS={MAX_NPCS}. Cannot add more NPCs."
                return
            name = self._prompt("New NPC name:")
            if not name:
                return
            new_id = max(n['id'] for n in self.npcs) + 1
            self.npcs.append({
                "id": new_id,
                "name": name.upper()[:MAX_NPCS],
                "nodes": [{"idx": 0, "text": "...", "choices": [], "next": ["END"]}]
            })
        else:
            nodes  = self.cur_nodes
            new_idx = len(nodes)
            nodes.append({"idx": new_idx, "text": "...", "choices": [], "next": ["END"]})
            self.node_cur = new_idx
        self.dirty = True

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
        result = subprocess.run(
            [sys.executable, GENERATOR, self.path, OUT_C],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            self.status = f"Generated {OUT_C}"
        else:
            self.status = f"ERROR: {result.stderr[:60]}"

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
