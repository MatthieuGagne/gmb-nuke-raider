# Debug Notes: feat-dialog-border-tiles blank screen (0 FPS)

## Status: ROOT CAUSE FOUND — fix pending

## Symptom
Feature ROM shows blank screen at 0 FPS. Master ROM (without dialog_border_tiles) works fine.

## Root Cause
`dialog_border_tiles.c` was autobanked (bank 255 → bank 1). Adding its 129 bytes pushed
`player_tile_data` (player_sprite.c) from bank 1 to bank 2 in the feature build.

Bank-1 code (`player.c`, `track.c`) calls `SET_BANK(player_tile_data)` to reach the tile data.
When `player_tile_data` was in bank 1, `SET_BANK(1)` from bank-1 code was a no-op (safe).
After the push, `SET_BANK(player_tile_data)` = `SET_BANK(2)` from bank-1 code → switches the
switchable window (0x4000–0x7FFF) to bank 2, unmapping the running bank-1 code → CPU crash.

This is **exactly** the scenario described in the Makefile for portrait pinning:
```
# Rationale: bankpack fills bank 1 first; portraits would land in bank 1 and
# push track_tile_data / player_tile_data to bank 2. track_init() and
# player_init() are BANKED functions in bank 1 that call SET_BANK() to reach
# those assets — SET_BANK inside a banked function in the switchable window
# (0x4000-0x7FFF) unmaps the executing code and crashes.
```

## Evidence From Map Files

Master ROM map (`build/nuke-raider.map` on master branch):
```
___bank_d = 2  → dialog_arrow_sprite in bank 2 (only 17 bytes, didn't fit bank 1)
___bank_n = 2  (×3) → npc portraits in bank 2
___bank_p = 1  → player_sprite IN BANK 1 (safe!)
Bank 1 = 16370 bytes, Bank 2 = 788 bytes
```

Feature ROM map (`.worktrees/feat-dialog-border-tiles/build/nuke-raider.map`):
```
___bank_d = 1  (×2) → dialog_arrow_sprite AND dialog_border_tiles both in bank 1
___bank_n = 2  (×3) → npc portraits still bank 2
___bank_p = 2  → player_sprite PUSHED TO BANK 2 (CRASH!)
Bank 1 = 16370 bytes (same — bankpack rearranged to keep 1 full)
Bank 2 = 917 bytes (portraits 788 + player_sprite delta)
```

The 17-byte `dialog_arrow_sprite` moved from bank 2 → bank 1.
The 129-byte `dialog_border_tiles` is new to bank 1.
The ~146-byte delta of `player_sprite` (+ maybe `track_tiles`) moved bank 1 → bank 2.
Net: bank 1 unchanged at 16370, bank 2 grew by 129.

## Fix
Pin `dialog_border_tiles.c` to bank 2 (same strategy as NPC portraits).

Changes needed:
1. `bank-manifest.json`: change `dialog_border_tiles.c` from bank 255 → bank 2
2. Regenerate `src/dialog_border_tiles.c` with `--bank 2` flag  
3. Update `Makefile` rule: `--bank 255` → `--bank 2`
4. `src/dialog_border_tiles.h`: update `BANKREF_EXTERN` (no change needed — it's generic)

Also wanted by user (separate fix):
- `tools/bank_post_build.py`: FAIL (not WARN) when bank is at 100% capacity

## Key Rule (from Makefile comment — must be followed for all future asset files)
Autobank fills bank 1 first. Any file that can push `player_tile_data` or `track_tile_data`
out of bank 1 MUST be pinned to bank 2 or higher. Specifically, large data files should
always check remaining bank-1 capacity before defaulting to autobank.

## Verification Plan After Fix
1. Rebuild with fixed manifest + pragma + Makefile
2. Check map: `___bank_dialog_border_tiles` must = 2
3. Check map: `___bank_p` (player_sprite) must = 1 (back to bank 1)
4. `make bank-post-build` — should pass
5. Launch ROM, confirm no blank screen

---

## Second Bug: set_bkg_tiles border accidentally reverted (commit 9825213)

### Symptom
Game worked (no blank screen) but dialog box still showed ASCII `+----+` borders.

### Root Cause
The banking-fix commit (`9825213`) staged and committed a stale version of `state_hub.c`.

Timeline:
1. Task 9 (commit 639a8bc) correctly replaced ASCII printf border with set_bkg_tiles calls.
2. Debugging the blank-screen bug, someone ran `git checkout 1ee0f7c -- .` which staged
   ALL files from the master commit (the old ASCII version of state_hub.c got staged).
3. The recovery used `git reset HEAD && git checkout -- .` but the staged state_hub.c
   (ASCII version) was left in the index.
4. `git status` showed `state_hub.c` under "Changes to be committed" — the old ASCII version.
5. Our banking-fix `git add` didn't include state_hub.c explicitly, but because it was
   already staged, it got swept up in the commit → reverted the set_bkg_tiles work.

### How to detect this earlier
- Always check `git diff --cached` (staged changes) before committing, not just `git status`.
- `git status` showed state_hub.c in "Changes to be committed" — that was the warning sign.
- `git diff origin/master -- src/state_hub.c` only showed a small diff (missing the 42-line
  set_bkg_tiles block) — should have been suspicious that Task 9 changes weren't there.

### Fix
`git show 639a8bc:src/state_hub.c > src/state_hub.c` to restore the correct version,
then re-committed (commit 1f45ff8).

### Prevention Rule
**After any git recovery operation (reset, checkout, restore), always run:**
```bash
git diff --cached   # show what is STAGED (about to be committed)
git diff            # show what is UNSTAGED
```
A file appearing in "Changes to be committed" with wrong content is a red flag.
