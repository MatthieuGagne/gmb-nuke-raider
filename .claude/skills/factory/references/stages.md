# Factory stages — exact sequences

Every command below is wrapped by the stage-log helper. Written out once in full:

```
python tools/factory_log.py --stage GATE --issue <N> --stream -- python tools/spec_lint.py --issue <N> --json
```

Below, `LOG <STAGE> -- <cmd>` is shorthand for exactly that wrapper. `<N>` is the spec issue
number. Pass `--attempt <k>` on every retry.

`LOG <STAGE> --stream -- <cmd>` is the same wrapper with `--stream` added before the `--`.

Nine invocations below carry `--stream`: the orchestrator parses their stdout, and the helper is
quiet on success without it (#529). They are GATE's `spec_lint --json`, PLAN's
`trace.py --check --plans-only`, BUILD's post-dispatch `git log --oneline -1` verification (the
controller reads the SHA it prints), both `smoketest_headless --json` runs, `factory_cache.py`,
VERIFY's evidence scenario, SHIP's `factory_publish --open-pr`, and SHIP's `preserve_workspace`
call. VERIFY's is stated as a rule
rather than a literal command line because step 6's scenario is composed ad hoc — there is no
fixed command to tag. Every other wrapped command is gated on its exit code alone, so the summary
line is enough.

---

## Run start — before GATE

Once per run, from *Session setup* in `SKILL.md` (step 4), before GATE:

```
python tools/factory_publish.py --issue <N> --run-start
```

It sets `Status = In Progress` on the spec issue's Documents-board item, adding the item first
if the issue was never on the board. It adds no duplicate item on a `--resume` or a second
attempt — the item id is cached in `publish.json` — and the Status write is re-issued on
purpose, which is what lifts a spec back out of `Todo` after a failed attempt. Exit `1` is a
degradation, never a run failure: note the `factory-publish: WARNING:` line and continue.

---

## GATE

1. `LOG GATE --stream -- python tools/spec_lint.py --issue <N> --json`
2. Record the gate result:
   `python tools/factory_event.py --issue <N> --kind gate --field stage=GATE --field gate=spec-lint --field result=<pass|fail>`
