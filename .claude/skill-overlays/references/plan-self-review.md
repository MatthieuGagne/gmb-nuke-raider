# Plan Self-Review Checklist (HARD STOP before presenting to user)

Extracted from the `writing-plans` overlay. Run all seven checks before offering the execution
handoff. Fix any failures first.

This **extends** the baseline's three-point self-review (spec coverage, placeholder scan, type
consistency) rather than replacing it — checks #1, #3, #4 and #6 are project-specific (magic
numbers vs `config.h`, the parallel annotations, the group tables, `trace.py`). Run the
baseline's three as well; they are not repeated here.

| # | Check | Pass criteria |
|---|-------|---------------|
| 1 | **No hardcoded values** | Every numeric constant, tile index, capacity, or coordinate is sourced from `config.h`, a Tiled export, or an explicit named constant — never a magic number |
| 2 | **All tasks have explicit test criteria** | Every task states exactly how to verify it passes (command + expected output, or visual check description) |
| 3 | **Parallel annotations justified** | Every task has `**Depends on:**` and `**Parallelizable with:**` filled in. Any `**Parallelizable with:** none` MUST be followed by a one-sentence justification (e.g. "writes same file as Task M"). An unjustified `none` is a plan defect. |
| 4 | **Parallel Execution Groups tables present** | Every batch that precedes a Smoketest Checkpoint has a `#### Parallel Execution Groups` table |
| 5 | **No implementation details leaked from brainstorming** | Plan contains file paths and task steps, not design narrative or requirement rationale (those belong in the GitHub issue) |
| 6 | **Issue header + filename** | The plan has an `**Issue:** #N` line matching the `issue<N>` in its filename. Verify with `python tools/trace.py --check --plans-only` — expect `PASS` and no `ERROR` lines mentioning this plan |
| 7 | **Landed-test impact named** | Every task that changes behaviour an already-landed test asserts names that test by path and says how the task handles it — update the test, or state why it still passes. A task that breaks a landed test without saying so is a **plan defect**, not a build-stage surprise. |

## Failure handling

- Checks #1, #2, #4, #5, #7 fail → fix the plan now and re-run the checklist from the top.
- Check #6 fails → fix the header and/or rename the file now, then re-run
  `python tools/trace.py --check --plans-only`.
- Check #3 fails (unjustified `none`) → do NOT silently fix. Present the plan WITH the Incomplete
  Warning block from `plan-structure.md`, immediately after the plan header. The user decides
  whether to proceed or fix first.
  **In factory mode this inverts:** there is no user to present to, so the annotation is fixed in
  place and the fix logged as a decision event.

## Why #7 exists

The `pre-commit` repository hook runs the whole tool suite on every commit and `--no-verify` is
forbidden, so every already-landed test is a hard gate on every task in the plan. Three of run
#590's four escalations were the same shape: `tests/test_rom_parity.py` refused a commit at
Tasks 2, 3 and 4, and each time the plan had not said the task would break it. A plan that
leaves this to BUILD converts a five-minute plan-time edit into a mid-run ruling.
