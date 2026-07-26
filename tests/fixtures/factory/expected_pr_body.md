## Summary

Factory run for issue #440 — observability.

- Attempt: 1
- Stage reached: SHIP
- Outcome: shipped

## Gate results

| Stage | Gate | Result |
| --- | --- | --- |
| GATE | spec lint | pass |
| PLAN | plan self-review | pass |
| BUILD | make test-tools | pass |
| SHIP | smoketest confirmed | pass |

## Decisions made

- Journal is the source of truth; state.json is a projection.
- Screenshots are embedded as data URIs so the page survives worktree deletion.

## Scenario evidence

| Scenario | Result |
| --- | --- |
| reach-race | pass |

Closes #440
