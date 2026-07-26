# Example Workflow

A worked end-to-end walkthrough of subagent-driven development, including a parallel batch.

```
[Worktree gate confirmed]
[Read plan: docs/plans/feature-plan.md]
[Extract all 5 tasks with full text and context]
[Create TodoWrite with all tasks]

Task 1: Add foo module

[Dispatch implementer with: task text + context + GB gate instructions]

Implementer: "Before I begin — should foo_init() take a config struct?"

You: "No config needed, just init to defaults"

Implementer: [Follows TDD, invokes bank-pre-write, gbdk-expert, writes C, runs tests,
              builds ROM, invokes bank-post-build, commits]

[Dispatch spec reviewer]
Spec reviewer: ✅ Spec compliant

[Dispatch code quality reviewer]
Code reviewer: ✅ Approved

[Mark Task 1 complete]

Task 3 + Task 4: Parallel batch (Group A in Parallel Execution Groups table)

[Read group table: Tasks 3 and 4 are (parallel) — different output files]
[Dispatch implementer for Task 3 AND implementer for Task 4 in a single message]

Implementer 3: [Implements Task 3, commits sha-abc]
Implementer 4: [Implements Task 4, commits sha-def]

[Dispatch spec reviewer + code quality reviewer in parallel for the batch]
Spec reviewer: ✅ Both tasks spec compliant
Code reviewer: ✅ Both approved

[Mark Task 3 complete, Task 4 complete]

...

[After all tasks]
[Dispatch final code-reviewer]
Final reviewer: All requirements met

[Run bank-post-build + gb-memory-validator]
[Run smoketest → user confirms]
[Use finishing-a-development-branch]
```
