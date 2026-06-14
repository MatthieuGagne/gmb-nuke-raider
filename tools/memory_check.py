#!/usr/bin/env python3
"""
memory_check.py — WRAM, VRAM, and OAM budget validator.

Checks:
  1. WRAM: parses build/nuke-raider.map for s__HEAP_E symbol vs 8,192-byte budget.
  2. VRAM: scans src/*_tiles.c for *_count = N values vs 384-tile budget.
  3. OAM:  scene-aware. Scenes (game states) are mutually exclusive and all share the
           one recycling sprite pool, so the OAM that matters is the *busiest single
           scene*, not the sum of every sprite in the game. The busiest scene (Playing)
           is reported vs the 40-slot hardware cap, and cross-checked against the pool
           size MAX_SPRITES (peak > pool => FAIL: pool too small; peak < pool => WARN:
           over-provisioned). Per-consumer counts come from src/config.h constants.

Exits 0 on PASS/WARN, 1 on FAIL.

Usage:
    python3 tools/memory_check.py [repo_root]
    python3 tools/memory_check.py --scenes-json [repo_root]   # emit the scene model
    or imported: memory_check.check(repo_root) -> dict
"""
import glob
import json
import os
import re
import sys

WRAM_BUDGET = 8192   # bytes
VRAM_BUDGET = 384    # tiles (2 CGB banks × 192)
OAM_BUDGET  = 40     # sprite slots (hardware cap — cannot change)

WARN_FRAC = 0.80
FAIL_FRAC = 1.00

WRAM_BASE = 0xC000

# ── Per-scene OAM model ──────────────────────────────────────────────────────────
# Each game state ("scene") lists the sprite consumers active while it is on screen.
# A consumer is (label, source, slots_per_entity); slots = source * slots_per_entity,
# where source is either an int literal or the name of a src/config.h #define.
# Scenes are mutually exclusive and reuse the same pool (sprite_pool.c wipes + reallocs
# on each scene's init), so live OAM = the busiest single scene, never the sum.
#
# Notes baked in from the code (keep in sync if these change):
#   - player car = 4 OAM slots (4 get_sprite() calls in player_init).
#   - explosions are slot-neutral: explosion_spawn() reuses the dying entity's slot
#     (turret blast on its own slot; car blast on the player's slots), so GameOver and
#     in-race explosions add nothing on top of the entities they replace.
#   - overmap car = slot 0 only (overmap clears slots 1-39); hub = dialog_arrow (slot 4).
#
# This table is the SOURCE OF TRUTH for the HTML explainer's scene selector
# (docs/memory-explained.html). Regenerate that file's embedded data with:
#     python tools/memory_check.py --scenes-json
SCENE_CONSUMERS = {
    'Title':    [],
    'Overmap':  [('car', 1, 1)],            # overmap car, slot 0
    'Hub':      [('dialog_arrow', 1, 1)],   # DIALOG_ARROW_OAM_SLOT
    'Prerace':  [],                         # text-only menu
    'Playing':  [
        ('player',      4,                  1),   # 4 get_sprite() in player_init
        ('projectiles', 'MAX_PROJECTILES',  1),
        ('turrets',     'MAX_ENEMIES',      1),
        ('racers',      'MAX_ENEMY_RACERS', 4),   # enemy racers, 4 slots each
        ('patrol',      'MAX_PATROLS',      4),   # patrol car, 4 slots each
    ],
    'Results':  [],                         # text-only
    'GameOver': [],                         # car blast reuses player slots (slot-neutral)
}

_SEVERITY = {'PASS': 0, 'WARN': 1, 'FAIL': 2, 'ERROR': 3}


def _status(used, budget):
    frac = used / budget
    if frac >= FAIL_FRAC:
        return 'FAIL'
    if frac >= WARN_FRAC:
        return 'WARN'
    return 'PASS'


def _worst(*statuses):
    """Return the most severe status (ERROR > FAIL > WARN > PASS)."""
    return max(statuses, key=lambda s: _SEVERITY.get(s, 0))


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


def _parse_config_constants(repo_root):
    """Parse all `#define NAME <int>` from src/config.h. Returns dict or None if missing."""
    config_path = os.path.join(repo_root, 'src', 'config.h')
    try:
        with open(config_path) as f:
            content = f.read()
    except FileNotFoundError:
        return None
    consts = {}
    for m in re.finditer(r'#define\s+(\w+)\s+(\d+)u?\b', content):
        consts[m.group(1)] = int(m.group(2))
    return consts


def _resolve(source, consts):
    """Resolve a consumer source: an int literal, or a config.h constant name (0 if absent)."""
    if isinstance(source, int):
        return source
    return consts.get(source, 0)


