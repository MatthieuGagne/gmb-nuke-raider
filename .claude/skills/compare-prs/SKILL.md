---
name: compare-prs
description: Use when debugging a regression against a known-good historical PR — builds the current branch and one or more historical PRs in parallel worktrees for side-by-side ROM comparison. Also useful for narrowing down which PR introduced a bug by comparing ROMs.
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
