# Car Stats Design — Static Constants

**Date:** 2026-03-10
**Feature:** Add all GDD vehicle stats as constants in config.h

---

## Overview

The GDD (Section 9) defines five vehicle stats: Speed, Acceleration, Handling, Armor, Fuel. The current codebase only has Speed and Acceleration mapped to physics constants. This feature adds the remaining three stats as named constants — not yet wired to any system, but defined in the canonical location so future systems have a clear hook.

---

## Data Model

All constants live in `src/config.h`, grouped with the existing physics constants:

```c
/* Player vehicle stats — will map to upgrade tiers when upgrade system is added */
#define PLAYER_ACCEL      1   /* GDD "Acceleration" — pixels/frame added per held frame */
#define PLAYER_FRICTION   1   /* friction applied when direction released               */
#define PLAYER_MAX_SPEED  6   /* GDD "Speed"        — hard cap on velocity per axis     */
#define PLAYER_HANDLING   3   /* GDD "Handling"     — not yet active, reserved for turning system */
#define PLAYER_ARMOR      5   /* GDD "Armor"        — not yet active, damage reduction factor     */
#define PLAYER_HP        10   /* hit points         — not yet active, health pool (after armor)   */
#define PLAYER_FUEL      20   /* GDD "Fuel"         — not yet active, reserved for fuel system    */
```

Armor and HP are distinct: incoming damage is reduced by Armor before being subtracted from HP.

---

## Scope

- **In scope:** define all 5 GDD stats as constants in `config.h`
- **Out of scope:** turning system, damage/HP system, fuel depletion, upgrade purchase system

---

## Files Changed

| File | Change |
|------|--------|
| `src/config.h` | Add `PLAYER_HANDLING`, `PLAYER_ARMOR`, `PLAYER_HP`, `PLAYER_FUEL` |
