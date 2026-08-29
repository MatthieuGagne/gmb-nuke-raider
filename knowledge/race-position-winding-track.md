---
summary: raw Y coordinate is not a valid "who is ahead" metric on a winding track — section-aware comparison and waypoint progress scores
tags: [race-position, track2, waypoint, racer, player]
---

# Race position on a winding track

Track2 is an oval: down the right side (`ty` increases), up the left side (`ty`
decreases). Two competitors at the same Y value can be at completely different
positions on the track — a naive Y-coordinate comparison flips randomly depending on
which side each one is on.

**Use section-aware comparison:**
- Detect side: `player_tx > 10` = right side; `racer_wp_idx < 6` = right side
- Right side (going down): higher `ty` = further ahead
- Left side (going up): lower `ty` = further ahead
- Different sides: the competitor on the left side is further along
- General rule: use waypoint progress scores (`laps × wp_count + wp_idx`), not raw
  pixel coordinates.

Related: [[verification-techniques]] documents the #390 Track-2 lap-counting case that
motivated verifying position logic against a real differential run rather than static
inspection.
