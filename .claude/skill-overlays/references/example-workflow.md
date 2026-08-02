# Example Workflow

A worked end-to-end walkthrough of subagent-driven development, including a parallel batch.

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

Task 3 + Task 4: Parallel batch (Group A in Parallel Execution Groups table)

[Read group table: Tasks 3 and 4 are (parallel) — different output files]
[Dispatch implementer for Task 3 AND implementer for Task 4 in a single message]

Implementer 3: [Implements Task 3, commits sha-abc]
Implementer 4: [Implements Task 4, commits sha-def]

[Verify both commits landed: git log --oneline -2]
[One review package per task, from each task's recorded BASE; one task reviewer per task]
Task reviewer 3: Spec ✅ compliant. Task quality: Approved.
Task reviewer 4: Spec ✅ compliant. Task quality: Approved.

[Mark Task 3 complete, Task 4 complete]

...

[After all tasks]
[Run review-package PLAN_FILE MERGE_BASE HEAD; dispatch final code-reviewer on the most capable model]
Final reviewer: All requirements met

[Check the bank-post-build and memory-check hook output from the last build — any FAIL stops here]
[Run smoketest → user confirms]
[Use finishing-a-development-branch]
```
