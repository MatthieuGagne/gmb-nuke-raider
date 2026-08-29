# Music pipeline detail (music-expert agent)

## Scenario 1: Adding a New Song

**Trigger:** Adding or replacing a song in the game.

**Step 1: Export from hUGETracker**

Export as "GBDK .c" format, from the hUGETracker version matching the vendored driver.

**Step 2: Add required declarations to the exported file**

At the top of the exported `.c` file, add:
```c
#pragma bank 255
#include <gb/gb.h>
#include "banking.h"
BANKREF(your_song_name)
```
Rename the exported `const hUGESong_t` variable to match the `BANKREF` name.

**Step 3: Validate the export**
```bash
python tools/music_song_validate.py path/to/your_song.c
```
Expected: `OK: ... validated successfully`. The validator names the exact defect and the file on
stderr — read its output rather than guessing. Fix every reported error before continuing.

**Step 4: Copy the file into the project**

```bash
cp path/to/your_song.c src/music_data.c   # replace existing, or add as new file
```

**Step 5: Update `src/music_data.h`**
```c
BANKREF_EXTERN(your_song_name)
extern const hUGESong_t your_song_name;
```

**Step 6: Update `src/music.c`**

In `music_init()`, update the `SET_BANK()` and `hUGE_init()` calls:
```c
current_song_bank = BANK(your_song_name);
__critical {
    { SET_BANK(your_song_name);
      hUGE_init(&your_song_name);
      RESTORE_BANK(); }
}
```

**Step 7: Add to `bank-manifest.json`**

If adding a new file (not replacing `src/music_data.c`), add an entry:
```json
"src/your_song.c": { "bank": 255, "reason": "music data — autobanked" }
```

**Step 8: Validate wiring**
```bash
python tools/music_wire_check.py
```
Expected: `music_wire_check: all consistent`. It catches cross-file mismatches between
`music_data.h`, `music.c` and `bank-manifest.json`, and prints which one is out of step. Fix every
reported error before building.

**Step 9: Build** — `make`. Both validators must exit 0 and the build must produce zero errors
before treating audio as verified; re-run both after any later change to a music file.

---

## Scenario 3: Adding SFX

**Trigger:** Playing a one-shot sound effect alongside music.

hUGEDriver has no built-in SFX system. Route SFX through channel muting:

```c
// 1. Release a channel from driver control
hUGE_mute_channel(HT_CH2, HT_CH_MUTE);

// 2. Play SFX on that channel using your SFX engine

// 3. Restore channel to hUGEDriver when SFX finishes
hUGE_mute_channel(HT_CH2, HT_CH_PLAY);
```

**Wave channel (CH3) — extra step required:**
```c
// After releasing CH3, if you write to wave RAM (FF30–FF3F):
hUGE_current_wave = HT_NO_WAVE;   // forces driver to reload waveform on restore
```

**Channel selection guidance:**
- Prefer CH2 (pulse) for most SFX — simplest restore
- CH4 (noise) for percussive/explosion SFX
- CH3 (wave) for melodic SFX — most complex restore; follow CH3 Wave RAM safe access
- CH1 carries sweep effects; releasing it stops any active sweep SFX from hUGEDriver

**Notes:**
- hUGE effects 5, 8, B, D, F continue processing on muted channels — factor into SFX timing
- Compatible SFX engines: VGM2GBSFX, CBT-FX, Libbet's SFX Engine

---

## Reference

### hUGEDriver API & hardware registers — read at source

For the driver API (`hUGE_init`, `hUGE_dosound`, `hUGE_mute_channel`, `hUGE_set_position`, `hUGE_reset_wave`, `hUGE_current_wave`, `hUGE_mute_mask`, channel/mute enums) and the `hUGESong_t` struct layout, read `lib/hUGEDriver/include/hUGEDriver.h` directly. For APU register bit layouts (NR10–NR52, FF10–FF3F), consult pandocs — do not rely on memory.

> **`order_cnt` is a byte-offset count, not a pattern count.** The driver reads `*order_cnt` as the total byte length of the order table, because `current_order` advances by 2 per pattern. Correct value: `n_patterns × 2`. Example: 68 patterns → `order_cnt = 136`. A wrong value makes the song loop at half its length. The regression test `test_music_data_order_cnt_is_136` in `tests/test_music.c` catches this automatically after any re-export.

**APU enable (required before `hUGE_init`):** `NR52_REG = 0x80;` (APU power) then `NR51_REG = 0xFF; NR50_REG = 0x77;` (full routing/volume).

### Playback Control (project-specific — read `src/music.h` for the full contract)

This project does **not** drive the tracker from the ISR, and there is no pause flag. The wiring is
a **VBlank catch-up counter** — `src/music.h:20-33` documents each function; the essentials:

- `music_notify_vblank()` runs **only** in `vbl_isr()` (`src/main.c:42`) and just increments the
  counter (saturating at 255) — no bank switch, no driver call. Must stay non-BANKED.
- `music_service()` runs once per main-loop iteration (`src/main.c:69`) **in place of**
  `music_tick()`, draining the counter one `music_tick()` per elapsed VBlank, clamped to
  `MUSIC_MAX_CATCHUP` (= 3, `src/config.h:204`).
- `music_resync()` zeroes the counter; `music_ticks_owed_peek()` reads it for tests.
- `vbl_sync()` / `vbl_display_off()` are the blocking waits to use instead of `wait_vbl_done()`, so
  a blocking state never misses a tick.

**Pause/resume:** stop calling `music_service()`, mute the channels for silence, and call
`music_resync()` before resuming so the accumulated backlog is discarded instead of replayed at
speed. **Never add pause state to `music_tick()`** — it takes no `static` locals at all.

**Song switching:** `music_start(uint8_t bank, const hUGESong_t *song)` (`src/music.c:35-44`) is the
canonical pattern, and it does **no** muting: store `current_song_bank`, then inside `__critical`
save `CURRENT_BANK`, `SWITCH_ROM(bank)`, `hUGE_init(song)`, `SWITCH_ROM(saved)`, then
`music_resync()`. `music_init()` uses the `SET_BANK`/`RESTORE_BANK` form for the default song.
Follow them; don't reinvent.

**Volume fading:** no built-in API — step NR50 each frame. NR50 = 0 is still slightly audible; set `NR51 = 0` to fully silence.

(Linking the driver into the build is covered in `music-expert.md`'s Banking Rules section.)

---

### CH3 Wave RAM — Safe Access Rules

**DMG hardware only:** Re-triggering CH3 while it is actively reading Wave RAM corrupts the first 4 bytes of Wave RAM.

Safe procedure for re-triggering CH3:
1. Disable DAC: `NR30_REG = 0`
2. Write new Wave RAM data (FF30–FF3F)
3. Re-enable DAC: `NR30_REG = 0x80`
4. Trigger: write trigger bit to NR34