3. **Exit 1 (invalid spec) → terminal, before any worktree exists.** Do **not** comment on the
   spec issue yourself — `factory_publish` owns every GitHub surface, and a raw `gh` write is
   what stalls an unattended run (#481). Put the lint errors in the failure message instead:
   ```
   python tools/factory_event.py --issue <N> --kind failure --field "message=GATE: spec_lint rejected the spec — missing <sections>"
   ```
   `comment_once` renders that verbatim into the spec-issue comment as
   `Failed in GATE: <message>`, so the missing sections reach the human exactly once, through
   the sanctioned path. Then follow *Terminal failure* in `SKILL.md`.
   Exit 2 is an operational error (could not fetch the issue) — also terminal, different message.
4. Read `doc_only` from the JSON. `true` → the doc-only route (see *Doc-only route* below).
5. `python tools/factory_publish.py --issue <N> --stage-completed GATE`

## PLAN

1. Append the stage event: `--kind stage --field stage=PLAN`.
2. Create the worktree. The `git worktree add` is the portable half; entering it is the one
   Claude-specific step to re-map on migration:
   ```
   LOG PLAN -- git worktree add .claude/worktrees/factory-issue-<N> -b factory-issue-<N> origin/master
   ```
   Then `EnterWorktree(path=".claude/worktrees/factory-issue-<N>")`.
   **If the path or branch already exists:** do not delete and do not overwrite. Resume when the
   registry state matches this issue; otherwise stop with guidance naming the existing path.
3. Record the worktree and branch on the run:
   ```
   python tools/factory_event.py --issue <N> --kind start --field worktree=<abs path> --field branch=factory-issue-<N> --field stage=PLAN
   ```
4. Write the plan with the `writing-plans` skill in **factory mode** (its overlay's
   `### Factory mode` subsection removes the handoff HARD-GATE). The plan filename and header
   follow PRD-3 exactly: `docs/plans/YYYY-MM-DD-issue<N>-<slug>.md` containing `**Issue:** #<N>`.
   Then record it on the run, so the publisher can find it:
   ```
   python tools/factory_event.py --issue <N> --kind start --field plan=docs/plans/YYYY-MM-DD-issue<N>-<slug>.md
   ```
   The path is **repo-relative** — the publisher resolves it against the run's worktree, which is
   the only place it exists: `docs/plans/` is gitignored, so the plan never reaches the branch.
5. **Adversarial plan self-review** — dispatch a subagent **with `model: opus`** (the most
   capable tier: this is the run's only defence against unrunnable or self-defeating
   verification steps, and an omitted model would inherit whatever tier the session started on
   — #528 R6). Its charter is to attack the plan, not to approve it. It must check, at minimum:
   - Does every spec requirement map to a task?
   - **Do the plan's verification commands actually work?** This is the #460 mandate. Hunt
     specifically for: asserts that pass no matter what (self-defeating), commands that assume
     the wrong platform, and checks that pass standalone but fail under the hook they were
     written for.
   - Are the types, names and signatures consistent between tasks?
   - **Which already-landed tests does each task break, and does the plan say how it handles
     them?** The `pre-commit` hook runs the whole suite and `--no-verify` is forbidden, so every
     existing test is a hard gate on every task. Concrete rejection: a task that adds a `BANKED`
     function and does not name `tests/test_rom_parity.py`. The new trampoline shifts bank-0
     addresses, the parity test refuses the commit, and the plan is silent — reject it and make
     the plan say whether the test is updated or why it still passes. Run #590 paid for this
     three times: `tests/test_rom_parity.py` refused a commit at Tasks 2, 3 and 4, and each fix
     was a mid-run ruling that a plan-time read would have caught.

   Every unresolved judgment call it raises becomes a `decision` event, written as **two
   fields**: `text` holds the ruling in one sentence, and `rationale` holds the reasoning in one
   to three sentences. Both renderers show `text` as a bold line and put `rationale` in a collapsed
   block, so a reader skims the rulings and opens only the ones that matter (#517 R15, R17).
   Add `--field finding=true` to each of these: they name defects in the draft plan, so the run
   issue renders them under *Plan review findings* and the PR body omits them (#530 R3).

   ```
   python tools/factory_event.py --issue <N> --kind decision --field finding=true \
     --field "text=<the ruling>" --field "rationale=<the reasoning>"
   ```
6. `LOG PLAN --stream -- python tools/trace.py --check --plans-only` — expect `PASS` and no `ERROR` line
   naming this plan. Record as a gate.
7. `python tools/factory_publish.py --issue <N> --stage-completed PLAN`
   This is where the **plan issue** appears (#514): title `plan: <slug> (#<N>)`, label `plan`,
   `Type = Plan` on the Documents project, a structural summary in the body and the byte-exact
   plan as the `factory-logs` release asset `issue-<N>-plan.md`. `Type = Plan` requires a
   one-time manual prerequisite: a human must add a `Plan` option to the `Type` field of project
   3 ("Nuke Raider — Documents"). Until that option exists, the issue is still created and
   labelled, only untyped, with one warning per publish. It is created once and re-synced
   on every later publish, so plan edits made during BUILD show up without another command. The
   plan asset is re-uploaded in place, not appended: a later attempt's plan replaces an earlier
   one, unlike stage logs, which keep per-attempt history. The run's PR closes it automatically.
   A plan that cannot be read is one `factory-publish: WARNING:` line and exit 1 — reportable,
   never a run failure.
8. **`--dry-run` stops here**, with the run state recording the PLAN stage.

## BUILD

1. Append the stage event: `--kind stage --field stage=BUILD`.
2. `LOG BUILD -- git log --oneline -1` — the head BUILD starts from. It is unconditional and it
   is BUILD's first wrapped command, so `logs/BUILD.log` exists and is non-empty from the moment
   the stage opens, however the stage ends (#654).
3. **Who wraps what inside BUILD.** BUILD is not exempt from the stage-log rule; it is the one
   stage whose commands are run by two different actors, so the rule names both.
   - **The controller** wraps every command it runs itself with `LOG BUILD --`: step 2 above,
     the `git log --oneline -1` verification the `subagent-driven-development` overlay mandates
     after **every** implementer dispatch, and each command of the batch-boundary headless
     checkpoint. The checkpoint's command list is stated once, in that overlay's
     `### Factory mode`, and is not copied here. The **verification** carries `--stream` —
     `LOG BUILD --stream -- git log --oneline -1` — because its whole purpose is that the
     controller reads the SHA; step 2's copy does not, because nothing reads it.
   - **A dispatched implementer** wraps its own `make`, `make test` and `git commit` with
     `python tools/factory_log.py --stage BUILD --issue <N> --`. The obligation and the issue
     number reach it through its brief: `NUKE_FACTORY_RUN` does not cross a dispatch, so a
     subagent that is not told the number cannot write to the run's log.
   - **Registry and publisher bookkeeping is not wrapped** — `factory_event.py`,
     `factory_publish.py` — exactly as in every other stage.
4. Run `subagent-driven-development` in **factory mode** (its overlay's `### Factory mode`
   subsection replaces the batch-boundary Emulicious pause with the headless gate, and states
   the implementer's wrapping obligation).
   - All existing GB hard gates fire unchanged: `bank-pre-write`, `gbdk-expert`,
     `post-build-gates`, `gb-c-optimizer`.
   - Every host-testable acceptance criterion gets a `make test` case.
   - A README task is added when user-visible behavior changes.
   - **Every implementer brief carries the run's issue number** and the wrapping rule from
     step 3.
5. **Retry budget: 2 attempts per task.** On the second attempt append
   `--kind retry --field stage=BUILD --attempt <k>` first, and pass `--attempt <k>` to every
   `LOG BUILD` call for that attempt. Exhausted → terminal failure.
6. **A ruling that makes the plan stale is written into the plan file, in the same step that
   records it.** Task briefs are extracted from the plan once, at dispatch time, so a ruling
   that amends a fact a later task's brief states never reaches that task unless the plan
   itself changes. Record the `decision` event **and** edit the plan file before dispatching
   the next task. The publisher re-syncs the plan issue on every later `--stage-completed`
   call, so the amendment reaches GitHub with no extra command. In run #590 three implementers
   corrected the controller about facts their briefs stated and later rulings had falsified —
   the controller was handing out text it had itself ruled false.
7. Commits: tool choice is free (#441 voided the old PowerShell-routing premise — repository
   hooks fire for every actor). Give every commit an explicit **300 s timeout**: the
   `pre-commit` hook runs the whole tool suite, which is past the 120 s default, and a
   default-timeout call is killed mid-hook. This is a ceiling, not a measurement — if a commit
   ever exceeds it, that is the signal, not a number to bump. Wrapping a commit in `LOG BUILD`
   does not change that budget: the helper adds a pipe, not work.
   **Never `--no-verify`.**
8. `python tools/factory_publish.py --issue <N> --stage-completed BUILD`

## VERIFY

1. Append the stage event: `--kind stage --field stage=VERIFY`.
2. `LOG VERIFY -- git fetch origin` then `LOG VERIFY -- git merge origin/master`.
   This is load-bearing for mergeability, not just correctness: branch protection on `master` is
   `strict`, so an out-of-date branch cannot merge (#441).
3. `LOG VERIFY -- make clean` then `LOG VERIFY -- make`. Record as a gate.
4. `LOG VERIFY -- make memory-check`. Record as a gate. **A FAIL aborts the run immediately** —
   no retry, no diagnostic.
5. Blocking generic smoketest:
   ```
   LOG VERIFY --stream -- python tools/smoketest_headless.py --scenario generic-smoke --json
   ```
   Record a `scenario` event with `blocking=true`.
   - Exit 0 → continue.
   - Exit 1 → **one** differential-guided attempt:
     a. `LOG VERIFY --stream -- python tools/factory_cache.py` → prints the reference ROM path. Exit 1 is
        a reference-build failure; exit 2 means it could not run. Either way, say so and treat
        the smoketest failure as undiagnosed.
     b. `LOG VERIFY --stream -- python tools/smoketest_headless.py --scenario generic-smoke --ref-rom <path> --json`
     c. Read `divergence` from the JSON — `step`, `frame`, `symbol`, `main`, `ref`. **That first
        WRAM divergence is where the diagnosis starts.** Never diagnose from code inspection.
     d. If `verdict` is `scenario-invalid`, both ROMs failed: the scenario is wrong, not the
        game. Downgrade to a scenario fix. The exit code does not tell you this — read the JSON.
     e. Fix, rebuild, re-run once. Still failing → terminal failure.
   - Exit 2 is a tool/usage error, not a game failure: fix the invocation.
6. Evidence scenario — compose a spec-specific scenario from the library
   (`tools/scenarios/*.json`; `include` pulls in `reach-race` / `reach-hub`), set
   `"blocking": false`, and run it. Record a `scenario` event with `blocking=false`.
   **Evidence, not a gate.** One fix attempt; still failing → the PR ships with a prominent
   FAILED section (the reporter emits it).

   Wrap it with `--stream`: its JSON verdict is read, not just its exit code.
7. `python tools/factory_publish.py --issue <N> --stage-completed VERIFY`

## SHIP

1. Append the stage event: `--kind stage --field stage=SHIP`.
2. Render the PR body:
   `LOG SHIP -- python tools/factory_report.py --issue <N> --out .factory/runs/issue-<N>/pr-body.md`
   It already contains the gate table, *Decisions made*, scenario evidence or the FAILED
   section, and `Closes #<N>`. At `--open-pr` the publisher appends `Closes #<plan issue>` to
   this same file and writes no second copy (#530 AC5).
   Re-run this render if you record a decision before step 4. Otherwise the pull request body
   omits that decision. The run issue then treats it as already covered (#530 finding 1).
3. `LOG SHIP -- git push -u origin factory-issue-<N>`. Budget a full clean build, not a push: the
   `pre-push` repository hook runs `make clean && make`. **Never `--no-verify`.** If push fails on
   credentials:
   `gh auth setup-git`.
4. Open the PR through the publisher — never `gh pr create` directly (#481):
   ```
   LOG SHIP --stream -- python tools/factory_publish.py --issue <N> --open-pr --branch factory-issue-<N> --title "<type>: <summary> (#<N>)" --body-file .factory/runs/issue-<N>/pr-body.md
   ```
   It prints the PR URL on stdout. **Exit 1 here is terminal, not a degradation** — this is the
   one `factory_publish` call where that is true, because the PR is the run's deliverable and
   there is nothing to review without it. An already-open PR for the branch exits 0 and prints
   nothing new, so `--resume` is safe.
5. `python tools/factory_event.py --issue <N> --kind finish --field result=shipped`
   This records the run's result. Do not add a `pr` field. The `finish` event ignores it.
   Step 4 already saved the PR URL in `publish.json`, through `--open-pr`. The run issue
   reads the URL from there, not from the `finish` event.
6. Preserve the run's own working notes, so they outlive the worktree:
   ```
   LOG SHIP --stream -- python -c "import sys; sys.path.insert(0, 'tools'); import factory_run; print(factory_run.preserve_workspace(<N>))"
   ```
   `--stream` is required: the printed path is read, not merely exit-code checked.
   It takes the worktree and plan from the run state, copies the plan, the SDD ledger
   (`progress.md`) and every task brief and report into
   `.factory/runs/issue-<N>/sdd-workspace/`, and writes a `manifest.json` listing each
   artifact as present or absent-with-reason. **It never raises and never fails the run**
   (#633 R7): a missing artifact is a manifest line, not an error. A printed `None` means the
   registry itself was unusable — report it and continue to the `--terminal` publish.
   Not published: like the autopsy bundle, these notes stay local.
7. `python tools/factory_publish.py --issue <N> --terminal`
8. **Stop.** Never merge. Never delete the worktree.

## Doc-only route (R10)

When GATE's JSON reports `doc_only: true`, BUILD is replaced by the abbreviated doc path
(`doc-review` skill in factory mode): edit the doc files, no TDD cycle, no bank gates, no
`gbdk-expert`. **VERIFY keeps its clean build and the blocking generic smoketest** — the
sanity gates survive on the doc-only route. GATE, PLAN, VERIFY and SHIP are otherwise identical.

## Terminal failure — the autopsy

Before publishing, write the bundle:

```
python -c "import sys; sys.path.insert(0, 'tools'); import factory_run; print(factory_run.write_autopsy(<N>, worktree=r'<abs path>'))"
```

It copies state, journal, the scenario as executed, smoketest screenshots and traces, and
sha256 sums of the ROM and reference ROM into `autopsy/attempt-<k>/`. It never raises.

Then `python tools/factory_publish.py --issue <N> --terminal`. The run issue carries stage,
reason, worktree path, and an inline ~100-line tail of the failing stage's log — explicitly
marked as a lossy excerpt, with the byte-exact whole file in the release assets. When the
stage-log helper fail-opened, the tail reads *"no stage log captured"*.

---

## Event cookbook — `tools/factory_event.py`

Moved from `SKILL.md`. State is written **only** through this helper; kinds outside
`factory_run.EVENT_KINDS` are refused, and `state.json` / `journal.jsonl` are never written by
any other means. The stage sequences above name the event each step must append; this is the
one-line form of each kind.

```
python tools/factory_event.py --issue <N> --kind stage    --field stage=BUILD
python tools/factory_event.py --issue <N> --kind gate     --field stage=VERIFY --field gate=memory-check --field result=pass
python tools/factory_event.py --issue <N> --kind decision --field "text=<the ruling, one sentence>" --field "rationale=<the reasoning, 1-3 sentences>"
python tools/factory_event.py --issue <N> --kind scenario --field scenario=generic-smoke --field result=pass --field blocking=true
python tools/factory_event.py --issue <N> --kind retry    --field stage=BUILD --attempt 2
python tools/factory_event.py --issue <N> --kind failure  --field "message=<stage>: <reason>"
python tools/factory_event.py --issue <N> --kind finish   --field result=shipped
```

`start` carries the run's identity rather than a stage result — see *Run start* and *PLAN*
above for its two forms (`worktree`/`branch`/`stage`, then `plan`).

---

## Retry budgets

Moved from `SKILL.md`. Each budget is also stated at the stage that owns it, above.

| What | Budget | On exhaustion |
|------|--------|---------------|
| BUILD task | 2 attempts | Terminal failure |
| Blocking generic smoketest | 1 differential-guided diagnostic/fix attempt | Terminal failure |
| Evidence scenario | 1 fix attempt | PR ships with a prominent FAILED section |
| Memory budget FAIL | 0 | Abort immediately |

The smoketest diagnostic starts from the **differential report** — the first WRAM divergence
against the reference ROM — never from code inspection. Provision the reference lazily with
`python tools/factory_cache.py`. A `verdict` of `scenario-invalid` in
`build/smoketest/<name>/results.json` means the scenario is wrong, not the game: downgrade to a
scenario fix. **Read the verdict from the JSON — the exit code does not distinguish it.**

---

## Stage-log mechanics and publication internals

Moved from `SKILL.md` — the operating detail behind its stage-log and publisher rules.

### Quiet success (#529)

A passing wrapped command prints one line, not its output:

```
factory-log: ok stage=VERIFY exit=0 bytes=12043 lines=118 log=<path> cmd: make
```

Nothing is lost — the complete, byte-exact output is in the stage log named on that line, which
is what the autopsy bundle and the published log assets read. A command that **fails** still
prints everything, unchanged, because that is where every line matters.

Two consequences to plan around. Add `--stream` after `--issue` when the orchestrator has to
*read* the command's stdout — a `--json` payload, a printed path or URL; the stage sequences
above mark every such invocation. And while a command is running the console is silent, so a
wrapped command that hangs or is killed prints nothing: tail
`.factory/runs/issue-<N>/logs/<STAGE>.log`, whose path is fixed by the stage and issue you passed.

### Helper exit codes

The helper is fail-open — it returns the child's exit code verbatim, so gate on that exit code
exactly as if the helper were not there. `127` means the command could not be spawned; `2` means
the helper itself was misused. A `factory-log: WARNING:` line on stderr means the log was not
captured; the run continues.

### Who wraps what (#654)

The orchestrator wraps every command it runs itself, in every stage — BUILD included. Most of
BUILD's commands are run by dispatched implementers rather than by the orchestrator, and each
subagent wraps its own: its brief carries `--issue <N>`, because `NUKE_FACTORY_RUN` does not
cross a dispatch. Registry and publisher bookkeeping — `factory_event.py`, `factory_status.py`,
and `factory_publish.py`'s `--run-start`, `--stage-completed` and `--terminal` calls — is not
wrapped: it writes its own record. The one publisher call that is wrapped is SHIP's `--open-pr`,
because the run reads the PR URL it prints. The BUILD sequence above names BUILD's wrapped
commands exactly.

### A stage that ran unwrapped is reported, not fatal (#489)

An unwrapped stage is a **reportable degradation, never a run failure**. The publisher's exit
code 1 keeps exactly the meaning it has in `SKILL.md`'s *Publication cadence*, and
`factory_log.py` stays fail-open: the child's exit code is what the run gates on, and no
bookkeeping outcome can fail a run.

What changed is that the omission is no longer prose alone. `factory_run` stamps the stage on the
transition event that **leaves** it, and the stage is then named by
`python tools/factory_status.py` — in the table's trailing summary line and in its `--json` rows —
by the PR body `factory_report.py` renders, and by the run issue. An **empty** log counts as no
log everywhere it is read: the upload path and the failure section's log tail alike.

Two limits, plainly:

1. A run recorded **before** this change reports nothing. The fact is captured at transition time
   and is never reconstructed afterwards, because the renderers that name unlogged stages —
   `factory_report.render` and `factory_status._row` — are pure functions of run state and never
   stat the registry. The failure section's log tail does read the registry; it is the exception,
   not the rule the other two follow.
2. A **retried** stage that runs unwrapped on a later attempt is **not** flagged.
   `tools/factory_log.py` opens the stage log in append mode and `factory_run.log_path` has no
   attempt component, so attempt 1's bytes keep the log non-empty. A `retry` event still clears
   the recorded stages, because carrying an earlier attempt's omission forward would misreport
   the current one.

### Publication internals

`--run-start` does exactly one thing: put the spec issue on the Documents board and set its
`Status = In Progress`, so the board shows what the factory is working on while it works on it.
It creates no run issue and never sets `Type` — classification stays with the human and with
`/prd`. At terminal the run issue goes to `Status = Done`, and a **failed** run puts the spec
back to `Todo`; a successful one leaves it `In Progress`, because the PR is open and the merge
is what finishes the spec. Known limitation: a retried run's dashboard issue is reopened but
keeps `Status = Done` while it is live — the `In Progress` write happens only when the run issue
first joins the board, not on every reopen.

The publisher owns three GitHub objects per run: the **run issue** (`Type = Log`, the execution
record), the **plan issue** (`Type = Plan`, created at PLAN completion and re-synced on every
later publish — #514; full mechanics in *PLAN* step 7 above), and the **PR** at SHIP. The plan
issue is never closed by the publisher; the PR body closes it on merge. A dry run and a terminal
failure both leave it open on purpose.

The run issue and the PR body do not repeat each other (#530). The decision record sits on one
of them and the other links to it. Plan-review findings sit on the run issue alone.
