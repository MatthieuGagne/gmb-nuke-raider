# PRD: Oval Track with Boundary Collision

**Status:** In Progress
**Issue:** #2

---

## Goal

Add a static oval racing track rendered as a BG tile map, preventing the player from driving off the track.

---

## Requirements

- R1: The track is a static oval ring occupying most of the 160×144 screen, rendered using BG tiles.
- R2: Two tile types are used: off-track (dark, wasteland) and track surface (lighter, road).
- R3: The player sprite cannot move onto off-track tiles — movement is blocked at the track boundary.
- R4: Collision is checked per-axis independently so the player can slide along track edges.
- R5: The player starts on the track at game start.

---

## Acceptance Criteria

- [ ] AC1: Title screen renders correctly (no tile corruption from track data).
- [ ] AC2: Pressing START shows the oval track on screen.
- [ ] AC3: Player sprite starts positioned on the track.
- [ ] AC4: Player cannot exit the track in any direction.
- [ ] AC5: Player slides along track edges (not stuck at corners when pushing diagonally into a wall).
- [ ] AC6: All unit tests pass (`make test`).

---

## Out of Scope

- Scrolling or multi-screen tracks.
- Multiple track layouts or track selection.
- Track decorations (curbs, markings, scenery).
- Lap counting or checkpoints.

---

## Files Impacted

- `src/track.c` — new: tile data, map array, `track_init()`, `track_passable()`
- `src/track.h` — new: public API
- `src/player.c` — update: collision checks in `player_update()`, new start position
- `src/main.c` — update: call `track_init()` on transition to STATE_PLAYING
- `tests/test_track.c` — new: unit tests for `track_passable()`
- `tests/test_player.c` — update: collision tests, updated position expectations
- `tests/mocks/gb/gb.h` — update: add BG tile mock stubs

---

## Notes

- Design doc: `docs/plans/2026-03-09-track-collision-design.md`
- Implementation plan: `docs/plans/2026-03-09-track-collision.md`
- Font conflict: GBDK default font occupies BG tile IDs 0–95. `track_init()` is called on transition to STATE_PLAYING (not during DISPLAY_OFF init) to avoid overwriting the font used by the title screen.
- Track tile IDs 0 (off-track) and 1 (track) are safe to use once the title screen is dismissed.