def _scene_breakdown(consts):
    """Resolve SCENE_CONSUMERS against parsed constants.

    Returns {scene: {'peak': int, 'consumers': [{'label', 'slots'}, ...]}}.
    """
    scenes = {}
    for name, consumers in SCENE_CONSUMERS.items():
        items = []
        peak = 0
        for label, source, per_entity in consumers:
            slots = _resolve(source, consts) * per_entity
            items.append({'label': label, 'slots': slots})
            peak += slots
        scenes[name] = {'peak': peak, 'consumers': items}
    return scenes


def _check_oam(repo_root):
    """Scene-aware OAM check. Returns a dict (see module docstring).

    Keys: used (busiest-scene peak, None on ERROR), budget, status, worst_scene,
    scenes, pool (MAX_SPRITES), crosscheck, crosscheck_msg, util_status.
    """
    consts = _parse_config_constants(repo_root)
    if consts is None:
        return {
            'used': None, 'budget': OAM_BUDGET, 'status': 'ERROR',
            'worst_scene': None, 'scenes': {}, 'pool': None,
            'crosscheck': 'ERROR', 'crosscheck_msg': 'src/config.h not found',
            'util_status': 'ERROR',
        }

    scenes = _scene_breakdown(consts)
    worst_scene = max(scenes, key=lambda s: scenes[s]['peak'])
    peak = scenes[worst_scene]['peak']
    pool = consts.get('MAX_SPRITES', 0)

    util_status = _status(peak, OAM_BUDGET)

    if peak > pool:
        crosscheck = 'FAIL'
        msg = f'busiest scene ({worst_scene}) needs {peak} slots but pool MAX_SPRITES={pool}'
    elif peak < pool:
        crosscheck = 'WARN'
        msg = f'pool MAX_SPRITES={pool} over-provisioned for busiest scene ({worst_scene}={peak})'
    else:
        crosscheck = 'PASS'
        msg = f'pool MAX_SPRITES={pool} matches busiest scene ({worst_scene})'

    return {
        'used': peak, 'budget': OAM_BUDGET,
        'status': _worst(util_status, crosscheck),
        'worst_scene': worst_scene, 'scenes': scenes, 'pool': pool,
        'crosscheck': crosscheck, 'crosscheck_msg': msg,
        'util_status': util_status,
    }


def scenes_json(repo_root='.'):
    """Build the per-scene OAM model for external consumers (e.g. the HTML explainer)."""
    consts = _parse_config_constants(repo_root) or {}
    scenes = _scene_breakdown(consts)
    worst_scene = max(scenes, key=lambda s: scenes[s]['peak']) if scenes else None
    return {
        'budget': OAM_BUDGET,
        'pool': consts.get('MAX_SPRITES'),
        'worst_scene': worst_scene,
        'scenes': scenes,
    }


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
    ]
    if o['used'] is None:
        lines.append(f"OAM:   ERROR — {o['crosscheck_msg']}")
    else:
        lines.append(
            f"OAM:   {o['used']} / {o['budget']} sprites  ({pct(o['used'], o['budget'])}%)  "
            f"{o['status']}  [busiest scene: {o['worst_scene']}]"
        )
        lines.append(f"       cross-check vs pool: {o['crosscheck']} — {o['crosscheck_msg']}")
        lines.append('       per-scene peak OAM:')
        for name, sc in o['scenes'].items():
            detail = ', '.join(f"{c['label']}={c['slots']}" for c in sc['consumers']) or '—'
            lines.append(f"         {name:<9} {sc['peak']:>2} / {o['budget']}   ({detail})")
    lines += ['', overall_status(result)]
    return '\n'.join(lines)


def check(repo_root='.'):
    """Run all three checks. Returns dict with 'wram', 'vram', 'oam' entries."""
    wram_used, wram_status = _check_wram(repo_root)
    vram_used, vram_status = _check_vram(repo_root)
    oam = _check_oam(repo_root)
    return {
        'wram': {'used': wram_used, 'budget': WRAM_BUDGET, 'status': wram_status},
        'vram': {'used': vram_used, 'budget': VRAM_BUDGET, 'status': vram_status},
        'oam':  oam,
    }


def main():
    args = sys.argv[1:]
    if args and args[0] == '--scenes-json':
        repo_root = args[1] if len(args) > 1 else '.'
        print(json.dumps(scenes_json(repo_root), indent=2))
        sys.exit(0)
    repo_root = args[0] if args else '.'
    result = check(repo_root)
    print(_format_report(result))
    sys.exit(1 if overall_status(result) == 'FAIL' else 0)


if __name__ == '__main__':
    main()
