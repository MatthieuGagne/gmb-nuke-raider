# Vendor Unity (Remove Submodule) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the `tests/unity` git submodule with the three vendored source files so worktrees work without `git submodule update --init`.

**Architecture:** Copy `unity.c`, `unity.h`, `unity_internals.h` from the live submodule checkout into `tests/unity/src/` as tracked files, then remove the submodule. Makefile paths are unchanged.

**Tech Stack:** git submodule removal, Unity 2.x (C testing framework)

---

### Task 1: Copy Unity source files out of the submodule

**Files:**
- Create: `tests/unity/src/unity.c` (vendored copy)
- Create: `tests/unity/src/unity.h` (vendored copy)
- Create: `tests/unity/src/unity_internals.h` (vendored copy)

**Step 1: Copy the three files to a temp location outside the repo**

```bash
cp tests/unity/src/unity.c /tmp/unity.c
cp tests/unity/src/unity.h /tmp/unity.h
cp tests/unity/src/unity_internals.h /tmp/unity_internals.h
```

**Step 2: Verify the copies exist and are non-empty**

```bash
wc -l /tmp/unity.c /tmp/unity.h /tmp/unity_internals.h
```

Expected: all three files show hundreds of lines.

---

### Task 2: Remove the submodule

**Files:**
- Delete: `.gitmodules`
- Remove: `tests/unity/` (submodule entry)

**Step 1: Deinit the submodule**

```bash
git submodule deinit -f tests/unity
```

Expected: `Cleared directory 'tests/unity'`

**Step 2: Remove the submodule from the index and working tree**

```bash
git rm -f tests/unity
```

Expected: `rm 'tests/unity'`

**Step 3: Delete the leftover git metadata**

```bash
rm -rf .git/modules/tests/unity
```

**Step 4: Verify `.gitmodules` is gone or empty**

```bash
cat .gitmodules 2>/dev/null || echo "no .gitmodules"
```

Expected: `no .gitmodules`

---

### Task 3: Re-add Unity files as tracked source

**Files:**
- Create: `tests/unity/src/unity.c`
- Create: `tests/unity/src/unity.h`
- Create: `tests/unity/src/unity_internals.h`

**Step 1: Recreate the directory and copy files back**

```bash
mkdir -p tests/unity/src
cp /tmp/unity.c tests/unity/src/unity.c
cp /tmp/unity.h tests/unity/src/unity.h
cp /tmp/unity_internals.h tests/unity/src/unity_internals.h
```

**Step 2: Verify files are present**

```bash
ls -la tests/unity/src/
```

Expected: `unity.c`, `unity.h`, `unity_internals.h` listed.

---

### Task 4: Verify tests still pass

**Step 1: Run the test suite**

```bash
GBDK_HOME=/home/mathdaman/gbdk make test
```

Expected: all tests PASS, no compilation errors.

---

### Task 5: Commit and push

**Step 1: Stage everything**

```bash
git add tests/unity/src/unity.c tests/unity/src/unity.h tests/unity/src/unity_internals.h
git add -u   # picks up .gitmodules removal and submodule entry removal
git status   # verify only expected changes
```

**Step 2: Commit**

```bash
git commit -m "chore: vendor Unity source files, remove git submodule

Replaces tests/unity submodule with vendored unity.c / unity.h /
unity_internals.h. Worktrees no longer need git submodule update --init.
Makefile paths are unchanged."
```

**Step 3: Push and open PR**

```bash
git push -u origin worktree-vendor-unity
gh pr create --title "chore: vendor Unity, remove git submodule" --body "$(cat <<'EOF'
## Summary
- Removes `tests/unity` git submodule
- Vendors `unity.c`, `unity.h`, `unity_internals.h` directly at `tests/unity/src/`
- No Makefile changes needed — paths are identical
- Fixes worktree friction: no more `git submodule update --init` per worktree

## Test plan
- [ ] `make test` passes with vendored files
- [ ] New worktree can run `make test` without any submodule init step

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
