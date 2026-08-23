---
name: writing-plans
baseline: superpowers@6.3.0
---

Project (Nuke Raider) additions and overrides for the baseline writing-plans skill. On conflict,
this overlay wins — but an override earns that only by stating what the baseline cannot know
(#527 R7).

**Baseline audit:** content of `superpowers@6.3.0` read and compared on 2026-08-22 (#527 R6).
6.3.0's only change here: a `**Spec:**` field added to the plan header. See
`references/plan-structure.md` — `**Issue:** #N` fills that role in this project.

## Overrides (do NOT follow the baseline here)

- **Save plans to `docs/plans/YYYY-MM-DD-issue<N>-<slug>.md`** — NOT `docs/superpowers/plans/`
  or any other baseline location, and NOT the issue-less `YYYY-MM-DD-<feature-name>.md` form.
  `<N>` is the GitHub issue number the plan implements; `<slug>` is lowercase, hyphen-separated
  (e.g. `docs/plans/2026-07-26-issue435-traceability.md`).
  **Why:** the baseline's own line says user preferences override the default location, and
  `tools/trace.py --check` parses this exact filename to link a plan to its spec issue.

## Project additions

### Before you begin

**Why:** the baseline assumes a worktree already exists and names no sync step; a stale branch
is this repo's most common plan-time defect, and `grill-with-docs` is a local skill.

- **First action, before anything else:** pull and merge latest master into the current worktree branch:
  ```bash
  git fetch origin && git merge origin/master
  ```
  Resolve any conflicts before proceeding. Never use `git merge master` alone — the local master ref may be stale.
- **Context:** this runs in a dedicated worktree. All file operations happen inside it.
- **Last step before writing:** invoke the `grill-with-docs` skill — it surfaces requirements, acceptance criteria, scope, and GB hardware constraints. Only once the grilling is satisfied, proceed to writing the plan.

### Hard Gate Sequence

**Why:** the baseline's task template is language-agnostic and knows nothing about ROM banking,
SDCC, or this project's agents. The sequence is **plan content** — what a plan document must
contain so an implementer sees it — not a runtime invocation list, so #527 R4's removal of manual
gate invocations does not reach it.

**Every task touching `src/*.c` or `src/*.h` MUST carry the full hard-gate sequence, written into
the plan.** The sequence and its expanded template are both in
`.claude/skill-overlays/references/task-templates.md` — write it into the plan verbatim, including
step 10 (`gb-c-optimizer`, dispatched by the **controller**, not the implementer; #633 R5).

Non-C tasks (markdown, Python, JSON, assets): write → verify → commit. No bank gates.

**Constant-removal audit:** if any task removes or renames a shared constant (e.g. `PLAYER_ACCEL`, `PLAYER_MAX_SPEED`), add a grep step at the top of that task before listing affected files:
```bash
grep -r CONSTANT_NAME tests/
```
Include ALL matching test files in the task's file list — not just the ones you remembered. Missing a file means surprise failures during parallel execution, after other tasks' commits have already landed.

### Smoketestable batches

**Why:** the baseline right-sizes tasks around a reviewer's gate; it has no concept of a
checkpoint where a ROM must visibly run. The `#### Parallel Execution Groups` table is also what
licenses the `subagent-driven-development` overlay's free task ordering — without it, the plan's
written order stands. It never licenses concurrency: that overlay dispatches one implementer at a
time whatever the table says.

**Tasks MUST be grouped into batches of 2–4.** Each batch ends with a **Smoketest Checkpoint** — a point where the ROM runs in Emulicious and the user confirms it looks correct. A good batch boundary = any point where the game should visually work end-to-end (even partially). If a batch cannot be independently smoke-tested, the plan must explain why.

**Dependency analysis** (required before writing each Smoketest Checkpoint block):
1. List all output files for each task in the batch.
2. Mark as **sequential** any two tasks that write the same file, or where Task B compiles against a symbol Task A defines.
3. Group remaining tasks into independent layers — tasks with the same `Depends on` set are parallelizable with each other.
4. Fill in `**Depends on:**` and `**Parallelizable with:**` on every task.
5. Insert a `#### Parallel Execution Groups` table immediately before the Smoketest Checkpoint block — this is the executor's source of truth for parallel dispatch.

The checkpoint block template is in `.claude/skill-overlays/references/plan-structure.md`.

### Plan document header and templates

**Why:** only the `**Issue:** #N` line and the *Open questions* block are this project's; the
rest is reproduced verbatim so the two cannot drift apart. `tools/trace.py` parses the issue
line, and nothing upstream knows this project files its specs as GitHub issues — which is also
why 6.3.0's new `**Spec:**` field is satisfied by the issue line rather than added beside it.

- **Plan header** (mandatory, exact form) → `.claude/skill-overlays/references/plan-structure.md`.
  Includes the `**Issue:** #N` rule, the mandatory `## Global Constraints` block, and why no
  separate `**Spec:**` line is written.
- **Task templates** → `.claude/skill-overlays/references/task-templates.md`: the 11-step C-File
  Task Template (for `src/*.c` / `src/*.h`, all HARD GATE steps) and the Non-C Task Template
  (markdown/Python/JSON/assets). The baseline's template has neither the GB hard-gate steps nor
  the `**Depends on:**` / `**Parallelizable with:**` annotations this project's execution path
  requires.

### Plan Self-Review Checklist (HARD STOP before presenting to user)

**Why:** this extends the baseline's three-point self-review rather than replacing it; four of
the seven checks are project-specific (`config.h`, the parallel annotations, the group tables,
`trace.py`).

**Run all seven checks in `.claude/skill-overlays/references/plan-self-review.md` before offering
the execution handoff, plus the baseline's own three.** Fix any failure and re-run from the top.

The one check that changes what the *user* sees: **#3, unjustified `**Parallelizable with:**
none`, is never silently fixed** — present the plan with the Incomplete Warning block and let the
user decide. (Factory mode inverts this; see below.)

### Verifying verification steps

**Why:** the baseline's placeholder scan checks that a plan *has* verification commands; nothing
upstream asks whether those commands can fail. All three failure shapes were found in this
repo's own tooling (#441).

Every verification command in a plan must be paired with evidence it *can* fail, not only that it
passes. For each one, the plan must name either (a) the input flip that makes the check fail, or
(b) a probe file that triggers the failure. The three observed failure shapes — self-defeating
assert, platform-wrong assertion, environment-dependent test — are in
`.claude/skill-overlays/references/verification-failure-shapes.md`.

### Handoff

**Why:** the baseline recommends subagent-driven execution and presents the choice immediately;
here the choice is the user's with no recommendation, and it is gated on an explicit affirmative.
The baseline cannot know that this project's plans are handed off across sessions and worktrees.

After saving the plan, present the full plan to the user.

<HARD-GATE>
Do NOT offer execution options until the user gives an explicit affirmative approval (e.g. "yes", "looks good", "let's go", "proceed", or equivalent). Do not interpret silence or continued conversation as approval.
</HARD-GATE>

Only after an explicit affirmative, offer the execution choice:

**"Plan complete and saved to `docs/plans/<filename>.md`. Two execution options:**

**1. Subagent-Driven (this session)** — fresh subagent per task, review between tasks, fast iteration. Stays in this session.

**2. Parallel Session (separate)** — open a new session with executing-plans, batch execution with checkpoints.

If Parallel Session is chosen, guide the user to open a new session in the worktree; that session uses `superpowers:executing-plans`.

### Factory mode

**Why:** the factory runs unattended, so every step that waits on a human must have a
replacement or be waived; the baseline has no notion of an unattended run. Note the one place
this deliberately goes *beyond* the baseline: the baseline's self-review is explicitly "a
checklist you run yourself — not a subagent dispatch", while factory mode adds an adversarial
review subagent. That is bought with the absence of a human reviewer, not with a claim that the
baseline is wrong.

Active when `NUKE_FACTORY_RUN` is set — i.e. the PLAN stage of a `/factory` run. It **overrides
the `### Handoff` subsection above**, and nothing else in this overlay.

- The `<HARD-GATE>` blocking on explicit user approval **does not apply.** There is no user to
  approve. Do not present the plan for approval and do not offer execution options.
- The grill step in *Before you begin* is replaced by the **adversarial plan self-review**
  subagent described in `.claude/skills/factory/references/stages.md`. Its charter includes
  verifying the plan's *verification commands*, not just its code (#460).
- Every unresolved judgment call from that self-review is recorded as a decision:
  ```
  python tools/factory_event.py --issue <N> --kind decision --field "text=<what and why>"
  ```
- A ruling recorded after the plan is written can make the plan itself stale. The plan file
  is then amended in the same step that records the ruling — the operative rule lives in the
  `subagent-driven-development` overlay's `### Factory mode`, because that is the overlay
  loaded while tasks are being dispatched. What matters here is that **the plan file is a
  live document during BUILD, not a frozen one**: briefs are extracted from it, once, at
  dispatch time.
- The Plan Self-Review Checklist still runs in full. Check #3's Incomplete Warning block is
  **not** presented to a user — an unjustified `**Parallelizable with:** none` is fixed in place
  and the fix logged as a decision.
- Everything else — the filename convention, the `**Issue:** #N` header, the batch structure,
  the Smoketest Checkpoint blocks — is unchanged. The checkpoints themselves are executed
  headlessly; see the `subagent-driven-development` overlay's Factory mode.

Outside a factory run every checkpoint above fires exactly as written.

### Remember

**Why:** the first three lines restate baseline rules on purpose — they are the ones this
project's plans most often drop. The rest (skill/agent names, the C template, the Lessons
Learned gate) are project-specific.

- Exact file paths always; complete code in the plan (not "add validation"); exact commands with expected output.
- Reference skills and agents by name (e.g. `bank-pre-write` skill, `gbdk-expert` agent).
- DRY, YAGNI, TDD, frequent commits.
- C files ALWAYS get the 11-step template with all HARD GATE steps.
- **Lessons Learned gate:** `executing-plans` runs a final Lessons Learned step after the smoketest passes — no action is needed in the plan itself.
