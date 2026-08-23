---
name: finishing-a-development-branch
baseline: superpowers@6.3.0
---

Project (Nuke Raider) additions and overrides for the baseline finishing-a-development-branch
skill. On conflict, this overlay wins — but an override earns that only by stating what the
baseline cannot know (#527 R7).

**Baseline audit:** content of `superpowers@6.3.0` read and compared on 2026-08-22 (#527 R6).
6.3.0's only change here: a new block on **refused worktree removal** — when
`git worktree remove` reports `contains modified or untracked files`, never `--force` on your
own initiative; show the `git status --porcelain -uall` output and offer commit / move / delete.
`### Cleanup failure recovery` below now defers to it.

## Overrides (do NOT follow the baseline here)

- **Never offer "merge to main locally."** All work integrates via PR. Present exactly two
  options: (1) push and create a Pull Request ← default, (2) keep the branch as-is. Keep them
  concise, no added explanation. **Discarding the work is not a menu option** — it happens only
  when the user asks for it in so many words, and then only after they type `discard`.
  **Why:** `master` is protected and branch protection is `strict`, so the baseline's Option 1
  cannot succeed here — offering it wastes a decision the repo has already made. The discard
  rule is the baseline's own and is restated because an earlier version of this overlay put
  discard in the menu, which the baseline explicitly forbids.
- **Never commit directly to `master`.**
  **Why:** project branch policy; the baseline's Option 1 would otherwise write to it.
- **The worktree-cleanup reference now lives at `.claude/skill-overlays/references/cleanup.md`** — not under the skill's own `references/` directory. It holds the full cleanup fallback ladders and per-option triggers.
  **Why:** this project's worktrees live under `.claude/worktrees/`, outside the `.worktrees/` /
  `worktrees/` paths the baseline is willing to clean, and the Windows removal failures in that
  reference have no upstream equivalent.

## Project additions

### Before anything else: fetch + merge, and review the bank manifest

**Why:** the baseline verifies tests on the branch as-is; it never syncs with the base branch,
and it has no concept of a bank manifest. Branch protection here is `strict`, so an out-of-date
branch cannot merge at all.

Run these two as a concurrent batch:

- **Fetch and merge latest master** — mandatory, always, even for doc-only branches:
  ```bash
  git fetch origin && git merge origin/master
  ```
  Never use bare `git merge master` — the local master ref may be stale and silently merges old code. Resolve any conflicts and commit the merge before pushing.
- **Bank manifest review** (read-only, no merge dependency): check `bank-manifest.json` against the branch's `src/*.c` files — every `src/*.c` file must have an entry. A missing entry is a blocker.

Wait for both before verifying tests.

### Verify tests against the merged state

**Why:** the baseline's own rationalization table says a green run only proves the tree it ran
on — this names *which* tree that must be here: the merged one.

Run `make test` **after** the merge, so tests execute against merged code. If tests fail, stop — do not proceed toward merge or PR until they pass.

### HARD GATE — the bank budgets must have reported clean

**Why:** an undetected bank overflow shows up as a blank screen or ~1–2 FPS, not as a test
failure — the baseline's test gate cannot see it.

`bank-post-build` and `make memory-check` fire automatically as PostToolUse hooks after a build.
Do not invoke them by hand (#527 R4): **read the hook output from the build** and treat any FAIL
as blocking. If no hook output exists because no build ran in this session, run
`make clean && make` first — the smoketest gate below requires it anyway.

### Smoketest gate — NEVER push or create a PR before it passes

**Why:** the deliverable is a Game Boy ROM. Nothing in the baseline's flow proves it boots, and
a green test suite regularly coexists with a black screen.

Skip only for doc-only branches with no `src/*.c`, `src/*.h`, or asset changes.

1. Always do a clean build (master is already merged): `make clean && make`
2. Read the `make memory-check` hook output. Any budget FAIL or ERROR → stop and fix.
3. **Ask the user for confirmation before launching the ROM.** If they confirm, launch via the **PowerShell tool** (not Bash — Bash exits silently without showing the window on Windows), from the **worktree** directory, never the main repo's `build/`:
   ```powershell
   Start-Process -FilePath "java" -ArgumentList "-jar", "C:\Tools\Emulicious\Emulicious.jar", "build\nuke-raider.gb" -PassThru
   ```
4. Ask the user to confirm it looks correct. **Stop and wait for explicit confirmation.** Issues found → fix with the user before continuing.

Never use `mgba-qt` (wrong emulator) or reference `wasteland-racer.gb` (wrong ROM name).

### Factory mode

**Why:** the factory runs unattended, so the baseline's menu — which exists to hand the
integration decision to a human — has no one to ask; that decision was made when the run started.

Active when `NUKE_FACTORY_RUN` is set — i.e. the SHIP stage of a `/factory` run. It **overrides
`### Smoketest gate` step 3-4 above** and the baseline's end-of-branch option menu.

- Steps 1-2 of the smoketest gate (clean build, `make memory-check`) still run. A memory FAIL
  still stops everything.
- Step 3-4 — "ask the user for confirmation before launching the ROM", then "stop and wait for
  explicit confirmation" — are replaced by the headless gate, already run by VERIFY:
  `python tools/smoketest_headless.py --scenario generic-smoke --json`. Do not launch Emulicious.
- The baseline's end-of-branch **option menu does not apply. The action is always push + PR**,
  with the body rendered by `python tools/factory_report.py --issue <N>`. Do not ask which
  option the user wants.
- `### Update docs before the PR` still applies in full, including the README rule and the
  allowlist-promotion rule.
- `### PR conventions` still applies, except: do not ask the user to confirm the merge. **Report
  the PR URL and stop.**
- `### Never` still applies in full, and factory mode adds two: never `--no-verify`, and never
  delete or prune the worktree or branch. The worktree is the run's evidence.

Outside a factory run every confirmation above fires exactly as written.

### Update docs before the PR

**Why:** the baseline's Option 2 goes straight from push to PR. These three co-authoritative
documents are this project's, and each has silently drifted before.

- **Any user-visible behavior changed** (new feature, changed controls, new screen, new module) → update the **Game Modules table** in `README.md`.
- **Any `.claude/skills/`, `.claude/agents/`, `.claude/skill-overlays/`, or `CLAUDE.md` file changed** → update `docs/dev-workflow.md` in the same PR. The two are co-authoritative and must agree.
- **Any new tool permission approved this session** → promote it into the tracked `.claude/settings.json` as a generalized rule in its tool's canonical form (`Bash(prefix:*)`, `PowerShell(prefix *)`), or discard it. Never commit `.claude/settings.local.json` — it is gitignored scratch. Validate with `python tools/allowlist_lint.py`. See [ADR 443](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/466).

### PR conventions

**Why:** the baseline says to use "the forge's tooling" and to follow the repo's PR conventions
without knowing what they are. This is what they are here.

Use `gh` for push and all GitHub operations (`gh auth setup-git` if push fails on credentials).

Always create a PR after pushing a branch — no need to ask. PR body:

```markdown
## Summary
<2-3 bullets of what changed>

## Test Plan
- [ ] make test passes
- [ ] Emulicious smoketest confirmed by user
- [ ] post-build gates reported clean: no FAIL banks, no FAIL/ERROR memory budgets

Closes #N
```

`Closes #N` auto-closes the linked issue on merge. After the PR is created, report the URL and tell the user the worktree path, asking them to confirm when it is merged. **Do NOT clean up the worktree at PR-creation time** — wait for merge confirmation, which is the baseline's rule too. Once merged, verify the linked issue actually closed; if not, `gh issue close N`.

### Cleanup failure recovery

**Why:** every trap below is Windows- or `EnterWorktree`-specific. The baseline's two-command
cleanup assumes a POSIX shell and a worktree it owns.

Full ladders are in `.claude/skill-overlays/references/cleanup.md`. The three recurring traps —
all **mechanical** failures, distinct from the baseline's `contains modified or untracked files`
refusal, which is a *content* refusal and is handled by the baseline's ask-first block, not here:

- Bash blocked with "Path does not exist" after merge → the session is inside an active `EnterWorktree`; use `ExitWorktree(action="remove", discard_changes=true)` first.
- `git worktree remove` fails with "Unable to read current working directory" → `cd C:/Code/nuke-raider` before any `git worktree remove`.
- `git worktree remove --force` fails with "is not a working tree" → the directory is already gone; fall back to `rm -rf <path> && git worktree prune`.

**`--force` is never this overlay's idea.** The only `--force` below is the discard path, where
the user has already typed `discard` and authorized the loss. For any other refusal, follow the
baseline: show the file list and ask.

To discard a branch — **only after the user has typed `discard`**, per the baseline — remove the worktree first, then delete the branch from the main repo:
```powershell
cd C:/Code/nuke-raider
GIT_DIR=C:/Code/nuke-raider/.git GIT_WORK_TREE=C:/Code/nuke-raider git worktree remove --force <worktree-path>
git -C C:/Code/nuke-raider branch -D <feature-branch>
```

### Never

**Why:** the first two restate baseline rules that have been broken here anyway; the last three
are project-specific and have no upstream equivalent.

- Proceed with failing tests, or skip test verification before offering options.
- Delete work without typed confirmation, or force-push without an explicit request.
- Launch the emulator from the main repo's `build/`.
- Push without fetching and merging first — even doc-only branches can conflict.
- Skip the doc updates when skills, agents, overlays, or `CLAUDE.md` changed.
