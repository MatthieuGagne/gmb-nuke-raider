## Goal
Add a laser overheat meter so sustained fire punishes the player.

## Requirements
- R1: The laser gains a heat value that rises while firing and falls while idle.
- R2: At max heat the laser is disabled until it cools below a threshold.

## Acceptance Criteria
- [ ] AC1: Holding fire for 2 seconds disables the laser.
- [ ] AC2: The laser re-enables after ~1 second of no fire.

## Out of Scope
- Visual overheat warning HUD (separate PRD).

## Files Impacted
- `src/laser.c` — heat accumulation + disable logic
- `src/laser.h` — heat state fields

## Notes
- WRAM: +2 bytes for heat state. No new banks.
