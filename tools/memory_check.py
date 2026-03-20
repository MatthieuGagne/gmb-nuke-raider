#!/usr/bin/env python3
"""
memory_check.py — WRAM, VRAM, and OAM budget validator.

Checks:
  1. WRAM: parses build/nuke-raider.map for s__HEAP_E symbol vs 8,192-byte budget.
  2. VRAM: scans src/*_tiles.c for *_count = N values vs 384-tile budget.
  3. OAM:  parses src/config.h for MAX_SPRITES + 3 fixed slots vs 40-slot budget.

Exits 0 on PASS/WARN, 1 on FAIL.

Usage:
    python3 tools/memory_check.py [repo_root]
    or imported: memory_check.check(repo_root) -> dict
"""
import glob
import os
import re
import sys

WRAM_BUDGET = 8192   # bytes
VRAM_BUDGET = 384    # tiles (2 CGB banks × 192)
OAM_BUDGET  = 40     # sprite slots

WARN_FRAC = 0.80
FAIL_FRAC = 1.00

WRAM_BASE = 0xC000

# Fixed OAM slots outside the sprite pool: player top + player bottom + dialog_arrow
OAM_FIXED_SLOTS = 3


def _status(used, budget):
    frac = used / budget
    if frac >= FAIL_FRAC:
        return 'FAIL'
    if frac >= WARN_FRAC:
        return 'WARN'
    return 'PASS'


def _check_wram(repo_root):
    """Parse build/nuke-raider.map for s__HEAP_E. Returns (used_bytes, status)."""
    map_path = os.path.join(repo_root, 'build', 'nuke-raider.map')
    try:
        with open(map_path) as f:
            content = f.read()
    except FileNotFoundError:
        return None, 'ERROR'
    m = re.search(r'([0-9A-Fa-f]{8})\s+s__HEAP_E\b', content)
    if not m:
        return None, 'ERROR'
    heap_e = int(m.group(1), 16)
    used = heap_e - WRAM_BASE
    return used, _status(used, WRAM_BUDGET)


def _check_vram(repo_root):
    """Scan src/*_tiles.c for *_count = N values. Returns (total_tiles, status)."""
    src_dir = os.path.join(repo_root, 'src')
    total = 0
    for path in glob.glob(os.path.join(src_dir, '*_tiles.c')):
        with open(path) as f:
            content = f.read()
        for m in re.finditer(r'_count\s*=\s*(\d+)', content):
            total += int(m.group(1))
    return total, _status(total, VRAM_BUDGET)


def _check_oam(repo_root):
    """Parse src/config.h for MAX_SPRITES + fixed slots. Returns (slots, status)."""
    config_path = os.path.join(repo_root, 'src', 'config.h')
    try:
        with open(config_path) as f:
            content = f.read()
    except FileNotFoundError:
        return None, 'ERROR'
    m = re.search(r'#define\s+MAX_SPRITES\s+(\d+)', content)
    pool_sprites = int(m.group(1)) if m else 0
    total = pool_sprites + OAM_FIXED_SLOTS
    return total, _status(total, OAM_BUDGET)


def overall_status(result):
    """Return FAIL > WARN > PASS based on worst individual status."""
    statuses = [v['status'] for v in result.values()]
    if 'FAIL' in statuses or 'ERROR' in statuses:
        return 'FAIL'
    if 'WARN' in statuses:
        return 'WARN'
    return 'PASS'


def _format_report(result):
    def pct(used, budget):
        return int(used / budget * 100) if used is not None else 0

    w = result['wram']
    v = result['vram']
    o = result['oam']
    lines = [
        '=== GB Memory Validation Report ===',
        f"WRAM:  {w['used']:,} / {w['budget']:,} bytes   ({pct(w['used'], w['budget'])}%)  {w['status']}",
        f"VRAM:  {v['used']} / {v['budget']} tiles   ({pct(v['used'], v['budget'])}%)  {v['status']}",
        f"OAM:   {o['used']} / {o['budget']} sprites  ({pct(o['used'], o['budget'])}%)  {o['status']}",
        '',
        overall_status(result),
    ]
    return '\n'.join(lines)


def check(repo_root='.'):
    """Run all three checks. Returns dict with 'wram', 'vram', 'oam' entries."""
    wram_used, wram_status = _check_wram(repo_root)
    vram_used, vram_status = _check_vram(repo_root)
    oam_used,  oam_status  = _check_oam(repo_root)
    return {
        'wram': {'used': wram_used, 'budget': WRAM_BUDGET, 'status': wram_status},
        'vram': {'used': vram_used, 'budget': VRAM_BUDGET, 'status': vram_status},
        'oam':  {'used': oam_used,  'budget': OAM_BUDGET,  'status': oam_status},
    }


def main():
    repo_root = sys.argv[1] if len(sys.argv) > 1 else '.'
    result = check(repo_root)
    print(_format_report(result))
    sys.exit(1 if overall_status(result) == 'FAIL' else 0)


if __name__ == '__main__':
    main()
