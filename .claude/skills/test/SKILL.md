---
name: test
description: Use this skill to run host-side unit tests. Triggers during TDD red/green cycles, before finishing a development branch, and when verifying logic changes. Tests compile with gcc and mock GBDK headers — no hardware required.
---

Run `timeout 30 make test`.

Use `timeout 30` every time — without it, a test binary that spins in an
infinite loop (e.g. a loader double-load assert) will never exit and `make`
will hang forever. The timeout turns a silent spin into a visible failure.

On success: report "Tests OK — N passed".

On failure: list each failing test with name, file:line, and expected vs
actual values. If compilation fails before tests run, show the gcc error
and identify which mock header or test file needs fixing.

If the command exits due to timeout (no PASS/FAIL output, exit code 124):
the test binary is spinning — likely a `while(1){}` assert triggered. Check
for double-init patterns (e.g. a test that calls `enter()` a second time
after `setUp()` already called it, without resetting shared state first).

New tests go in `tests/test_*.c` — the Makefile picks them up automatically.
Mock GBDK headers live in `tests/mocks/`.
