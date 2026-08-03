**Spec** #440 · **Branch** `worktree-obs-440` · **Attempt** 1 · **Updated** 2026-07-26T12:13:00+00:00

✅ GATE → ✅ PLAN → ✅ BUILD → ✅ VERIFY → ✅ SHIP

### Gate results

| Stage | Gate | Result |
|---|---|---|
| GATE | spec lint | pass |
| PLAN | plan self-review | pass |
| BUILD | make test-tools | pass |
| SHIP | smoketest confirmed | pass |

### Decisions made

- Journal is the source of truth; state.json is a projection.
- **Screenshots become data URIs.**
  <details><summary>Rationale</summary>

  A worktree is deleted after the run, and a file path into it stops resolving. A data URI keeps the evidence inside the page.

  </details>
- **The publisher deletes the temporary copy after each upload.**
  <details><summary>Rationale</summary>

  A second copy in the run registry costs disk for the life of the run. The upload already proves the bytes are identical.

  </details>

### Scenario evidence

| Scenario | Blocking | Result |
|---|---|---|
| reach-race | - | pass |

### Stage logs

| Stage | Attempt | Log |
|---|---|---|
| BUILD | 1 | [issue-440-attempt-1-BUILD.log](https://github.com/MatthieuGagne/gmb-nuke-raider/releases/download/factory-logs/issue-440-attempt-1-BUILD.log) |

<!-- factory-publish v1 — regenerated on every publish; manual edits are overwritten -->
