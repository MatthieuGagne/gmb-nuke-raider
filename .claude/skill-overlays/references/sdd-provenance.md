# subagent-driven-development overlay — provenance

Why the overlay's harder rules exist, kept out of the injected body because it is history, not
instruction. Read it when a rule looks arbitrary or you are tempted to relax one.

## Why concurrency lost (`### Dispatch order`)

The overlay used to tell the controller to dispatch every task in a `(parallel)` group as
concurrent implementers — four lines above "never parallelize tasks that share git state". Every
task in this project commits, so both rules bound every group and the section contradicted
itself. Runs **#430** and **#590** each hit the contradiction and each resolved it the same way:
keep the plan-time file-level analysis, drop the concurrency.

The mechanism is why it was never a loss. Concurrent committers on one branch collide on
`index.lock`, and the `pre-commit` hook runs the whole tool suite on every commit and serializes
them anyway. The concurrency was never buying wall-clock time it could keep.

## Why a task's review must close first (`### Dispatch order`)

The reviewer builds and runs tests in the same working tree. Dispatch the next implementer before
the review closes and the tree holds another task's uncommitted work while the reviewer builds —
so the reviewer verifies code it was not asked to review, and nothing in its report says so.

In run **#590** the Task 3 reviewer found 403 lines of uncommitted Task 4 work and isolated
itself in a detached checkout before building. It was right, and it was working around the
controller.

## Why the controller dispatches `gb-c-optimizer` (R5)

The overlay used to assign the gate to the `gbdk-expert` implementer. That assignment could never
be carried out: the implementer dispatch forbids dispatching subagents, and `gb-c-optimizer` is
an agent. superpowers@6.3.0 later made the same contract explicit upstream ("the implementer
never dispatches subagents — not helpers, and never a reviewer") and added a red flag treating a
worker-spawned reviewer as a defect.

In run **#590** the implementer, unable to dispatch the agent, applied that agent's checklist to
its own work by hand. The controller dispatched the real gate afterwards; it reproduced the
self-check's findings and named one hazard the self-check had missed. A self-applied checklist is
not this gate.

## Why rulings make the plan stale (`### Factory mode`)

Task briefs are extracted from the plan once, at dispatch time. A ruling that amends a fact a
later task's brief states never reaches that task unless the plan file itself changes.

In run **#590** three implementers corrected the controller about facts their briefs stated and
later rulings had already falsified — the controller was handing out text it had itself ruled
false. superpowers@6.3.0 makes this sharper, not softer: rulings are the normal path now, so the
plan goes stale faster than it did when conflicts were escalated to a human.
