# hUGEDriver Music Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add looping background music via hUGEDriver v6.1.3, playing a placeholder song across all game states.

**Architecture:** Vendor hUGEDriver header + prebuilt lib into `lib/hUGEDriver/`. Song data lives in `src/music_data.c` (banked, `#pragma bank 255`). `src/music.c` lives in **bank 0** (no pragma) because `music_tick()` calls `SET_BANK` — a macro that issues `SWITCH_ROM`, which would remap the CPU's own code out from under itself if that code were in a switched bank. `music_init()` enables the APU and calls `hUGE_init` under `__critical`. `music_tick()` wraps `hUGE_dosound` with the music data bank switched in and is called directly from `vbl_isr` in `main.c`.

**Tech Stack:** GBDK 4.x, hUGEDriver v6.1.3, SDCC/SM83, MBC1 autobanking

---

## Background: hUGEDriver API

- `void hUGE_init(const hUGESong_t *song)` — initialize driver with song; call inside `__critical`
- `void hUGE_dosound(void)` — advance one tick; call exactly once per VBlank while music bank is switched in
- APU must be enabled before `hUGE_init`: `NR52_REG = 0x80; NR51_REG = 0xFF; NR50_REG = 0x77;`
- `hUGEDriver.lib` is a prebuilt GBDK library; it links into bank 0 (fixed ROM, always accessible)
- `hUGEDriver.h` uses `#include <gbdk/platform.h>` — valid in GBDK 4.x

## Critical Banking Rule for music.c

`SET_BANK(x)` expands to inline `SWITCH_ROM(BANK(x))`. If `music_tick()` lives at address 0x4000–0x7FFF (a switched bank), calling `SET_BANK` remaps that window to the data bank and the CPU immediately executes garbage bytes. Therefore:
- `music.c` has **no `#pragma bank 255`** — it stays in bank 0 (0x0000–0x3FFF, always mapped)
- `music.h` does **not** use `BANKED` on these functions
- `music_data.c` uses `#pragma bank 255` as normal (its code is only ever called while its bank is already active)

---

### Task 1: Create worktree

Already done — this plan is being written inside `feat/hugedriver-music`.

---

### Task 2: Vendor hUGEDriver files

**Files:**
- Create: `lib/hUGEDriver/include/hUGEDriver.h`
- Create: `lib/hUGEDriver/gbdk/hUGEDriver.lib`

**Step 1: Download the release zip**

```bash
wget -q https://github.com/SuperDisk/hUGEDriver/releases/download/v6.1.3/hUGEDriver-6.1.3.zip \
     -O /tmp/hUGEDriver.zip
```

**Step 2: Extract the two needed files**

```bash
mkdir -p lib/hUGEDriver/include lib/hUGEDriver/gbdk
unzip -j /tmp/hUGEDriver.zip include/hUGEDriver.h -d lib/hUGEDriver/include/
unzip -j /tmp/hUGEDriver.zip gbdk/hUGEDriver.lib   -d lib/hUGEDriver/gbdk/
```

**Step 3: Verify**

```bash
ls lib/hUGEDriver/include/hUGEDriver.h lib/hUGEDriver/gbdk/hUGEDriver.lib
```
Expected: both files listed, no errors.

**Step 4: Commit**

```bash
git add lib/
git commit -m "chore: vendor hUGEDriver v6.1.3 (header + prebuilt lib)"
```

---

### Task 3: Update Makefile

**Files:**
- Modify: `Makefile`

**Step 1: Inspect current CFLAGS and link line**

Open `Makefile`. The current lines are:
```makefile
CFLAGS    := -Wa-l -Wl-m -Wl-j -Wm-ya4 -autobank -Wb-ext=.rel
...
$(TARGET): $(OBJS) | build
	$(LCC) $(CFLAGS) $(ROMFLAGS) -o $@ $(OBJS)
```

**Step 2: Add include path to CFLAGS and lib to link step**

Edit `Makefile`:

1. Append `-Ilib/hUGEDriver/include` to `CFLAGS`:
```makefile
CFLAGS    := -Wa-l -Wl-m -Wl-j -Wm-ya4 -autobank -Wb-ext=.rel -Ilib/hUGEDriver/include
```

2. Add the library to the ROM link rule using `-Wl-k`/`-Wl-l` (NOT as a positional arg — bankpack would corrupt it):
```makefile
$(TARGET): $(OBJS) | build
	$(LCC) $(CFLAGS) $(ROMFLAGS) -o $@ $(OBJS) -Wl-k$(CURDIR)/lib/hUGEDriver/gbdk -Wl-lhUGEDriver.lib
```

**Step 3: Verify build still works (no music yet)**

