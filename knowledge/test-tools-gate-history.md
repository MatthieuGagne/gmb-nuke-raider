---
summary: make test-tools rotted red for months while nothing ran it — #441 wired it to pre-commit and CI with unittest discovery (450→509 tests); a gate nobody runs is not a gate, prefer discovery over enumeration
tags: [testing, test-tools, ci, pre-commit, gates, history, lessons]
---

# The test-tools gate that nobody ran (history)

**Resolved by #441 (2026-07-26) — kept for the failure pattern, not the current
state.** The suite now runs from a `.githooks/pre-commit` repository hook on every
commit and from a matrixed `Tool Tests` CI job, and it **discovers** `tests/test_*.py`
instead of naming modules in the `Makefile`, so a new test module is gated the moment
it exists.

Before that: `make test-tools` was not wired into any hook, PostToolUse gate, or CI
job — nothing ran it except a human typing it. As of 2026-07-26 it had been red on
`master` since at least 2026-04-03, with 6 failures + 2 errors, and nobody noticed. The
hardcoded module list also hid two modules entirely (`test_dialog_editor`,
`test_check_tile_budget`) — the suite reported 450 tests where discovery finds 509.

Two of the three failure groups were **tests left behind by intentional changes**, not
bugs: `test_bank_post_build` still asserted `FAIL` after commit `43491d8` deliberately
demoted bank-at-100% to `WARN`, and `test_tmx_to_c.TestParseRacerWaypoints` still
asserted a flat-list return after `parse_racer_waypoints()` became a dict keyed by
layer index. The third was a real Windows-only defect (`tools/balancer.py` importing
POSIX-only `termios` at module scope, so the test module could not even load —
see also [[trace-py-stdlib-shadow]] for another import-time trap in `tools/`).

**Why:** a gate nobody runs stops being a gate. Because the suite was already red, each
new intentional change could leave its tests stale without anyone seeing a status
change — the failures were indistinguishable from the existing noise. This matters
more going forward: the agent factory epic (#432) leans on this suite to judge whether
generated work is sound.

**How to apply:** when a tool's behaviour is changed on purpose, update its tests in
the same commit and say so in the message. The general lesson survives the fix: a gate
nobody runs is not a gate, and an opt-in list is how things stay ungated — prefer
discovery over enumeration. The pre-commit wiring's cost implications are a live memory
(`project_precommit_hook_serializes_commits` in the memory store).
