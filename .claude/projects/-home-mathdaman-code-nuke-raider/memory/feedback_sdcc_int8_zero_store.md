---
name: feedback_sdcc_int8_zero_store
description: Bare = 0 stores into int8_t SoA arrays need explicit (int8_t)0 cast in SDCC to avoid 16-bit store emission
metadata:
  type: feedback
---

Always cast zero stores into `int8_t` variables/arrays: use `= (int8_t)0`, not `= 0`.

**Why:** SDCC promotes the untyped `0` literal to 16-bit `int` before assignment. Without an explicit `(int8_t)` cast, the compiler may emit a 16-bit store instruction rather than an 8-bit one, producing larger code and inconsistent codegen. Found during PR #369 gb-c-optimizer review — 8 sites in racer.c zero-initializing `racer_vx[i]` and `racer_vy[i]` needed the cast.

**How to apply:** Applies to all `int8_t` SoA array zero-inits and resets (in init loops, collision reset blocks, spawn helpers). The `gb-c-optimizer` agent catches this automatically, but write it correctly the first time.
