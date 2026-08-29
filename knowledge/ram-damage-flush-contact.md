---
summary: a strict AABB overlap test misses "from behind" ram damage against a solid enemy — enemy_ram_overlap() inflates the box by a reach margin
tags: [damage, ram, collision, aabb, racer, patrol, enemy_common]
---

# Ram damage vs a solid enemy — strict AABB silently misses "from behind"

Racers are solid to the player (`corner_active_racer` in `player.c`'s
`corners_passable`), so the player is blocked *flush* against the racer's bumper: the
boxes only touch (`px+16 == racer_px`), and a strict overlap test (`px+16 >
racer_px`) is **false** — no ram registers when chasing from behind. Head-on/side hits
work only because closing velocity interpenetrates for a frame.

**Fix:** detect contact with a small reach margin, not strict overlap.
`enemy_ram_overlap()` in `enemy_common.c` inflates the enemy box by
`ENEMY_RAM_REACH` (2px) on every side so flush contact rams from any direction. Both
`racer.c` and `patrol.c` MUST use that shared helper — identical collision logic, no
per-module reimplementation.

Any new player↔enemy contact-damage feature has the same trap (#417).

Related: [[enemy-damage-pipeline]] (the damage flow this feeds into).
