# Nuke Raider — Feature Roadmap

_Last updated: 2026-03-31. Derived from grill-me session on core loop, combat, mission variety, and save system._

---

## Priority Order

### Tier 1 — Core Loop Closure

| # | Feature | Notes |
|---|---------|-------|
| 1 | **Race/combat map types** (Issue #256) | Foundation for all mission variety. `TRACK_TYPE_RACE` and `TRACK_TYPE_COMBAT` declared in TMX, consumed by `track.c` and `hud.c`. Ships first — all mission types build on this. |
| 2 | **SRAM save system** (`player_save.c`) | Scrap balance + upgrade levels survive power-off. Makefile: `-Wm-yt1b -Wm-ya1` (MBC5+RAM+BATTERY). Serialization/checksum testable host-side; SRAM I/O behind `#ifdef __SDCC`. |
| 3 | **Vehicle upgrade system** | Spend scrap at hub to increase speed, armor, max HP. Reads/writes `player_save.c` struct. |

### Tier 2 — Combat Differentiation

| # | Feature | Notes |
|---|---------|-------|
| 4 | **Moving enemies** | Shared `enemy.c` SoA pool (`MAX_ENEMIES=8`). Add `enemy_vx[]`, `enemy_vy[]`, `enemy_state[]`. Two types: 16×16 chaser (rival car, VRAM tiles 20–23) and 8×8 scout (motorbike, tile 24). Behavior: chase when in range (Manhattan distance), random patrol direction on wall collision. |
| 5 | **Delivery mission type** (`TRACK_TYPE_DELIVERY`) | Player carries cargo to destination. Cargo drops at current map position when HP falls below 50%. Player retrieves by driving over it. 1 OAM slot for dropped cargo sprite. Mission restarts on death. |
| 6 | **Survival mission type** (`TRACK_TYPE_SURVIVAL`) | Stay alive for N seconds. Countdown timer on HUD. Separate map type (not a combat map with a flag). Mission restarts on death. |

### Tier 3 — Story Hook

| # | Feature | Notes |
|---|---------|-------|
| 7 | **Act 1 missions wired to dialog** | Tutorial checkpoint run + convoy combat encounter. Vale dialog milestones trigger on mission completion. Gating rule (complete both vs. each independently) TBD. |
| 8 | **Faction briefing screens** | Context screen before entering a mission (faction, objective, reward). |

### Tier 4 — Polish

| # | Feature | Notes |
|---|---------|-------|
| 9 | **HUD improvements** | Scrap counter, HP bar, gear indicator. Layout TBD (HUD strip only vs. always-visible). Resolve before implementing — OAM headroom is only 2 slots. |
| 10 | **Track 3 (Act 3 finale map)** | Boss/climax map for Old World Corp facility assault. |
| 11 | **Title/intro sequence** | Opening crawl, Vale reveal moment. |

---

## Architectural Decisions

### Save System
- New module: `src/player_save.c` / `src/player_save.h`
- Struct fields: `scrap` (uint16_t), `speed_level`, `armor_level`, `max_hp` (uint8_t each)
- Checksum validation on load; corrupt save → reset to defaults
- Must add `player_save.c` to `bank-manifest.json` before writing

### Moving Enemies
- Extend existing `enemy.c` SoA arrays — do NOT create a separate module
- New arrays: `enemy_vx[MAX_ENEMIES]`, `enemy_vy[MAX_ENEMIES]`, `enemy_state[MAX_ENEMIES]`
- `enemy_state` values: `ENEMY_STATE_PATROL`, `ENEMY_STATE_CHASE`
- Distance check: Manhattan distance (`|dx| + |dy|`) — no sqrt
- Renderer uses `enemy_type` to determine 8×8 vs 16×16 OAM slot count

### Map Types
- 4 total: `TRACK_TYPE_RACE` (0), `TRACK_TYPE_COMBAT` (1), `TRACK_TYPE_DELIVERY` (2), `TRACK_TYPE_SURVIVAL` (3)
- Declared as TMX custom property `map_type`, emitted by `tmx_to_c.py`
- Issue #256 implements types 0 and 1; types 2 and 3 extend that infrastructure

### Delivery Cargo
- Cargo state: position `(cargo_x, cargo_y)` + `cargo_active` flag in `state_playing.c`
- Drop trigger: `damage_get_hp() < PLAYER_MAX_HP / 2`
- Pickup trigger: player position within hit radius of cargo position
- 1 OAM slot reserved for cargo sprite when on ground

---

## OAM Budget

| Entity | Slots | Notes |
|--------|-------|-------|
| Player | 4 | 16×16 (2×2 grid) |
| Dialog arrow | 1 | Fixed slot 4 |
| Projectiles | 8 | MAX_PROJECTILES=8 |
| Enemies (worst case 16×16) | 16 | MAX_ENEMIES=8 × 2 slots |
| Dropped cargo | 1 | Only active during delivery missions |
| **Total** | **30 / 40** | 10 slots remaining for HUD |

_Note: Turrets are 8×8 (1 slot each). Worst case above assumes all 8 enemy slots are 16×16 chasers._

---

## Open Questions

| Question | Status |
|----------|--------|
| Act 1 mission gating: complete both to unlock Act 2, or each independently? | TBD |
| HUD layout: scrap/HP/gear in HUD strip only, or always-visible above play area? | TBD |

---

## Risk Areas

- **OAM headroom:** 10 slots remain after full enemy worst-case. HUD layout decision must happen before HUD implementation — any sprite-based HUD element draws from this pool.
- **Bank manifest:** `player_save.c` needs a `bank-manifest.json` entry before the file is written. Makefile SRAM flag (`-Wm-yt1b`) must match the physical cartridge — mismatch silently disables SRAM on real hardware.
- **VRAM tile slots 20–24:** Assumed free for moving enemy sprites. Verify no other asset occupies these before implementing.
- **Cargo OAM slot:** Must be allocated from sprite pool, not hardcoded — pool is at 30/40 worst case.
