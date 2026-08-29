---
summary: player waypoint detection needs a looser threshold than the racer's — RACER_WP_THRESHOLD*2 is too tight on track2
tags: [waypoint, player, racer, track2]
---

# Player waypoint tracking uses different thresholds than the racer

The racer steers toward waypoints; the player drives freely. `RACER_WP_THRESHOLD * 2 =
24px` is too tight for player waypoint detection on track2 — the player start position
(96,40) and WP0 (124,44) are 32px east of each other, so the player never comes within
24px of WP0.

**Fix:** use a ≥32px threshold for player waypoint detection, or initialize the
player's tracked waypoint to the nearest one at race start instead of relying on the
racer's tighter threshold.

Related: [[race-position-winding-track]] (the progress metric that consumes waypoint
index).
