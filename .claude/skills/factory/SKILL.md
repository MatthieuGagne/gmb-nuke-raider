---
name: factory
description: "Use when the user runs /factory <issue#> — drives a PRD issue through GATE, PLAN, BUILD, VERIFY and SHIP unattended, ending at a reviewable PR. Flags: --stage NAME, --resume, --dry-run."
---

# Factory Orchestrator

**Announce at start:** "I'm using the factory skill to run issue #<N>."

**You are running unattended.** Never ask the user a question — not for approval, not for
confirmation, not to disambiguate. Every ambiguity is resolved conservatively and recorded as a
decision (see *Decisions*). A run that stops to ask has failed, not paused. Human review happens
at the PR and nowhere else.

## Invocation

```
/factory <issue#> [--stage <GATE|PLAN|BUILD|VERIFY|SHIP>] [--resume] [--dry-run]
```

| Flag | Effect |
|------|--------|
| *(none)* | Run GATE → PLAN → BUILD → VERIFY → SHIP |
| `--stage <NAME>` | Run exactly that one stage against the recorded run state, then stop |
| `--resume` | Continue from the stage recorded in the registry |
| `--dry-run` | GATE and PLAN only; stop before BUILD |

## Session setup — before any stage

1. Export the correlation variable for this session: `NUKE_FACTORY_RUN=<issue#>`. It is what
   links permission prompts and deny-gate refusals to this run. Never set it from a settings
   file — the repo tier forbids `env` ([ADR 443](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/466)).
2. Read the existing run state: `python tools/factory_status.py --json` and look for this issue.
   - No entry, and no `--resume` → this is a fresh run. Append the `start` event at GATE.
   - Entry exists, `--resume` given → validate the recorded `worktree` still exists on disk. If
     it does not, stop with: `stale run: worktree <path> no longer exists; start a fresh run or
     restore the worktree`. Do not recreate it.
   - Entry exists, no `--resume` and no `--stage` → **do not collide.** If the recorded stage is
     terminal (`failed`/`complete`), append a `retry` event with the next `attempt` and continue
     from the recorded stage. Otherwise stop and say which run is already in flight.
3. **Never delete or overwrite an existing worktree or branch**, whatever the state says.
4. Announce the run on the Documents board, before GATE:
   ```
   python tools/factory_publish.py --issue <N> --run-start
   ```
   Exit `1` is a degradation, never a run failure — note the `factory-publish: WARNING:` line
   and continue into GATE.

## The five stages

Exact command sequences are in `references/stages.md` — follow them literally.

| Stage | Does | Blocking on |
|-------|------|-------------|
| GATE | `spec_lint` the issue | Lint failure → comment the missing sections on the issue, terminal |
| PLAN | Create the factory worktree and branch, write the plan, adversarially self-review it | Plan self-review cannot be waived |
| BUILD | subagent-driven-development in factory mode; all GB hard gates fire unchanged | 2 attempts per task |
| VERIFY | fetch+merge, clean build, memory check, blocking smoketest, evidence scenario | memory FAIL aborts immediately; smoketest gets 1 differential-guided fix attempt |
| SHIP | Push, open the PR with the reporter body, preserve the run's working notes | `pre-push` runs `make clean && make` |

**SHIP preserves the run's working notes.** The plan, the subagent-driven-development ledger
and every task brief and report live in the worktree, and `docs/plans/` and `.superpowers/`
are both gitignored — so the record of *why* the run made its choices dies with ordinary
worktree cleanup. `factory_run.preserve_workspace` copies them into
`.factory/runs/issue-<N>/sdd-workspace/` at SHIP. It is best-effort by contract: a missing
artifact is recorded in `manifest.json` and never raised, so preservation cannot fail a run
that has already opened its pull request. Terminal failure keeps its own bundle —
`write_autopsy` — and the two do not overlap.

## Every stage command goes through the stage-log helper

A stage's work commands are wrapped — builds, tests, git operations, scenario runs:

```
python tools/factory_log.py --stage <STAGE> --issue <N> [--attempt <k>] -- <argv...>
```

