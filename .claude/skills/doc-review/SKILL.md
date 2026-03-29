---
name: doc-review
description: "Use instead of writing-plans + executing-plans when implementing a doc-only PRD (no .c/.h files). Trigger on: doc-only, documentation changes, skill file edits, markdown updates. Runs a 4-step checklist then proceeds directly to editing."
---

# Doc-Review Skill

## Purpose

Replace the full `writing-plans` → `executing-plans` pipeline for PRDs whose scope is **entirely doc-only** (no `.c` or `.h` files). This skill skips spec-review and quality-review agents that are overkill for documentation changes.

**Announce at start:** "I'm using the doc-review skill."

---

## Step 1 — Scope Gate (HARD STOP if failed)

List every file to be touched. For each file, write one sentence describing the intended change.

**Rule:** If ANY file in scope has a `.c` or `.h` extension, OR is `bank-manifest.json`, STOP immediately and say:

> "This PRD touches code files. The doc-review skill does not apply. Use the full `writing-plans` → `executing-plans` workflow instead."

Do not proceed past this step if the hard stop triggers.

---

## Step 2 — Cross-File Consistency Check

Scan the list of files from Step 1 for consistency risks:

- Is the same rule, term, or workflow described in more than one file? If so, flag each pair and note which file is authoritative.
- Are there any references between files (e.g., CLAUDE.md pointing to a skill by name) that will break or become stale after the edits?

List all risks found. If none, write "No cross-file consistency risks found."

If any risks are found, resolve them or get explicit user confirmation before proceeding to Step 3.

---

## Step 3 — Worktree Check

**HARD STOP:** If you are not inside a git worktree, enter one now using the `using-git-worktrees` skill or `EnterWorktree` tool. Do not proceed until confirmed.

Branch naming convention: `feat/<short-description>`.

---

## Step 4 — Edit, Commit, PR

Proceed directly to editing — no spec-review agent, no quality-review agent.

Follow the **abbreviated doc-only step sequence** from `CLAUDE.md`:

1. Edit the doc file(s) identified in Step 1
2. Fetch + merge: `git fetch origin && git merge origin/master`
3. Clean build: `make clean && GBDK_HOME=/home/mathdaman/gbdk make`
4. Smoketest: launch ROM in Emulicious; **wait for the user to confirm it looks correct** before continuing
5. Commit: `git add <files> && git commit -m "docs: <message>"`
6. Push branch and create PR with `Closes #N` in the body
