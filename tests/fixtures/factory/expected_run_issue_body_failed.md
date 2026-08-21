**Spec** #441 · **Branch** `worktree-autopsy-441` · **Attempt** 1 · **Updated** 2026-07-26T12:05:00+00:00

✅ GATE → ✅ PLAN → ❌ BUILD → ⬜ VERIFY → ⬜ SHIP

### Failure

- **Stage** BUILD
- **Reason** make test: tests/test_factory_run.py failed
- **Worktree** `wt-441`

no stage log captured

### Gate results

| Stage | Gate | Result |
|---|---|---|
| GATE | spec lint | pass |
| BUILD | make test | fail |

### Decisions made

- Autopsy assembly is best-effort; a missing artifact is never an error.

### Stage logs

No log was captured for: GATE, BUILD. Those commands ran outside `tools/factory_log.py`, so their output is not recoverable.

_No stage logs published yet._

<!-- factory-publish v1 — regenerated on every publish; manual edits are overwritten -->
