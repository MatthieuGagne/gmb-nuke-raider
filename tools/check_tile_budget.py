#!/usr/bin/env python3
"""
check_tile_budget.py — per-state tile slot budget validator.

Reads *_count values from src/*.c files and checks that each game state's
tile assets fit within the loader-managed VRAM pool:
  - Sprite pool: slots 0–63   (SPRITE_BUDGET = 64)
  - BG pool:     slots 143–254 (BG_BUDGET = 112, derived from LOADER_BG_START=143)

Exits 0 on PASS, 1 on FAIL.

Usage:
    python3 tools/check_tile_budget.py [repo_root]
    or imported: check_tile_budget.check(repo_root) -> list[dict]
"""
import glob
import os
import re
import sys

SPRITE_BUDGET = 64   # slots 0–63  (update if config.h LOADER_SPRITE_END changes)
BG_BUDGET     = 112  # slots 143–254 (update if config.h LOADER_BG_START changes)

# Per-state manifest: maps state name → {'sprite': [...symbols], 'bg': [...symbols]}
# Keep in sync with loader.c k_*_assets[] arrays and loader_registry_tbl[].
# HUD_FONT is self-managed by hud.c and excluded from all manifests.
STATE_MANIFESTS = {
    'playing': {
        'sprite': [
            'player_tile_data_count',
            'bullet_tile_data_count',
            'turret_tile_data_count',
        ],
        'bg': [
            'track_tile_data_count',
        ],
    },
    'overmap': {
        'sprite': [
            'overmap_car_tile_data_count',
        ],
        'bg': [
            'overmap_tile_data_count',
        ],
    },
    'hub': {
        'sprite': [
            'dialog_arrow_tile_data_count',
        ],
        'bg': [
            'npc_drifter_portrait_count',
            'npc_mechanic_portrait_count',
            'npc_trader_portrait_count',
            'dialog_border_tiles_count',
        ],
    },
}


def _parse_counts(src_dir):
    """Scan all src/*.c files for `const uint8_t <name> = <N>u?;` lines.

    Returns a dict mapping symbol name → int value.
    A symbol appearing in multiple files takes its last seen value (should not happen).
    """
    counts = {}
    pattern = re.compile(r'const\s+uint8_t\s+(\w+)\s*=\s*(\d+)u?\s*;')
    for path in glob.glob(os.path.join(src_dir, '*.c')):
        with open(path) as f:
            for line in f:
                m = pattern.search(line)
                if m:
                    counts[m.group(1)] = int(m.group(2))
    return counts


def _check_state(counts, state_name, manifest):
    """Return dict with keys: state, sprite_used, bg_used, status."""
    sprite_used = sum(counts.get(sym, 0) for sym in manifest['sprite'])
    bg_used     = sum(counts.get(sym, 0) for sym in manifest['bg'])
    if sprite_used > SPRITE_BUDGET or bg_used > BG_BUDGET:
        status = 'FAIL'
    else:
        status = 'PASS'
    return {
        'state':       state_name,
        'sprite_used': sprite_used,
        'bg_used':     bg_used,
        'status':      status,
    }


def check(repo_root='.'):
    """Run budget check for all states. Returns list of result dicts."""
    src_dir = os.path.join(repo_root, 'src')
    counts = _parse_counts(src_dir)
    return [
        _check_state(counts, name, manifest)
        for name, manifest in STATE_MANIFESTS.items()
    ]


def main():
    repo_root = sys.argv[1] if len(sys.argv) > 1 else '.'
    results = check(repo_root)

    any_fail = False
    print('Tile budget check:')
    print(f'  Sprite budget: {SPRITE_BUDGET} slots | BG budget: {BG_BUDGET} slots')
    print()
    for r in results:
        sprite_free = SPRITE_BUDGET - r['sprite_used']
        bg_free     = BG_BUDGET     - r['bg_used']
        print(f"  [{r['status']:4s}] {r['state']:8s}  "
              f"sprite {r['sprite_used']:3d}/{SPRITE_BUDGET} ({sprite_free:3d} free)  "
              f"BG {r['bg_used']:3d}/{BG_BUDGET} ({bg_free:3d} free)")
        if r['status'] == 'FAIL':
            any_fail = True

    print()
    if any_fail:
        print('FAIL: one or more states exceed tile slot budget.')
        sys.exit(1)
    else:
        print('PASS: all states within tile slot budget.')


if __name__ == '__main__':
    main()
