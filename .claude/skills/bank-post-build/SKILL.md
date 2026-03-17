---
name: bank-post-build
description: Hard gate — invoke after a successful build, before smoketest. Validates .map symbol placements against manifest and checks ROM bank budgets.
---

# Bank Post-Build Gate

Run after `GBDK_HOME=/home/mathdaman/gbdk make` succeeds. Block proceeding to smoketest if any check fails.

## Step 1 — Run romusage

```sh
/home/mathdaman/gbdk/bin/romusage build/nuke-raider.gb -a
```

### Budget thresholds

| Bank | WARN | FAIL |
|------|------|------|
| Bank 1 | >90% | >100% |
| All others | >80% | >100% |

If any bank FAILs → **BLOCK.** Tell user:
> "Bank N is full. Fix: bump `-Wm-ya` to the next power of 2 in the Makefile (e.g. `-Wm-ya16` → `-Wm-ya32`)."

If bank 1 WARNs (>90%) → flag prominently:
> "Bank 1 is at X% — state code is at risk of overflowing. Consider bumping `-Wm-ya` now."

## Step 2 — Check state code stays in bank 1

```sh
grep "_state_" build/nuke-raider.map | grep -v "^;" | grep -v " 014[0-9A-Fa-f]\{3\} "
```

Symbols matching `_state_*` that appear at addresses **outside** `0x14000–0x17FFF` (bank 1 range) indicate overflow.

If any `_state_` symbol appears at `0x024xxx` or higher → **BLOCK:**
> "State code overflowed bank 1 — blank screen crash at boot guaranteed. Bump `-Wm-ya` to next power of 2."

## Step 3 — Verify `__bank_` symbols match manifest

```sh
grep "__bank_" build/nuke-raider.map | grep -v "^;"
```

For each `__bank_<symbol>` entry, the numeric value should match the manifest's bank for the file containing that symbol.

If a `__bank_` value is wrong → flag to user. Common cause: BANKREF placed in a different file than the data it references (was the root cause of PR #107).

## Step 4 — Check `-Wm-ya` declares enough banks

```sh
grep "\-Wm-ya" Makefile
/home/mathdaman/gbdk/bin/romusage build/nuke-raider.gb -a | grep "ROM Bank"
```

The highest bank number in use must be < the value declared with `-Wm-ya`. If banks are present beyond the declared count → **BLOCK.**

## Output format

```
=== Bank Post-Build Report ===
Bank 0: X / 16384 bytes (Y%)  [PASS/WARN/FAIL]
Bank 1: X / 16384 bytes (Y%)  [PASS/WARN/FAIL]
...
State symbols: [OK — all in bank 1] or [FAIL — N symbols outside bank 1]
__bank_ symbols: [OK] or [FAIL — list mismatches]
-Wm-ya capacity: [OK — Ya banks declared, M highest in use] or [FAIL]

[PASS / WARN / FAIL — overall]
```

If all checks pass: "bank-post-build: all checks passed — safe to proceed to smoketest."
