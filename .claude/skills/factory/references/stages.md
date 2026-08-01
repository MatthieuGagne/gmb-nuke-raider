# Factory stages — exact sequences

Every command below is wrapped by the stage-log helper. Written out once in full:

```
python tools/factory_log.py --stage GATE --issue <N> -- python tools/spec_lint.py --issue <N> --json
```

Below, `LOG <STAGE> -- <cmd>` is shorthand for exactly that wrapper. `<N>` is the spec issue
number. Pass `--attempt <k>` on every retry.

---

## Run start — before GATE

Once per run, from *Session setup* in `SKILL.md` (step 4), after the `start` event and before
the first stage:

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

1. `LOG GATE -- python tools/spec_lint.py --issue <N> --json`
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
5. **Adversarial plan self-review** — dispatch a subagent whose charter is to attack the plan,
   not to approve it. It must check, at minimum:
   - Does every spec requirement map to a task?
   - **Do the plan's verification commands actually work?** This is the #460 mandate. Hunt
     specifically for: asserts that pass no matter what (self-defeating), commands that assume
     the wrong platform, and checks that pass standalone but fail under the hook they were
     written for.
   - Are the types, names and signatures consistent between tasks?

   Every unresolved judgment call it raises becomes a `decision` event.
6. `LOG PLAN -- python tools/trace.py --check --plans-only` — expect `PASS` and no `ERROR` line
   naming this plan. Record as a gate.
7. `python tools/factory_publish.py --issue <N> --stage-completed PLAN`
8. **`--dry-run` stops here**, with the run state recording the PLAN stage.

## BUILD

1. Append the stage event: `--kind stage --field stage=BUILD`.
2. Run `subagent-driven-development` in **factory mode** (its overlay's `### Factory mode`
   subsection replaces the batch-boundary Emulicious pause with the headless gate).
   - All existing GB hard gates fire unchanged: `bank-pre-write`, `gbdk-expert`,
     `bank-post-build`, `gb-c-optimizer`.
   - Every host-testable acceptance criterion gets a `make test` case.
   - A README task is added when user-visible behavior changes.
3. **Retry budget: 2 attempts per task.** On the second attempt append
   `--kind retry --field stage=BUILD --attempt <k>` first. Exhausted → terminal failure.
4. Commits: tool choice is free (#441 voided the old PowerShell-routing premise — repository
   hooks fire for every actor). Budget ~6 s per commit for the `pre-commit` tool suite.
   **Never `--no-verify`.**
5. `python tools/factory_publish.py --issue <N> --stage-completed BUILD`

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
   LOG VERIFY -- python tools/smoketest_headless.py --scenario generic-smoke --json
   ```
   Record a `scenario` event with `blocking=true`.
   - Exit 0 → continue.
   - Exit 1 → **one** differential-guided attempt:
     a. `LOG VERIFY -- python tools/factory_cache.py` → prints the reference ROM path. Exit 1 is
        a reference-build failure; exit 2 means it could not run. Either way, say so and treat
        the smoketest failure as undiagnosed.
     b. `LOG VERIFY -- python tools/smoketest_headless.py --scenario generic-smoke --ref-rom <path> --json`
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
7. `python tools/factory_publish.py --issue <N> --stage-completed VERIFY`

## SHIP

1. Append the stage event: `--kind stage --field stage=SHIP`.
2. Render the PR body:
   `LOG SHIP -- python tools/factory_report.py --issue <N> --out .factory/runs/issue-<N>/pr-body.md`
   It already contains the gate table, *Decisions made*, scenario evidence or the FAILED
   section, and `Closes #<N>`.
3. `LOG SHIP -- git push -u origin factory-issue-<N>`. Budget ~29 s: the `pre-push` repository
   hook runs `make clean && make`. **Never `--no-verify`.** If push fails on credentials:
   `gh auth setup-git`.
4. Open the PR through the publisher — never `gh pr create` directly (#481):
   ```
   LOG SHIP -- python tools/factory_publish.py --issue <N> --open-pr --branch factory-issue-<N> --title "<type>: <summary> (#<N>)" --body-file .factory/runs/issue-<N>/pr-body.md
   ```
   It prints the PR URL on stdout. **Exit 1 here is terminal, not a degradation** — this is the
   one `factory_publish` call where that is true, because the PR is the run's deliverable and
   there is nothing to review without it. An already-open PR for the branch exits 0 and prints
   nothing new, so `--resume` is safe.
5. `python tools/factory_event.py --issue <N> --kind finish --field result=shipped`
   plus a `--kind start --field pr=<url>` style update is **not** needed — record the PR with
   `--kind finish --field result=shipped --field pr=<url>`.
6. `python tools/factory_publish.py --issue <N> --terminal`
7. **Stop.** Never merge. Never delete the worktree.

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
