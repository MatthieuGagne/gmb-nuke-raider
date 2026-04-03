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


def test_race_finish_results_screen(rom_path: str, noi_path: str) -> None:
    """STATE_PLAYING → STATE_RESULTS → STATE_OVERMAP regression.

    Boots a dedicated headless session (independent of the shared game_session
    fixture) to avoid state pollution from test_all_states.  Navigates to
    track 1 (race type, 1 lap, 50-scrap reward) via the same hub→left path
    used by test_all_states, drives south to the finish line, confirms the
    results screen is reached via WRAM (economy_get_scrap() == 50), presses A
    to continue, and confirms the overmap is reached without error.

    Frame-count derivation:
      Title boot + overmap entry: 60 + 1 + 10 frames.
      Hub visit (UP nav + dwell + START): _HUB_NAV_FRAMES + 10 + 1 + 10.
      Dest nav (LEFT): _PLAYING_NAV_FRAMES + _PLAYING_DWELL_FRAMES.
      Driving south to finish line:
        track1 start_y=8 (px), finish_line_y=95 (tile) → py target ≥ 756 px.
        Distance: 756 − 8 = 748 px.  Gear-3 max speed = 6 px/frame.
        Acceleration phase: ~6 frames.  Cruise: 748/6 ≈ 125 frames.
        Empirical: py=718 at frame 200, finish at py=756 (38 px short).
        Total: ~131 frames + 99-frame safety buffer = 230 frames held.
    """
    with GameSession.boot(rom_path, headless=True) as s:
        # ── 1. Title screen ──────────────────────────────────────────────────
        s.advance(_TITLE_BOOT_FRAMES)

        # ── 2. Enter overmap ──────────────────────────────────────────────────
        s.press(["START"])
        s.advance(_OVERMAP_SETTLE)

        # ── 3. Hub visit — sets car spawn via state_pop() re-entry ────────────
        # Navigate UP to CITY_HUB, dwell, then START to pop back to overmap.
        # On re-entry overmap.enter() sets car_tx/ty = hub spawn (9,8).
        s.press(["UP"])
        s.advance(_HUB_NAV_FRAMES)
        s.advance(_HUB_DWELL_FRAMES)
        s.press(["START"])
        s.advance(_OVERMAP_SETTLE)

        # ── 4. Navigate LEFT to track 1 race destination ──────────────────────
        # From (9,8): LEFT → DEST at (2,8).  state_replace(&state_playing).
        s.press(["LEFT"])
        s.advance(_PLAYING_NAV_FRAMES)
        s.advance(_PLAYING_DWELL_FRAMES)

        # ── 5. Drive south to the finish line ────────────────────────────────
        # Hold DOWN 230 frames — enough to reach tile row 95 (TILE_FINISH).
        # finish_eval() fires: economy_add_scrap(50) → state_replace(&state_results).
        # Empirical: py=718 at frame 200; finish at py=756 (~7 more frames needed).
        s.press(["DOWN"], hold_frames=230)

        # ── 6. Verify results screen via WRAM ────────────────────────────────
        # economy_get_scrap() reads the static `player_scrap` WRAM variable.
        # find_wram_read_in_fn locates it by disassembling the getter; the
        # helper now handles both LD A,(nn) (8-bit) and LD HL,nn (16-bit) vars.
        scrap_addr = find_wram_read_in_fn(noi_path, rom_path, "_economy_get_scrap")
        scrap_val  = s.read_wram(scrap_addr) | (s.read_wram(scrap_addr + 1) << 8)
        assert scrap_val == 50, (
            f"Expected scrap == 50 (TRACK1_REWARD) after crossing finish line, "
            f"got {scrap_val}.  Finish line may not have been reached — "
            f"check frame count or finish_line_y offset."
        )

        # ── 7. Press A to dismiss results → state_replace(&state_overmap) ────
        # Advance 2 frames first so KEY_TICKED(J_A) latches cleanly.
        s.advance(2)
        s.press(["A"])
        s.advance(_OVERMAP_SETTLE)
        # No PyBoy exception means overmap was reached successfully.


def test_direct_left_race(rom_path: str, noi_path: str) -> None:
    """Regression guard: STATE_OVERMAP → STATE_PLAYING via direct LEFT — issue #275.

    Verifies that pressing LEFT from the overmap hub (9,8) reaches the race
    destination (2,8) and enters state_playing without stalling.

    Root cause (fixed): state_manager stored raw pointers into banked ROM;
    dereferencing without bank-switching yielded garbage fn ptrs → grey screen.
    Fix: load_entry() caches {bank, enter, update, exit} in WRAM at push/replace.

    Navigation: spawn(9,8) → DEST(2,8) = 7 tiles LEFT.
    Frame budget: 7 * 4 + 5 = 33 frames (same as _PLAYING_NAV_FRAMES).
    """
    _LCDC_ADDR = 0xFF40
    _LCDC_DISPLAY_ON = 0x80

    with GameSession.boot(rom_path, headless=True) as s:
        # ── 1. Title screen ──────────────────────────────────────────────────
        s.advance(_TITLE_BOOT_FRAMES)

        # ── 2. Enter overmap ──────────────────────────────────────────────────
        s.press(["START"])
        s.advance(_OVERMAP_SETTLE)
        # Car is at hub spawn (9, 8). No hub visit.

        # ── 3. Navigate LEFT directly to DEST (2, 8) ─────────────────────────
        s.press(["LEFT"])
        s.advance(_PLAYING_NAV_FRAMES)   # 7 tiles × 4 frames/tile + 5 settle
        s.advance(_PLAYING_DWELL_FRAMES)

        # ── 4. Assert display is on ───────────────────────────────────────────
        # If state_playing.enter() stalled (grey screen), LCDC bit 7 stays 0.
        # If it completed normally, DISPLAY_ON set bit 7 to 1.
        lcdc = s._pyboy.memory[_LCDC_ADDR]
        assert lcdc & _LCDC_DISPLAY_ON, (
            f"Display is OFF after direct-left navigation (LCDC=0x{lcdc:02X}). "
            f"state_playing.enter() stalled between DISPLAY_OFF and DISPLAY_ON. "
            f"See issue #275."
        )
