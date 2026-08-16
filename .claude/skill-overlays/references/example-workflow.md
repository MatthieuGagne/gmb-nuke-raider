# Example Workflow

A worked end-to-end walkthrough of subagent-driven development, including a `(parallel)` group
dispatched one implementer at a time.

```
[Worktree gate confirmed]
[Read plan: docs/plans/feature-plan.md]
[Extract all 5 tasks with full text and context]
[Create TodoWrite with all tasks]

Task 1: Add foo module

[Record BASE: git rev-parse HEAD]
[Dispatch implementer with: brief path + report path + context]

Implementer: "Before I begin — should foo_init() take a config struct?"

You: "No config needed, just init to defaults"

Implementer: [Follows TDD; the bank-pre-write hook fires on the src/ write; writes C,
              runs tests, builds ROM; the bank-post-build and memory-check hooks fire
              post-build; commits]

[Verify the commit landed: git log --oneline -1]
[Run scripts/review-package PLAN_FILE BASE HEAD; dispatch ONE task reviewer with the printed path]
Task reviewer: Spec ✅ compliant. Task quality: Approved.

[Mark Task 1 complete]

Task 3 + Task 4: (parallel) group A — free ordering, still one at a time

[Read group table: Tasks 3 and 4 are (parallel) — different output files, so either may go first]
[Dispatch implementer for Task 3. Only Task 3.]

Implementer 3: [Implements Task 3, commits sha-abc]

[Verify the commit landed: git log --oneline -1]
[Controller dispatches gb-c-optimizer on Task 3's committed diff — C task; any edits it makes are committed before the review]
[Run review-package; dispatch ONE task reviewer for Task 3; close its fix loop]
Task reviewer 3: Spec compliant. Task quality: Approved.

[Mark Task 3 complete. ONLY NOW dispatch Task 4's implementer.]

Implementer 4: [Implements Task 4, commits sha-def]

[Verify the commit landed: git log --oneline -1]
[Run review-package from Task 4's recorded BASE; dispatch ONE task reviewer for Task 4]
Task reviewer 4: Spec compliant. Task quality: Approved.

[Mark Task 4 complete]

...

[After all tasks]
[Run review-package PLAN_FILE MERGE_BASE HEAD; dispatch final code-reviewer on the most capable model,
 with the overlay's adversarial charter appended to the dispatch]
Final reviewer: All requirements met

[Check the bank-post-build and memory-check hook output from the last build — any FAIL stops here]
[Run smoketest → user confirms]
[Use finishing-a-development-branch]
```