```bash
GBDK_HOME=/home/mathdaman/gbdk make
```
Expected: `build/junk-runner.gb` produced, no errors. The `-I` flag is new but harmless until music headers are included.

**Step 4: Commit**

```bash
git add Makefile
git commit -m "build: add hUGEDriver include path and lib to Makefile"
```

---

### Task 4: Create src/music_data.h

**Files:**
- Create: `src/music_data.h`

**Step 1: Write the header**

```c
#ifndef MUSIC_DATA_H
#define MUSIC_DATA_H

#include <gb/gb.h>
#include "banking.h"
#include "hUGEDriver.h"

BANKREF_EXTERN(music_data_song)
extern const hUGESong_t music_data_song;

#endif /* MUSIC_DATA_H */
```

No step to run tests — this is a header-only declaration. It will be verified at build time in Task 6.

**Step 2: Commit**

```bash
git add src/music_data.h
git commit -m "feat: add music_data.h with BANKREF_EXTERN for song data"
```

---

### Task 5: Create src/music_data.c (placeholder song)

This task adapts the hUGEDriver sample song into the project's banked format.

**Files:**
- Create: `src/music_data.c`

**Step 1: Download sample_song.c from hUGEDriver**

```bash
wget -q https://raw.githubusercontent.com/SuperDisk/hUGEDriver/master/gbdk_example/src/sample_song.c \
     -O /tmp/sample_song.c
```

**Step 2: Copy and adapt into src/music_data.c**

The original file starts with:
```c
#include "hUGEDriver.h"
#include <stddef.h>
```
And ends with:
```c
const hUGESong_t sample_song = { ... };
```

Create `src/music_data.c` by:
1. Replacing the top includes with the banking boilerplate
2. Renaming `sample_song` → `music_data_song` everywhere (one occurrence at the end)

The file should begin with:
```c
#pragma bank 255
#include <gb/gb.h>
#include <stddef.h>
#include "banking.h"
#include "hUGEDriver.h"

BANKREF(music_data_song)
```
Then all the static data arrays from the downloaded file (unchanged), then:
```c
const hUGESong_t music_data_song = {
    /* same initializer as sample_song, just renamed */
    ...
};
```

**Concrete command to do this:**
```bash
# Add banking header at top, then original file with include swapped and name changed
{
  printf '#pragma bank 255\n'
  printf '#include <gb/gb.h>\n'
  printf '#include <stddef.h>\n'
  printf '#include "banking.h"\n'
  printf '#include "hUGEDriver.h"\n'
  printf '\nBANKREF(music_data_song)\n\n'
  # Drop original includes (first 2 lines of sample_song.c)
  tail -n +3 /tmp/sample_song.c
} > src/music_data.c

# Rename sample_song → music_data_song (only the final exported symbol)
sed -i 's/const hUGESong_t sample_song/const hUGESong_t music_data_song/' src/music_data.c
```

**Step 3: Verify the file starts and ends correctly**

```bash
head -10 src/music_data.c
tail -10 src/music_data.c
```
Expected head:
```
#pragma bank 255
#include <gb/gb.h>
#include <stddef.h>
#include "banking.h"
#include "hUGEDriver.h"

BANKREF(music_data_song)
```
Expected tail: contains `const hUGESong_t music_data_song = {` and closing `};`.

**Step 4: Commit**

```bash
git add src/music_data.c
git commit -m "feat: add banked placeholder song data (hUGEDriver sample)"
```

---

### Task 6: Create src/music.h and src/music.c

**Files:**
- Create: `src/music.h`
- Create: `src/music.c`

**Step 1: Write src/music.h**

```c
#ifndef MUSIC_H
#define MUSIC_H

/* music_init() — enable APU and start the song. Call once in main() before
 * the game loop, after hardware init. */
void music_init(void);

/* music_tick() — advance the music driver by one tick. Must be called exactly
 * once per VBlank from vbl_isr(). */
void music_tick(void);

#endif /* MUSIC_H */
```

Note: No `BANKED` annotation — these functions live in bank 0 (see "Critical Banking Rule" above).

**Step 2: Write src/music.c**

```c
/* music.c — hUGEDriver wrapper.
 *
 * IMPORTANT: This file intentionally omits #pragma bank 255.
 * music_tick() calls SET_BANK (inline SWITCH_ROM). If this code were in a
 * switched bank, SWITCH_ROM would remap the CPU's own instructions out from
 * under itself → undefined behavior. Keep this file in bank 0.
 */
#include <gb/gb.h>
#include <gb/hardware.h>
#include "banking.h"
#include "hUGEDriver.h"
#include "music_data.h"
#include "music.h"

void music_init(void) {
    NR52_REG = 0x80;  /* enable APU */
    NR51_REG = 0xFF;  /* route all channels to both speakers */
    NR50_REG = 0x77;  /* max master volume */
    __critical {
        { SET_BANK(music_data_song);
          hUGE_init(&music_data_song);
          RESTORE_BANK(); }
    }
}

void music_tick(void) {
    { SET_BANK(music_data_song);
      hUGE_dosound();
      RESTORE_BANK(); }
}
```

