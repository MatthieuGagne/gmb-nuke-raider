---
name: gb-memory-validator
description: Validates WRAM, VRAM, and OAM budgets after a successful build. ROM bank budget is checked by the bank-post-build skill. Reports PASS/WARN/FAIL — no auto-fix.
color: green
---

> **Deprecated:** This agent has been replaced by `tools/memory_check.py`.
> Invoke the `gb-memory-validator` **skill** instead, which runs `make memory-check`.

If invoked directly, run:

```bash
make memory-check
```

from the repo root (or worktree directory) and report the output verbatim.
Do not edit any source files. Report only.
