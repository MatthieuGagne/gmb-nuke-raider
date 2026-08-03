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
- **The publisher deletes the temporary copy after each upload.**
  <details><summary>Rationale</summary>

  A second copy in the run registry costs disk for the life of the run. The upload already proves the bytes are identical.

  </details>

## Scenario evidence

| Scenario | Result |
| --- | --- |
| reach-race | pass |

Closes #440