Pass `--attempt` on every retry. The helper is fail-open — it returns the child's exit code
verbatim, so gate on that exit code exactly as if the helper were not there. `127` means the
command could not be spawned; `2` means the helper itself was misused. A
`factory-log: WARNING:` line on stderr means the log was not captured; the run continues.

**A passing command prints one line, not its output** (#529):

```
factory-log: ok stage=VERIFY exit=0 bytes=12043 lines=118 log=<path> cmd: make
```

Nothing is lost — the complete, byte-exact output is in the stage log named on that line, which
is what the autopsy bundle and the published log assets read. A command that **fails** still
prints everything, unchanged, because that is where every line matters.

Two consequences to plan around. Add `--stream` after `--issue` when the orchestrator has to
*read* the command's stdout — a `--json` payload, a printed path or URL; `references/stages.md`
marks every such invocation. And while a command is running the console is silent, so a wrapped
command that hangs or is killed prints nothing: tail
`.factory/runs/issue-<N>/logs/<STAGE>.log`, whose path is fixed by the stage and issue you passed.

**Who wraps what.** The orchestrator wraps every command it runs itself, in every stage —
BUILD included. Most of BUILD's commands are run by dispatched implementers rather than by the
orchestrator, and each subagent wraps its own: its brief carries `--issue <N>`, because
`NUKE_FACTORY_RUN` does not cross a dispatch. Registry and publisher bookkeeping —
`factory_event.py`, `factory_status.py`, and `factory_publish.py`'s `--run-start`,
`--stage-completed` and `--terminal` calls — is not wrapped: it writes its own record. The one
publisher call that is wrapped is SHIP's `--open-pr`, because the run reads the PR URL it
prints. `references/stages.md` names BUILD's wrapped commands exactly (#654).

## Recording state

State is written only through `tools/factory_event.py`:

```
python tools/factory_event.py --issue <N> --kind stage    --field stage=BUILD
python tools/factory_event.py --issue <N> --kind gate     --field stage=VERIFY --field gate=memory-check --field result=pass
python tools/factory_event.py --issue <N> --kind decision --field "text=<the ruling, one sentence>" --field "rationale=<the reasoning, 1-3 sentences>"
python tools/factory_event.py --issue <N> --kind scenario --field scenario=generic-smoke --field result=pass --field blocking=true
python tools/factory_event.py --issue <N> --kind retry    --field stage=BUILD --attempt 2
python tools/factory_event.py --issue <N> --kind failure  --field "message=<stage>: <reason>"
python tools/factory_event.py --issue <N> --kind finish   --field result=shipped
```

Kinds outside `factory_run.EVENT_KINDS` are refused. Do not write `state.json` or
`journal.jsonl` by any other means.

## Publication cadence

Call the publisher (PRD-12, #472) — never write a GitHub surface yourself. **"Yourself" includes
running `gh`.** If a step would create, edit, or comment on any GitHub object, it goes through
`factory_publish`; a raw `gh` write is refused by the harness permission gate and stalls the run
(#481). The only sanctioned direct `gh` call is `gh auth setup-git`, which is local credential
configuration and writes nothing.

```
python tools/factory_publish.py --issue <N> --run-start
python tools/factory_publish.py --issue <N> --stage-completed <STAGE>
python tools/factory_publish.py --issue <N> --terminal
```

`--run-start` is the first publisher call of a run, made in *Session setup* **before GATE**. It
does exactly one thing: put the spec issue on the Documents board and set its
`Status = In Progress`, so the board shows what the factory is working on while it works on it.
It creates no run issue and never sets `Type` — classification stays with the human and with
`/prd`. At terminal the run issue goes to `Status = Done`, and a **failed** run puts the spec
back to `Todo`; a successful one leaves it `In Progress`, because the PR is open and the merge
is what finishes the spec. Known limitation: a retried run's dashboard issue is reopened but
keeps `Status = Done` while it is live — the `In Progress` write happens only when the run issue
first joins the board, not on every reopen.

The publisher owns three GitHub objects per run: the **run issue** (`Type = Log`, the execution
record), the **plan issue** (`Type = Plan`, created at PLAN completion and re-synced on every
later publish — #514), and the **PR** at SHIP. `Type = Plan` is a one-time manual prerequisite: a
human must add a `Plan` option to the `Type` field of project 3 ("Nuke Raider — Documents");
until then the plan issue is still created and labelled, only untyped, with one warning per
publish. The plan issue is never closed by the publisher;
the PR body closes it on merge. A dry run and a terminal failure both leave it open on purpose.

The run issue and the PR body do not repeat each other (#530). The decision record sits on one
of them and the other links to it. Plan-review findings sit on the run issue alone.

Call `--stage-completed` and `--terminal` at **every stage transition, every gate result, and at
terminal** (SHIP success and terminal failure alike) — roughly 15-25 edits per run.

**Exit code 1 means "published with degradation". It is reportable, never a run failure.**
Note the `factory-publish: WARNING:` lines and carry on. Exit 2 is misuse — fix the call.

## Decisions

R5 of the epic: mid-run ambiguities are resolved **conservatively** and logged. Conservative
means: prefer the interpretation that changes least, keeps existing behaviour, and stays inside
the spec's stated scope. When the spec itself asks you to choose (e.g. "decide which side is
wrong"), pick the option with the smaller blast radius, record the reasoning, and move on.

Every such call becomes a `decision` event immediately — not at the end. The record goes to one
surface per run. A run that opens a pull request puts it in the PR body's *Decisions made*
section, which is the human's entry point at review, and the run issue links to the PR. A run
that fails opens no pull request, so the run issue keeps the record.

Add `--field finding=true` when the ruling names a defect in the draft plan that you corrected
before writing code. The run issue then renders it under *Plan review findings* and the PR body
omits it. A finding shows that plan review works. It is not a fact about the code under review.
An unmarked ruling stays a decision, so a forgotten marker costs nothing.

## How to write a decision, a failure, and a PR summary

Plain English: short sentences, active voice, simple tense, concrete verbs. Use the term
`CONTEXT.md` defines. **A `failure` message that quotes tool output keeps that output verbatim** —
simplifying it falsifies it.

A `decision` event carries two fields:

- `text` — the ruling, one sentence. This is what a reader skims.
- `rationale` — the reasoning, one to three sentences. This renders inside a collapsed block.

Neither length is enforced. Never drop a decision, or pad a rationale to fill the cap.

## Retry budgets

| What | Budget | On exhaustion |
|------|--------|---------------|
| BUILD task | 2 attempts | Terminal failure |
| Blocking generic smoketest | 1 differential-guided diagnostic/fix attempt | Terminal failure |
| Evidence scenario | 1 fix attempt | PR ships with a prominent FAILED section |
| Memory budget FAIL | 0 | Abort immediately |

The smoketest diagnostic starts from the **differential report** — the first WRAM divergence
against the reference ROM — never from code inspection. Provision the reference lazily:

```
python tools/factory_cache.py
```

A `verdict` of `scenario-invalid` in `build/smoketest/<name>/results.json` means the scenario is
wrong, not the game: downgrade to a scenario fix. **Read the verdict from the JSON — the exit
code does not distinguish it.**

## Safety rails — never

- Never merge a PR, and never `gh pr merge`.
- Never commit to `master`, and never push to `master`/`main`.
- Never force-push, in any spelling.
- Never pass `--no-verify` to `git commit` or `git push`. If a hook blocks you, fix the cause.
- Never delete or prune a worktree or branch, and never `git reset --hard`.
- Never edit `.claude/settings.local.json`, and never commit it.
- Never create, edit, or comment on a GitHub object with a raw `gh` command. Route it through
  `tools/factory_publish.py`.

The deny gate mechanizes these, and it matches **raw command text** — a diagnostic that merely
quotes a forbidden command is itself refused. Assemble such strings piecewise.

## Terminal failure

1. Append the `failure` event with stage and reason.
2. Write the autopsy bundle (`factory_run.write_autopsy`) — see `references/stages.md`.
3. `python tools/factory_publish.py --issue <N> --terminal` — the run issue becomes the autopsy
   and the spec issue gets exactly one comment linking it.
4. **Leave the worktree and the run state intact.** They are the evidence.

A permission prompt during a run is an allowlist bug (#432 R6), not a run failure: it is
recorded as a `permission` event. Report it; the fix is a tracked-allowlist promotion.
