"""test_regression.py — full state traversal regression suite.

One PyBoy session navigates through every game state in sequence:
    title → overmap → hub → overmap → playing → game_over → title

Pass criterion: no PyBoy exception raised within per-state frame budgets.

Navigation sequences are derived from source-code analysis — not empirical probing.
See docs/plans/2026-03-29-headless-regression-suite.md for derivation details.
"""
from __future__ import annotations

from tests.integration.helpers import GameSession, find_wram_read_in_fn

# ---------------------------------------------------------------------------
# Navigation constants (derived from src/state_overmap.c + src/overmap_map.c)
# ---------------------------------------------------------------------------
_TRAVEL_FRAMES_PER_TILE = 4   # TRAVEL_FRAMES_PER_TILE in state_overmap.c
_HUB_TO_CITY_HUB_TILES  = 2   # spawn(9,8) → CITY_HUB(9,6): 2 tiles UP
_HUB_TO_DEST_TILES       = 7   # spawn(9,8) → DEST(2,8): 7 tiles LEFT
_SETTLE                  = 5   # extra frames after each state transition

_TITLE_BOOT_FRAMES    = 60
_OVERMAP_SETTLE       = 10
_HUB_NAV_FRAMES       = _HUB_TO_CITY_HUB_TILES * _TRAVEL_FRAMES_PER_TILE + _SETTLE
_HUB_DWELL_FRAMES     = 10
_PLAYING_NAV_FRAMES   = _HUB_TO_DEST_TILES * _TRAVEL_FRAMES_PER_TILE + _SETTLE
_PLAYING_DWELL_FRAMES = 5
_GAME_OVER_FRAMES     = 10


def test_all_states(game_session: GameSession, map_path: str, rom_path: str, noi_path: str) -> None:
    """Navigate through every game state in one session; assert no crash per state."""
    s = game_session

    # ── 1. Title screen ──────────────────────────────────────────────────────
    s.advance(_TITLE_BOOT_FRAMES)
    # If we reach here without a PyBoy exception, title state is stable.

    # ── 2. Overmap ───────────────────────────────────────────────────────────
    s.press(["START"])
    s.advance(_OVERMAP_SETTLE)
    # Overmap entered: player car at HUB spawn (col=9, row=8).

    # ── 3. Hub ───────────────────────────────────────────────────────────────
    # One UP press → find_next_node(0,-1) jumps to CITY_HUB at (9,6).
    # Travel: 2 tiles × 4 frames/tile = 8 frames. Add _SETTLE buffer.
    s.press(["UP"])
    s.advance(_HUB_NAV_FRAMES)
    # state_push(&state_hub) fires automatically on arrival.
    s.advance(_HUB_DWELL_FRAMES)

    # ── 4. Back to overmap ───────────────────────────────────────────────────
    # START in hub → state_pop() → overmap re-enters at spawn (9,8).
    s.press(["START"])
    s.advance(_OVERMAP_SETTLE)

    # ── 5. Playing ───────────────────────────────────────────────────────────
    # One LEFT press → find_next_node(-1,0) jumps to DEST at (2,8).
    # Travel: 7 tiles × 4 frames/tile = 28 frames. Add _SETTLE buffer.
    s.press(["LEFT"])
    s.advance(_PLAYING_NAV_FRAMES)
    # state_replace(&state_playing) fires automatically on arrival.
    s.advance(_PLAYING_DWELL_FRAMES)

    # ── 6. Game over ─────────────────────────────────────────────────────────
    # Write 0 to static `hp` in damage.c via WRAM map symbol lookup.
    # Next frame: damage_is_dead() returns true → state_replace(&state_game_over).
    # `hp` is static in damage.c — not exported to .map. Locate it by
    # disassembling damage_get_hp() from the ROM binary (.noi gives its address).
    hp_addr = find_wram_read_in_fn(noi_path, rom_path, "_damage_get_hp")
    s.write_wram(hp_addr, 0)
    s.advance(2)  # 1 frame for state_playing update, 1 settle
    s.advance(_GAME_OVER_FRAMES)

    # ── 7. Back to title ─────────────────────────────────────────────────────
    s.press(["START"])
    s.advance(5)
    # Full cycle complete — no exception raised means all states are stable.
