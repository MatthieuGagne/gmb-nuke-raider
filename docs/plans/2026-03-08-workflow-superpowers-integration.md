# Workflow: Superpowers Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the custom PRD-driven workflow with Superpowers, keeping only GBC-specific skills and infrastructure.

**Architecture:** Delete the four flat skill files, recreate `/build` and `/test` as proper `<name>/SKILL.md` subdirectories, update CLAUDE.md with a Workflow section, add cross-references to the two project agents, and move `docs/prd/` to `docs/plans/`.

**Tech Stack:** Bash, Markdown, CLAUDE.md, `.claude/skills/`, `.claude/agents/`

---

### Task 1: Delete the four flat skill files

**Files:**
- Delete: `.claude/skills/build.md`
- Delete: `.claude/skills/test.md`
- Delete: `.claude/skills/done.md`
- Delete: `.claude/skills/prd.md`

**Step 1: Delete the files**

```bash
rm .claude/skills/build.md .claude/skills/test.md .claude/skills/done.md .claude/skills/prd.md
```

**Step 2: Verify they're gone**

```bash
ls .claude/skills/
```
Expected: empty directory (or no output)

**Step 3: Commit**

```bash
git add -A .claude/skills/
git commit -m "Remove flat custom skills replaced by Superpowers"
```

---

### Task 2: Create `.claude/skills/build/SKILL.md`

**Files:**
- Create: `.claude/skills/build/SKILL.md`

**Step 1: Create the file**

```bash
mkdir -p .claude/skills/build
```

Contents of `.claude/skills/build/SKILL.md`:

```markdown
---
name: build
description: Use this skill to build the GBC ROM. Triggers when verifying a build, checking for compiler errors, or confirming the ROM was produced after making changes.
---

Run `GBDK_HOME=/home/mathdaman/gbdk make`.

On success: report ROM size with `ls -lh build/wasteland-racer.gb`.

On failure: extract lines containing "error:" from the output, show each as
`file:line: message`. Distinguish compiler errors (fixable in source) from
linker errors. Identify which file to look at first. Do not attempt to fix
errors automatically unless the user asks.
```

**Step 2: Verify**

```bash
cat .claude/skills/build/SKILL.md
```
Expected: file with frontmatter `name: build`

**Step 3: Commit**

```bash
git add .claude/skills/build/SKILL.md
git commit -m "Add /build skill in proper SKILL.md format"
```

---

### Task 3: Create `.claude/skills/test/SKILL.md`

**Files:**
- Create: `.claude/skills/test/SKILL.md`

**Step 1: Create the file**

```bash
mkdir -p .claude/skills/test
```

Contents of `.claude/skills/test/SKILL.md`:

```markdown
---
name: test
description: Use this skill to run host-side unit tests. Triggers during TDD red/green cycles, before finishing a development branch, and when verifying logic changes. Tests compile with gcc and mock GBDK headers — no hardware required.
---

Run `make test`.

On success: report "Tests OK — N passed".

On failure: list each failing test with name, file:line, and expected vs
actual values. If compilation fails before tests run, show the gcc error
and identify which mock header or test file needs fixing.

New tests go in `tests/test_*.c` — the Makefile picks them up automatically.
Mock GBDK headers live in `tests/mocks/`.
```

**Step 2: Verify**

```bash
cat .claude/skills/test/SKILL.md
```
Expected: file with frontmatter `name: test`

**Step 3: Run tests to confirm the target still works**

```bash
make test
```
Expected: `2 Tests 0 Failures 0 Ignored — OK`

**Step 4: Commit**

```bash
git add .claude/skills/test/SKILL.md
git commit -m "Add /test skill in proper SKILL.md format"
```

---

### Task 4: Move `docs/prd/` to `docs/plans/`

**Files:**
- Move: `docs/prd/TEMPLATE.md` → `docs/plans/TEMPLATE.md`
- Delete: `docs/prd/` directory

**Step 1: Move the template**

```bash
mv docs/prd/TEMPLATE.md docs/plans/TEMPLATE.md
rmdir docs/prd
```

**Step 2: Update the template header** to say `docs/plans/` instead of `docs/prd/`:

In `docs/plans/TEMPLATE.md`, the file needs no path references changed — it's a content template. Just verify it exists:

```bash
ls docs/plans/
```
Expected: `2026-03-08-workflow-design.md  2026-03-08-workflow-superpowers-integration.md  TEMPLATE.md`

**Step 3: Commit**

```bash
git add -A docs/
git commit -m "Move docs/prd/ to docs/plans/ to align with Superpowers convention"
```

---

### Task 5: Add `## Workflow` section to `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add the section** after the `## Specialized Agents` section:

```markdown
## Workflow

This project uses [Superpowers](https://github.com/obra/superpowers) (installed globally in `~/.claude/`).

**Outer loop:** brainstorming → writing-plans → subagent-driven-development
**TDD red/green command:** `make test` (gcc + Unity, no hardware needed — use `/test` skill)
**Build verification:** `GBDK_HOME=/home/mathdaman/gbdk make` (use `/build` skill)
**Design docs:** saved to `docs/plans/YYYY-MM-DD-<topic>-design.md`
```

**Step 2: Verify CLAUDE.md looks correct**

```bash
tail -15 CLAUDE.md
```
Expected: `## Workflow` section visible at end of file

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "Add Workflow section to CLAUDE.md referencing Superpowers"
```

---

### Task 6: Add cross-references to project agent files

**Files:**
- Modify: `.claude/agents/gbdk-expert.md` (after `## Project Context` block)
- Modify: `.claude/agents/gb-c-optimizer.md` (after `## Project Context` block)

**Step 1: Add to `gbdk-expert.md`** — insert after the Project Context block:

```markdown
## Verification Commands
After making changes, verify with:
- `/test` skill — run `make test` (host-side unit tests, gcc only)
- `/build` skill — run `GBDK_HOME=/home/mathdaman/gbdk make` (full ROM build)
```

**Step 2: Add the same block to `gb-c-optimizer.md`**

**Step 3: Verify both files**

```bash
grep -A4 "Verification Commands" .claude/agents/gbdk-expert.md
grep -A4 "Verification Commands" .claude/agents/gb-c-optimizer.md
```
Expected: both show the verification block

**Step 4: Commit**

```bash
git add .claude/agents/
git commit -m "Add verification command cross-references to project agents"
```

---

### Task 7: Final verification

**Step 1: Confirm skill directory structure**

```bash
find .claude/skills -type f | sort
```
Expected:
```
.claude/skills/build/SKILL.md
.claude/skills/test/SKILL.md
```

**Step 2: Run tests one final time**

```bash
make test
```
Expected: `OK`

**Step 3: Confirm no flat .md files remain in .claude/skills/**

```bash
find .claude/skills -maxdepth 1 -name "*.md"
```
Expected: no output
