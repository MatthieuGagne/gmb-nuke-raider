# compare-prs + debug Skills Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add two new skills — `/compare-prs` (parallel PR build comparison for regression debugging) and `/debug` (structured hypothesis-driven debugging that shadows `systematic-debugging`).

**Architecture:** Both are doc-only changes: shell script + skill SKILL.md files + CLAUDE.md updates. No `src/` C files are touched. The `/compare-prs` skill orchestrates subagents that each run `tools/compare_prs.sh <N>` in isolated worktrees. The `/debug` skill enforces a ranked hypothesis queue with hard rules (one variable per test, 3-strikes halt) and references `emulicious-debug` and `/compare-prs` as instrumentation tools.

**Tech Stack:** Bash (shell script), Markdown (skill files), `git worktree`, `gh pr checkout`, `GBDK_HOME=/home/mathdaman/gbdk make`

---

## Issue #212 — compare-prs skill + shell script

### Task 1: Create `tools/compare_prs.sh`

**Files:**
- Create: `tools/compare_prs.sh`

**Step 1: Write the script**

```bash
#!/usr/bin/env bash
# compare_prs.sh <PR_NUMBER>
# Checks out a PR into an isolated worktree, clean-builds the ROM.
# Prints ROM path on success, build error on failure. Exits 0/1.

set -euo pipefail

PR="$1"
WORKTREE_DIR="/tmp/pr-compare-${PR}"
REPO_ROOT="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"

# Clean up any stale worktree for this PR
if [ -d "$WORKTREE_DIR" ]; then
  git -C "$REPO_ROOT" worktree remove --force "$WORKTREE_DIR" 2>/dev/null || true
  rm -rf "$WORKTREE_DIR"
fi

# Create worktree and checkout PR branch
git -C "$REPO_ROOT" worktree add "$WORKTREE_DIR" HEAD 2>/dev/null
cd "$WORKTREE_DIR"

# Fetch and checkout the PR branch into the worktree
gh pr checkout "$PR" --repo MatthieuGagne/gmb-nuke-raider 2>/dev/null || {
  echo "ERROR: Could not checkout PR #${PR}" >&2
  git -C "$REPO_ROOT" worktree remove --force "$WORKTREE_DIR" 2>/dev/null || true
  exit 1
}

# Verify CWD is the worktree directory (safety check)
ACTUAL_DIR="$(pwd)"
if [ "$ACTUAL_DIR" != "$WORKTREE_DIR" ]; then
  echo "ERROR: CWD mismatch — expected $WORKTREE_DIR, got $ACTUAL_DIR" >&2
  exit 1
fi

# Clean build
if make clean && GBDK_HOME=/home/mathdaman/gbdk make; then
  echo "ROM:${WORKTREE_DIR}/build/nuke-raider.gb"
  exit 0
else
  echo "ERROR: Build failed for PR #${PR}" >&2
  exit 1
fi
```

**Step 2: Make it executable**

```bash
chmod +x tools/compare_prs.sh
```

**Step 3: Manual smoke-test (single PR)**

```bash
cd /home/mathdaman/code/nuke-raider/.claude/worktrees/chore+compare-prs-and-debug-skills
bash tools/compare_prs.sh 206
```
Expected: output line starting with `ROM:` and exit 0 (or `ERROR:` and exit 1 if PR is already merged/gone — either is acceptable for this step).

**Step 4: Commit**

```bash
git add tools/compare_prs.sh
git commit -m "feat: add tools/compare_prs.sh — single-PR worktree build worker"
```

---

### Task 2: Create `.claude/skills/compare-prs/SKILL.md`

**Files:**
- Create: `.claude/skills/compare-prs/SKILL.md`

**Step 1: Write the skill**

