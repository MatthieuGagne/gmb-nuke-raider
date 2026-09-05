# subagent-driven-development overlay — why each override exists

Moved out of `.claude/skill-overlays/subagent-driven-development.md` so the injected overlay
carries the imperative override text and not its justification (#527 R7 still holds: an override
earns its place only by stating what the baseline cannot know — this file is where it states it).
Section headings match the overlay's.

## The fifth stop — the batch-boundary smoketest pause

**Why:** 6.3.0's **"Rulings, not stalls"** stops the controller asking a human about conflicts,
ambiguities or plan defects, and names exactly four things that may stop a run: an irreversible
or destructive operation; a security-sensitive action; a side effect outside this worktree (a
merge, a push, a publish); a plan so broken every path forward is a guess. Read literally, that
list deletes this project's batch-boundary Emulicious pause — "a human looks at the screen" is
none of the four.

**Why it earns the exception:** the deliverable is a ROM, and its most common failure — black
screen, or ~1–2 FPS — is invisible to `make test`, to the reviewer, and to any diff. There is no
artifact the controller can rule *from*; the evidence exists only on a screen a human is
watching. That is a measurement the controller cannot take, not a decision it is deferring — so
it is not what "Rulings, not stalls" exists to prevent. The baseline cannot know the deliverable
is a ROM.

## Task-review model tier

**Why:** the baseline mandates an explicit model on every dispatch but cannot know which tier
this project wants for its own reviewer; without a declared value the review inherits the
session model, which is the failure the accepted bullet in the overlay warns about.

## Adversarial charter for the final whole-branch review

**Why:** the baseline's reviewer charter has no falsification step and asks for no evidence,
because it cannot assume the repo can produce any. This one can: `make test` is a one-command
host suite (gcc + Unity, no hardware) and `tools/smoketest_headless.py` runs a scripted ROM
headlessly for a machine-readable verdict — which makes "demonstrate it" a fair ask here. Second
thing upstream cannot know: reviewer and reviewed are the same model here, so the observed
failure mode is a confident finding nobody can reproduce (epic #531 R8, #533 R7).

## Verify subagent claims against version control

**Why:** the baseline treats the implementer's report as the record of what happened; this
project has seen reports name commits that did not exist.

## Workspace hygiene

**Why:** the baseline assumes its workspace is git-ignored; whether that is true is a fact about
*this* repo's `.gitignore`.

## Commits

**Why:** the `pre-commit` repository hook and its tool suite are this project's, and their cost
shapes how commits are batched.

## C task routing (include in every implementer brief)

**Why:** which agent owns a file type is project-specific routing the baseline cannot know.

## Who dispatches `gb-c-optimizer`

**Why:** the baseline has no notion of this agent. The overlay used to assign it to the
`gbdk-expert` implementer — impossible, and 6.3.0 now says so outright via the no-subagents
contract. Upstream has caught up with the R5 correction; the routing is still ours.

## Dispatch order

**Why:** the baseline forbids concurrent implementers and gives one reason; this project has
a second the baseline cannot know — the `pre-commit` repository hook runs the whole tool
suite on every commit, so concurrent committers on one branch collide on `index.lock` and are
serialized by the hook anyway. What this section overrides is not the concurrency ban but the
baseline's assumption that task order is fixed: this project's plans carry a
`#### Parallel Execution Groups` table computed at plan time from file-level dependency
analysis, and that table is what licenses free ordering.

## Factory mode

**Why:** the factory runs unattended, so every human-confirmation step must have a headless
replacement, and the run-level retry budget comes from the factory contract
(`.claude/skills/factory/SKILL.md`), which the baseline knows nothing about.

## Pre-PR Gate (HARD STOP)

**Why:** checks 2-4 are GB/SDCC-specific failure modes the baseline has no reason to know about.

## Example workflow

**Why:** the baseline's own example is upstream-shaped; this one shows the project's agent
routing and its dispatch-order override in one place.

## Red flags — never

**Why:** each names a project-specific trap — the worktree policy, the stale-`build/` trap, and
the brief discipline this project's plans depend on.