**Step 3: Build to verify compilation**

```bash
GBDK_HOME=/home/mathdaman/gbdk make 2>&1 | grep -i "error\|warning" | grep -v "so said EVELYN"
```
Expected: no errors. The "so said EVELYN" warning from SDCC is harmless and filtered.

**Step 4: Commit**

```bash
git add src/music.h src/music.c
git commit -m "feat: add music_init() and music_tick() wrappers for hUGEDriver"
```

---

### Task 7: Wire music into main.c

**Files:**
- Modify: `src/main.c:1-59`

**Step 1: Read current main.c**

The current file is:
```c
#include <gb/gb.h>
#include <gb/cgb.h>
#include "camera.h"
...
static void vbl_isr(void) {
    frame_ready = 1;
    move_bkg(0, (uint8_t)cam_y);
}

void main(void) {
    DISPLAY_OFF;
    init_palettes();
    player_init();
    add_VBL(vbl_isr);
    set_interrupts(VBL_IFLAG);
    DISPLAY_ON;
    state_manager_init();
    state_push(&state_title);
    while (1) { ... }
}
```

**Step 2: Add include**

Add `#include "music.h"` after the other local includes (after `"state_title.h"`):
```c
#include "state_title.h"
#include "music.h"
```

**Step 3: Add music_tick() call to vbl_isr**

```c
static void vbl_isr(void) {
    frame_ready = 1;
    move_bkg(0, (uint8_t)cam_y);
    music_tick();
}
```

**Step 4: Add music_init() call in main()**

Call `music_init()` before `add_VBL(vbl_isr)` (so the driver is ready before interrupts fire):
```c
void main(void) {
    DISPLAY_OFF;

    init_palettes();
    player_init();
    music_init();
    add_VBL(vbl_isr);
    set_interrupts(VBL_IFLAG);

    DISPLAY_ON;
    ...
}
```

**Step 5: Build to verify**

```bash
GBDK_HOME=/home/mathdaman/gbdk make 2>&1 | grep -i "error" | grep -v "so said EVELYN"
```
Expected: no errors, `build/junk-runner.gb` produced.

**Step 6: Commit**

```bash
git add src/main.c
git commit -m "feat: wire music_init() and music_tick() into main.c"
```

---

### Task 8: Smoketest in Emulicious

**Step 1: Launch emulator in background**

```bash
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/junk-runner.gb &
```

**Step 2: Inform the user**

Tell the user: "Emulicious is running. Please confirm that music plays and loops — you should hear audio from startup through the title screen and into gameplay. Confirm when it looks and sounds correct."

**Wait for user confirmation before proceeding.**

---

### Task 9: Create PR

**Step 1: Push the branch**

```bash
gh repo set-default MatthieuGagne/gmb-junk-runner
git push -u origin worktree-feat/hugedriver-music
```

**Step 2: Create PR**

```bash
gh pr create \
  --title "feat: add hUGEDriver music with looping placeholder song" \
  --body "$(cat <<'EOF'
Closes #71

## Summary
- Vendors hUGEDriver v6.1.3 (`lib/hUGEDriver/`) — header + prebuilt GBDK lib
- Adds `src/music_data.c` with banked placeholder song (hUGEDriver sample, `#pragma bank 255`)
- Adds `src/music.c` / `src/music.h` with `music_init()` + `music_tick()` wrappers
- Wires into `main.c`: `music_init()` before game loop, `music_tick()` in `vbl_isr`
- Music loops automatically across all game states

## Banking note
`music.c` intentionally omits `#pragma bank 255` — `music_tick()` calls `SET_BANK` (inline `SWITCH_ROM`). Code that calls `SET_BANK` must live in bank 0; otherwise `SWITCH_ROM` remaps the CPU's own instructions out from under itself.

## Test plan
- [ ] ROM builds without errors
- [ ] Music plays and loops in Emulicious smoketest
- [ ] No per-state music logic added

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Acceptance Checklist

- [ ] AC1: ROM builds without errors with hUGEDriver vendored
- [ ] AC2: Music audibly plays and loops in Emulicious
- [ ] AC3: Only `main.c` changed outside music/music_data files
- [ ] AC4: `src/music_data.c` uses `#pragma bank 255`, `BANKREF`, and `SET_BANK`
- [ ] AC5: No unit tests (hardware audio not mockable)
