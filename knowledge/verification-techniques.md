---
summary: Prove-it-bites verification techniques — gcc -Wconversion pre-SDCC truncation audit, neuter-the-function red/green diff, flip-header-on-disk constant-drift test, bytearray mutation for parity tests
tags: [verification, testing, prove-it-bites, gcc, wconversion, audit, technique]
---

# Verification techniques ("prove it bites")

Concrete techniques used in this repo to prove that a check, test, or gate can actually
fail. Instances live throughout: [[beam-trail-repair]] (neutered function),
[[rom-parity-testing]] (bytearray mutation), [[config-h-patterns]] (range-guard flip
test).

## gcc warning pass as a cheap pre-SDCC truncation audit

`gcc -Wconversion -Wsign-conversion -Wshadow -Wcast-qual` on a single `src/*.c` is a
cheap pre-SDCC truncation audit. The mock headers make it compile standalone; a clean
run is strong evidence that no implicit narrowing (the `(uint8_t)(n << 3u)` class of
bug — see [[beam-laser-module]]) is hiding in new integer arithmetic. The only expected
warning is `#pragma bank` under `-Wunknown-pragmas`.

## Temporarily neuter the function under test (red → restore → green)

For a repair/repaint-class feature where a wrong assertion could pass against a no-op:
comment out the call to the function under test, re-run the suite, confirm the new
tests FAIL with values that prove they read the un-repaired state, restore the line,
confirm green. Concrete instance: `beam_repair_leaving()` in [[beam-trail-repair]]
(both new hi_n tests failed `Expected 1 Was 64`/`65` with the call commented out).
Deletion-testing a single load-bearing line works the same way (the
`s_cast_memo_ok = 0u;` reset — removing it fails exactly one test).

## Flip the real source header on disk (#590 final review item 1)

Proving a hand-written Python constant-drift test can actually fail: flip the real
source header on disk, run the test, then restore from a backup — don't mock or
monkeypatch the parser. `tools/debug_protocol.py`'s `_CACHE` dict caches `_read()`
results per-process, so a single Python process can safely mutate
`src/debug.h`/`src/config.h` on disk, re-run `python -m unittest discover` as a
**fresh subprocess** (avoids the cache), and see the real failure — then `shutil.copy`
the backup back. Do this once per new constant with `subprocess.run` in a throwaway
script (not a permanent test), confirm the assertion message names the flipped values
(e.g. `AssertionError: 7 != 8`), and confirm `git status --porcelain` shows no diff on
the header afterward. This is the concrete technique behind "prove it bites" for any
test whose only job is comparing two parsed values that agree today by construction.
The compile-time variant (flip a guarded constant and check the `#error` fires) is in
[[config-h-patterns]].

## Mutate in-memory copies, never the real artifact

For byte-level ROM tests: mutate in-memory `bytearray` copies of a real bank (never the
real `.gb` file) — flip a byte in an agreeing run, fabricate a conflicting relocation
tuple — and confirm a control run against the unmutated bytes shows zero findings
first. Details in [[rom-parity-testing]].
