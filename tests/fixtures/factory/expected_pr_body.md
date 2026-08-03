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
- **Screenshots become data URIs.**
  <details><summary>Rationale</summary>

  A worktree is deleted after the run, and a file path into it stops resolving. A data URI keeps the evidence inside the page.

  </details>

## Scenario evidence

| Scenario | Result |
| --- | --- |
| reach-race | pass |

Closes #440
