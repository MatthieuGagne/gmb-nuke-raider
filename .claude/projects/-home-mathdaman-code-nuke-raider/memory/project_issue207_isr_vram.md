---
name: Issue #207 resolution
description: Issue #207 music degradation — root cause found, issue closed, no code change needed
type: project
---

Issue #207 (music degrades to clicks ~30s) is **CLOSED**. Root cause was `order_cnt` semantics.

**Root cause:** `order_cnt` is a byte count (not entry count). hUGEDriver increments `current_order` by 2 per pattern (2-byte pointers). Correct value for 34 entries = 68. With `order_cnt = 34` only 17 of 34 patterns played before abrupt loop → click artifacts.

**Resolution:** Master already has `order_cnt = 68` (correct). Three emulator runs confirmed zero degradation past 2 minutes.

**Why:** Confirmed by hUGEDriver rgbds_example (`order_cnt: db 68` for 34 entries) and GBDK example.

**How to apply:** Do NOT merge branch `fix/issue-207-music-degradation` — commit `6040261` re-introduces the bug by changing 68 → 34. Also do not merge `worktree-fix-music-order-cnt` branch for the same reason.
