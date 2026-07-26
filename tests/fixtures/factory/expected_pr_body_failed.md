## Summary

Factory run for issue #441 — autopsy-demo.

- Attempt: 1
- Stage reached: BUILD
- Outcome: failed

## Gate results

| Stage | Gate | Result |
| --- | --- | --- |
| GATE | spec lint | pass |
| BUILD | make test | fail |

## Decisions made

- Autopsy assembly is best-effort; a missing artifact is never an error.

## FAILED

make test: tests/test_factory_run.py failed

Autopsy bundle: `.factory/runs/issue-441/autopsy/attempt-1/`

Closes #441