```markdown
---
name: compare-prs
description: Use when debugging a regression against a known-good historical PR — builds the current branch and one or more historical PRs in parallel worktrees for side-by-side ROM comparison. Also useful for bisecting: narrow down which PR introduced a bug by comparing ROMs.
---

# compare-prs — Parallel PR Build Comparison

## When to Use

- You suspect a regression: something worked in a previous PR but is broken now
- You want to compare the built ROM from two or more PRs side-by-side in Emulicious
- The `/debug` skill identifies a "worked in PR X, broken now" hypothesis

## Usage

```
/compare-prs <PR1> <PR2> [PR3 ...]
```

Example: `/compare-prs 195 193 192`

---

## Process

### Step 1: Dispatch parallel subagents

In a **single Agent tool call message**, dispatch one subagent per PR. Each subagent runs:

```bash
bash tools/compare_prs.sh <N>
```

The subagent reports back: `ROM:<path>` on success, `ERROR:<message>` on failure.

Do NOT run subagents sequentially. All must be dispatched in one message.

### Step 2: Collect results and show summary table

Wait for all subagents to complete, then display:

| PR # | Result |
|------|--------|
| 195  | `/tmp/pr-compare-195/build/nuke-raider.gb` |
| 193  | `/tmp/pr-compare-193/build/nuke-raider.gb` |
| 192  | ERROR: Build failed |

### Step 3: Ask which ROM to open first

Ask the user: "Which PR's ROM would you like to launch first?"

Then open it in Emulicious **from the worktree directory** so the path resolves correctly:

```bash
cd /tmp/pr-compare-<N>
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
```

Repeat for any additional ROMs the user wants to test.

### Step 4: Clean up

After the user is done comparing, remove all worktrees created during this session:

```bash
# For each PR N that was checked out:
git worktree remove --force /tmp/pr-compare-<N>
rm -rf /tmp/pr-compare-<N>
```

---

## Notes

- Parallelism is skill-side (subagents), not shell-side (`&` background processes)
- The script handles stale worktree cleanup automatically on re-run
- If a PR branch is gone (merged/deleted), the script exits 1 with a clear error — report it in the table and skip that ROM
- Always launch Emulicious **from the worktree directory** (`cd /tmp/pr-compare-<N>` first)
```

**Step 2: Commit**

```bash
git add .claude/skills/compare-prs/SKILL.md
git commit -m "feat: add .claude/skills/compare-prs — parallel PR build comparison skill"
```

---

### Task 3: Update CLAUDE.md — add compare-prs to Skills section

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add compare-prs entry under the Skills section**

Find the Skills section listing in CLAUDE.md and add this entry alongside the other skill descriptions:

```markdown
- **`compare-prs`** — Parallel PR build comparison for regression debugging. Builds the current branch + historical PRs in isolated worktrees simultaneously, presents a summary table, and opens ROMs in Emulicious for side-by-side comparison. Referenced by `/debug` for "worked in PR X, broken now" hypotheses.
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "chore: add compare-prs skill to CLAUDE.md skills listing  Closes #212"
```

---

## Issue #213 — debug skill (shadows systematic-debugging)

### Task 4: Create `.claude/skills/debug/SKILL.md`

**Files:**
- Create: `.claude/skills/debug/SKILL.md`

**Step 1: Write the skill**

```markdown
---
name: debug
description: Use when encountering any bug, test failure, or unexpected behavior — before proposing fixes. Enforces hypothesis-queue-first debugging with hard rules against fixation and cascading regressions. Shadows global systematic-debugging with GBC-specific tooling and a 3-strikes halt rule.
---

# debug — Structured Hypothesis-Driven Debugging

## The Iron Law

```
NO FIXES WITHOUT A VISIBLE, APPROVED HYPOTHESIS QUEUE FIRST
```

**Never touch code, instrument, or propose a fix until:**
1. You have a ranked list of hypotheses
2. The user has approved that list
3. You have stated which hypothesis you are currently testing

---

## Entry Modes

### Mode A: Start of Session

Use when beginning a new bug investigation.

Ask the user (one question at a time):
1. "What is the GitHub issue number for this bug?"
2. "Describe the symptom in one sentence: what do you observe, and when?"
3. "Which hypotheses have you already ruled out? (list them, or say 'none')"

Then:

**Generate a ranked hypothesis queue** — ordered most-likely to least-likely. Format:

```
Hypothesis Queue (pending user approval):
1. [Most likely] <hypothesis> — reasoning: <why>
2. [Likely]      <hypothesis> — reasoning: <why>
3. [Possible]    <hypothesis> — reasoning: <why>
...

