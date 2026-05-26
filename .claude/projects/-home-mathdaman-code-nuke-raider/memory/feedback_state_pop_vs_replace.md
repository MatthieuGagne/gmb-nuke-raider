---
name: feedback_state_pop_vs_replace
description: state_pop() vs state_replace() rule — using state_replace to go back silently corrupts stack depth and breaks subsequent state_push
metadata:
  type: feedback
---

Use `state_pop()` to navigate back, NOT `state_replace()`.

**Why:** `state_replace` never reduces stack depth. If stack is at depth=2 and you `state_replace` to go "back," depth stays 2. The next `state_push` silently fails (STACK_MAX=2 in state_manager.c). Discovered when `state_game_over` used `state_replace(&state_title)` — after game over the stack was [overmap, game_over]; replace left it [overmap, title]; then overmap's `state_push(&state_prerace)` silently no-op'd; race never started.

**How to apply:**
- `state_push` — go deeper (overmap → prerace)
- `state_pop` — go back (game_over → overmap, results → overmap)
- `state_replace` — lateral only, same depth (prerace → playing, playing → game_over, playing → results)
- Never use `state_replace` when the intent is "I'm done, return to caller"
