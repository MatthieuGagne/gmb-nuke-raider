#!/usr/bin/env python3
"""Nuke Raider game-feel balancer — tune config.h variables via TUI.

Usage:
    python3 tools/balancer.py

Keys:
    ↑/↓        navigate variables
    ←/→        decrement/increment value (clamped to min/max)
    s          save changes to src/config.h
    q          quit (prompts if unsaved changes)
"""
import os
import re
import subprocess
import sys
import termios
import tty

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT   = os.path.dirname(SCRIPT_DIR)
CONFIG_H    = os.path.join(REPO_ROOT, 'src', 'config.h')

# ---------------------------------------------------------------------------
# Variable catalogue — (name, category, min, max)
# ---------------------------------------------------------------------------
VARIABLES = [
    ('GEAR1_MAX_SPEED',             'Car Physics', 1,  15),
    ('GEAR1_ACCEL',                 'Car Physics', 1,  15),
    ('GEAR2_MAX_SPEED',             'Car Physics', 1,  15),
    ('GEAR2_ACCEL',                 'Car Physics', 1,  15),
    ('GEAR3_MAX_SPEED',             'Car Physics', 1,  15),
    ('GEAR3_ACCEL',                 'Car Physics', 1,  15),
    ('GEAR_DOWNSHIFT_FRAMES',       'Car Physics', 1,  60),
    ('PLAYER_FRICTION',             'Car Physics', 0,   8),
    ('PLAYER_MAX_HP',               'Combat',      1, 255),
    ('PLAYER_ARMOR',                'Combat',      0,  15),
    ('DAMAGE_INVINCIBILITY_FRAMES', 'Combat',      0,  60),
    ('ENEMY_BULLET_DAMAGE',         'Combat',      1,  99),
    ('PROJ_FIRE_COOLDOWN',          'Combat',      1,  60),
    ('PROJ_SPEED',                  'Combat',      1,  15),
    ('TURRET_FIRE_INTERVAL',        'Enemies',     1, 120),
    ('TURRET_HP',                   'Enemies',     1,  10),
]

# ---------------------------------------------------------------------------
# Pure logic helpers (testable without TUI)
# ---------------------------------------------------------------------------

def parse_config(text: str) -> dict:
    """Return {name: int} for every #define NAME value[u] line."""
    result = {}
    for line in text.splitlines():
        m = re.match(r'^\s*#define\s+(\w+)\s+(\d+)u?', line)
        if m:
            result[m.group(1)] = int(m.group(2))
    return result


def apply_changes(text: str, changes: dict) -> str:
    """Return config text with values in `changes` updated in-place.

    Preserves the trailing u suffix and any inline comments.
    """
    if not changes:
        return text
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        m = re.match(r'^(#define\s+(\w+)\s+)(\d+)(u?)(\s*.*)', line)
        if m and m.group(2) in changes:
            lines[i] = m.group(1) + str(changes[m.group(2)]) + m.group(4) + m.group(5)
    return ''.join(lines)


# ---------------------------------------------------------------------------
# Keyboard input
# ---------------------------------------------------------------------------

def _read_key(fd: int) -> str:
    """Read one keypress from raw-mode fd; return a string token."""
    ch = os.read(fd, 1)
    if ch == b'\x1b':
        rest = os.read(fd, 2)
        seq = ch + rest
        return {
            b'\x1b[A': 'UP',
            b'\x1b[B': 'DOWN',
            b'\x1b[C': 'RIGHT',
            b'\x1b[D': 'LEFT',
        }.get(seq, '')
    return ch.decode('ascii', errors='replace')


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _build_panel(variables, values, cursor, status):
    table = Table.grid(padding=(0, 2))
    table.add_column(justify='left',  no_wrap=True)
    table.add_column(justify='right', no_wrap=True)
    table.add_column(justify='left',  no_wrap=True)

    last_cat = None
    for idx, (name, cat, lo, hi) in enumerate(variables):
        if cat != last_cat:
            table.add_row(Text(f'\n  {cat}', style='bold yellow'), '', '')
            last_cat = cat
        val    = values.get(name, '?')
        is_cur = idx == cursor
        style  = 'bold cyan' if is_cur else 'white'
        arrow  = '\u25b6 ' if is_cur else '  '
        table.add_row(
            Text(f'{arrow}{name}', style=style),
            Text(f'[{val:>3}]',    style=style),
            Text(f'({lo}\u2013{hi})', style='dim'),
        )

    table.add_row('', '', '')
    table.add_row(
        Text('  [\u2191\u2193] navigate  [\u2190\u2192] change  [s] save  [q] quit',
             style='dim'),
        '', '',
    )
    if status:
        st_style = 'green' if status.startswith('Saved') else 'red'
        table.add_row(Text(f'  {status}', style=st_style), '', '')

    return Panel(table, title='[bold]Nuke Raider Balancer[/bold]', border_style='blue')


# ---------------------------------------------------------------------------
# Main TUI loop
# ---------------------------------------------------------------------------

def main():
    with open(CONFIG_H) as f:
        original_text = f.read()

    all_values   = parse_config(original_text)
    var_names    = [v[0] for v in VARIABLES]
    values       = {n: all_values[n] for n in var_names if n in all_values}
    saved_values = dict(values)
    cursor       = 0
    status       = ''

    console      = Console()
    fd           = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    try:
        tty.setraw(fd)
        with Live(_build_panel(VARIABLES, values, cursor, status),
                  console=console, refresh_per_second=30, screen=True) as live:
            while True:
                key = _read_key(fd)

                if key == 'UP':
                    cursor = max(0, cursor - 1)
                elif key == 'DOWN':
                    cursor = min(len(VARIABLES) - 1, cursor + 1)
                elif key in ('LEFT', 'RIGHT'):
                    name, _, lo, hi = VARIABLES[cursor]
                    delta = -1 if key == 'LEFT' else 1
                    values[name] = max(lo, min(hi, values[name] + delta))
                    status = ''
                elif key == 's':
                    changes  = {n: v for n, v in values.items()
                                if v != saved_values.get(n)}
                    new_text = apply_changes(original_text, changes)
                    try:
                        with open(CONFIG_H, 'w') as f:
                            f.write(new_text)
                        original_text = new_text
                        saved_values  = dict(values)
                        status        = 'Saved.'
                    except OSError as e:
                        status = f'Error: {e}'
                elif key in ('q', '\x03'):  # q or Ctrl-C
                    if values != saved_values:
                        live.stop()
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                        ans = input('Unsaved changes. Quit? [y/N] ').strip().lower()
                        if ans != 'y':
                            tty.setraw(fd)
                            live.start()
                            status = ''
                            live.update(_build_panel(VARIABLES, values, cursor, status))
                            continue
                    break

                live.update(_build_panel(VARIABLES, values, cursor, status))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    # Optional build prompt — after TUI exits, tool exits after build
    ans = input('Build now? [y/N] ').strip().lower()
    if ans == 'y':
        os.chdir(REPO_ROOT)
        ret = subprocess.call(
            'make clean && GBDK_HOME=/home/mathdaman/gbdk make',
            shell=True,
        )
        sys.exit(ret)


if __name__ == '__main__':
    main()