Ruled out (will not re-test): <list from user>
```

**STOP. Show queue to user. Do not proceed until they approve.**

If the user asks to reorder or add/remove hypotheses, update and show again.

### Mode B: Mid-Session Interrupt

Use when already mid-investigation and going in circles, or when the user types `/debug` to reset.

1. **Snapshot current state** — state out loud:
   - Active hypothesis: X
   - Attempt count: N
   - Observations so far: (list)
2. **Halt current hypothesis** — do not make any further changes for it
3. **Re-enumerate** remaining untested hypotheses (updated with any new observations)
4. **Pick next highest-probability** and confirm with user before proceeding

---

## Per-Hypothesis Loop

For each hypothesis in the queue:

**Before touching anything:**
- State: "Testing hypothesis N: <text>"
- State: "Instrumentation plan: <exactly what I will add/change to test this>"
- Wait for implicit or explicit user go-ahead

**Then:**
1. Add instrumentation (use `emulicious-debug` skill for GBC runtime inspection)
2. Build: `make clean && GBDK_HOME=/home/mathdaman/gbdk make`
3. Run: launch ROM in Emulicious, observe output/behavior
4. Conclude: one of:
   - **Confirmed** — hypothesis is the root cause, proceed to fix
   - **Ruled out** — add to ruled-out list, advance queue
   - **Inconclusive** — refine instrumentation, count as attempt

---

## Hard Rules

| Rule | Detail |
|------|--------|
| Never re-test a ruled-out hypothesis | Once ruled out, it stays ruled out |
| One variable per test | Never make two changes between test runs |
| 3-strikes halt | After 3 consecutive failed/inconclusive attempts on ANY hypothesis: halt, post findings to the GitHub issue, ask user for direction |

### 3-strikes action

When triggered:
1. Post a findings comment to the GitHub issue:
   ```bash
   gh issue comment <N> --repo MatthieuGagne/gmb-nuke-raider --body "..."
   ```
   Include: symptom, all tested hypotheses + outcomes, current observations, what remains untested
2. Say: "I've hit 3 consecutive inconclusive attempts. Findings posted to issue #N. What direction would you like to take?"
3. Do NOT push forward

---

## Instrumentation Tools

- **`emulicious-debug`** skill — step-through debugger, EMU_printf, memory/tile/sprite inspection, tracer, profiler
- **`/compare-prs <N>`** skill — for "worked in PR X, broken now" hypotheses: builds both, lets you compare ROMs and diffs side-by-side

---

## Notes

- Motivation: the ~33s stall bug investigation spanned 5+ sessions. Claude fixated on music/order_cnt, introduced a worse crash (26s stall), and dismissed the new symptom as the known issue. This skill prevents all three failure modes.
- Stateless across sessions — each invocation starts from what the user provides in Mode A
- This skill shadows the global `systematic-debugging` skill for this project
```

**Step 2: Commit**

```bash
git add .claude/skills/debug/SKILL.md
git commit -m "feat: add .claude/skills/debug — hypothesis-driven debugging skill (shadows systematic-debugging)"
```

---

### Task 5: Update CLAUDE.md — add debug to Project-local shadows section

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add debug entry under "Project-local shadows/extensions" section**

Find the section that starts with `### Project-local shadows/extensions of global superpowers skills` and add:

```markdown
- **`debug`** — Shadows superpowers:systematic-debugging; adds hypothesis-queue-first workflow (user approves queue before any code touch), mid-session interrupt mode, GBC instrumentation via `emulicious-debug`, `/compare-prs` reference for regression hypotheses, and 3-strikes halt rule (post findings to GitHub issue and stop).
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "chore: add debug skill shadow to CLAUDE.md  Closes #213"
```

---

## Final Gate: Smoketest

After all tasks are committed:

1. Fetch and merge latest master:
   ```bash
   git fetch origin && git merge origin/master
   ```
2. Clean build:
   ```bash
   make clean && GBDK_HOME=/home/mathdaman/gbdk make
   ```
3. Launch ROM in Emulicious (from the worktree directory):
   ```bash
   java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/nuke-raider.gb
   ```
4. Confirm with user that the ROM runs correctly (doc-only change — should be identical to master)
5. Push branch and create PR with `Closes #212` and `Closes #213` in body
