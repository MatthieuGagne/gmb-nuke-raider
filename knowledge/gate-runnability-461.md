---
summary: a gate whose tool is missing from PATH cannot fail — romusage absent hid the bank-budget gate for months (#461); lizard, gcov and gcc have the same shape, and the fix is PATH setup in CLAUDE.local.md
tags: [gates, tooling, path, romusage, lizard, gcov, ci, lessons]
---

# A gate that cannot run never fails (#461)

`make bank-post-build` resolves `romusage` through `shutil.which`, so the tool must be **on
PATH**, not merely installed. On this machine it ships in `C:\gbdk\bin`. Without that entry the
gate exits 2 with a `FileNotFoundError` — but a shell that never runs it reports nothing at all.
**This is the exact condition that hid #461 for months:** the bank-budget gate could not run, so
it never failed, and the ROM drifted past its budget unobserved.

The same shape repeats across the hard gates:

- `gcc` (host tests) lives in a non-standard MinGW-W64 install, so nothing finds it by accident.
  Without it on PATH `make test` fails outright with `gcc: command not found` — loud, but only if
  someone runs it.
- `lizard` (CRAP score) is a Python package imported by `tools/crap_score.py`, not resolved from
  PATH; absent, that script exits 2 with a named install message. It never passes silently.
- `gcov` ships with the same MinGW-W64 install as `gcc`, so the coverage half needs no separate
  step.

**Why it stayed invisible:** `make` alone builds the ROM fine without any of these. A shell set up
to build is therefore *not* a shell set up to gate, and the difference produces no error — the
gates simply are not exercised. A green-looking session and a session with no gates at all are
indistinguishable from the outside.

**How to apply:** treat "the gate's tool is missing" as a gate **failure**, never as a skip.
Before trusting any gate result, confirm the tool resolves (`shutil.which` / `Get-Command`). The
machine-local PATH block that makes all of them runnable is in `CLAUDE.local.md` (gitignored) —
that block is the actionable half of this page. Related: [[test-tools-gate-history]], the same
lesson from the other direction (a gate nobody runs is not a gate).
