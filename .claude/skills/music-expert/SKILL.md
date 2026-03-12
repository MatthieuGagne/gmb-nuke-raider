# Music Expert — Junk Runner

Use when working with hUGEDriver music integration, song data, APU registers, or audio for the Junk Runner GBC project.

---

## hUGEDriver v6.1.3 — Key Facts

- **Source:** https://github.com/SuperDisk/hUGEDriver
- **License:** Public domain
- **Release zip:** `https://github.com/SuperDisk/hUGEDriver/releases/download/v6.1.3/hUGEDriver-6.1.3.zip`
- **Vendored in this project:** `lib/hUGEDriver/include/hUGEDriver.h` + `lib/hUGEDriver/gbdk/hUGEDriver.lib`

---

## API

```c
#include "hUGEDriver.h"

// Initialize driver with a song. Call inside __critical.
void hUGE_init(const hUGESong_t *song);

// Advance one tick. Call exactly once per VBlank.
// hUGEDriver.lib is in bank 0 — always accessible.
void hUGE_dosound(void);

// Mute/unmute individual channels
void hUGE_mute_channel(enum hUGE_channel_t ch, enum hUGE_mute_t mute);
// Channels: HT_CH1=0, HT_CH2, HT_CH3, HT_CH4
// Mute:     HT_CH_PLAY=0, HT_CH_MUTE

// Jump to a pattern position
void hUGE_set_position(unsigned char pattern);

// Force wave channel to reload (needed if you externally modified wave RAM)
void hUGE_reset_wave(void);   // sets hUGE_current_wave = 100

extern volatile unsigned char hUGE_current_wave;
extern volatile unsigned char hUGE_mute_mask;
```

---

## APU Enable (required before hUGE_init)

```c
NR52_REG = 0x80;  /* bit7=1: enable sound system */
NR51_REG = 0xFF;  /* route all 4 channels to both left and right */
NR50_REG = 0x77;  /* max master volume: left=7, right=7 */
```

---

## hUGESong_t Struct

```c
typedef struct hUGESong_t {
    unsigned char tempo;
    const unsigned char * order_cnt;      /* pointer to order count byte */
    const unsigned char ** order1;        /* CH1 pattern order table */
    const unsigned char ** order2;        /* CH2 pattern order table */
    const unsigned char ** order3;        /* CH3 pattern order table */
    const unsigned char ** order4;        /* CH4 pattern order table */
    const hUGEDutyInstr_t * duty_instruments;
    const hUGEWaveInstr_t * wave_instruments;
    const hUGENoiseInstr_t * noise_instruments;
    const hUGERoutine_t ** routines;      /* NULL if no custom routines */
    const unsigned char * waves;          /* 256-byte wave table */
} hUGESong_t;
```

Songs are exported from hUGETracker as "GBDK .c" format. The project uses the hUGEDriver sample song as a placeholder (`src/music_data.c`).

---

## CRITICAL: Banking Rule for music.c

**`music.c` must NOT have `#pragma bank 255`.**

`SET_BANK(var)` expands to inline `SWITCH_ROM(BANK(var))`. If `music_tick()` lived in a switched ROM bank (0x4000–0x7FFF), calling `SET_BANK` would remap that window to the data bank — the CPU's next instructions would come from the data bank's bytes → garbage execution.

`music.c` stays in bank 0 (0x0000–0x3FFF, always accessible). Same pattern as `main.c`.

`music_data.c` uses `#pragma bank 255` as normal — it only runs while its bank is switched in.

---

## Integration Pattern

### music_data.c (banked)

```c
#pragma bank 255
#include <gb/gb.h>
#include <stddef.h>
#include "banking.h"
#include "hUGEDriver.h"

BANKREF(music_data_song)

/* ... all static pattern/instrument/wave arrays ... */

const hUGESong_t music_data_song = {
    2,                   /* tempo */
    &order_cnt,
    order1, order2, order3, order4,
    duty_instruments,
    wave_instruments,
    noise_instruments,
    NULL,                /* routines */
    waves
};
```

### music_data.h

```c
#ifndef MUSIC_DATA_H
#define MUSIC_DATA_H
#include <gb/gb.h>
#include "banking.h"
#include "hUGEDriver.h"

BANKREF_EXTERN(music_data_song)
extern const hUGESong_t music_data_song;
#endif
```

### music.c (bank 0 — no #pragma)

```c
/* No #pragma bank 255 — see CRITICAL note above */
#include <gb/gb.h>
#include <gb/hardware.h>
#include "banking.h"
#include "hUGEDriver.h"
#include "music_data.h"
#include "music.h"

void music_init(void) {
    NR52_REG = 0x80;
    NR51_REG = 0xFF;
    NR50_REG = 0x77;
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

### music.h

```c
#ifndef MUSIC_H
#define MUSIC_H
/* No BANKED — these functions are in bank 0 */
void music_init(void);
void music_tick(void);
#endif
```

### main.c wiring

```c
#include "music.h"

static void vbl_isr(void) {
    frame_ready = 1;
    move_bkg(0, (uint8_t)cam_y);
    music_tick();          /* called every VBlank */
}

void main(void) {
    DISPLAY_OFF;
    init_palettes();
    player_init();
    music_init();          /* before add_VBL */
    add_VBL(vbl_isr);
    set_interrupts(VBL_IFLAG);
    DISPLAY_ON;
    /* ... */
}
```

---

## Makefile Changes

```makefile
# Add to CFLAGS:
CFLAGS := ... -Ilib/hUGEDriver/include

# Add lib to the ROM link rule using -Wl-k / -Wl-l (NOT as a positional arg):
$(TARGET): $(OBJS) | build
	$(LCC) $(CFLAGS) $(ROMFLAGS) -o $@ $(OBJS) -Wl-k$(CURDIR)/lib/hUGEDriver/gbdk -Wl-lhUGEDriver.lib
```

### CRITICAL: Do NOT pass hUGEDriver.lib as a positional argument

```makefile
# WRONG — bankpack will process the .lib, overwrite hUGEDriver.rel with just
# the 68-byte ar symbol index, and _hUGE_init/_hUGE_dosound become undefined:
$(LCC) ... $(OBJS) lib/hUGEDriver/gbdk/hUGEDriver.lib

# CORRECT — route directly to sdldgb as a search-path library (bypasses bankpack):
$(LCC) ... $(OBJS) -Wl-k$(CURDIR)/lib/hUGEDriver/gbdk -Wl-lhUGEDriver.lib
```

`-Wl-k<dir>` adds a library search directory; `-Wl-l<name>` names the lib to link. This is the same pattern GBDK uses internally for `sm83.lib` and `gb.lib`.

---

## Vendoring hUGEDriver (one-time setup)

```bash
wget -q https://github.com/SuperDisk/hUGEDriver/releases/download/v6.1.3/hUGEDriver-6.1.3.zip \
     -O /tmp/hUGEDriver.zip
mkdir -p lib/hUGEDriver/include lib/hUGEDriver/gbdk
unzip -j /tmp/hUGEDriver.zip include/hUGEDriver.h -d lib/hUGEDriver/include/
unzip -j /tmp/hUGEDriver.zip gbdk/hUGEDriver.lib   -d lib/hUGEDriver/gbdk/
```

---

## Adapting a hUGETracker Export

1. Export song from hUGETracker as "GBDK .c" format
2. Add to the top of the exported file:
   ```c
   #pragma bank 255
   #include <gb/gb.h>
   #include "banking.h"
   BANKREF(your_song_name)
   ```
3. Rename the exported `const hUGESong_t ...` variable to match your `BANKREF` name
4. Update `music_data.h` with `BANKREF_EXTERN` and `extern` declaration
5. Update `music.c` to reference the new song name in `SET_BANK` and `hUGE_init`

---

## Placeholder Song Source

The current placeholder uses the hUGEDriver sample song:
```
https://raw.githubusercontent.com/SuperDisk/hUGEDriver/master/gbdk_example/src/sample_song.c
```
68 orders, 40 patterns. Replace with a real composition when ready.

---

## APU Hardware Notes (Game Boy)

- APU registers: FF10–FF3F (see GBDK `<gb/hardware.h>`)
- `NR52_REG` (FF26) bit 7 = master on/off; must be 1 before any channel config
- `NR51_REG` (FF25) = channel panning (all bits = all channels both speakers)
- `NR50_REG` (FF24) = master volume; `0x77` = max (7 left, 7 right)
- hUGEDriver uses CH1 (pulse), CH2 (pulse), CH3 (wave), CH4 (noise)
- CH3 wave RAM at FF30–FF3F; hUGEDriver manages this — don't write it manually while music plays unless using `hUGE_reset_wave()` afterward

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| `#pragma bank 255` in `music.c` | Remove it — `music.c` must be in bank 0 |
| `add_VBL(hUGE_dosound)` directly | Use a wrapper that calls `SET_BANK` first |
| Calling `hUGE_init` without `__critical` | Wrap in `__critical { ... }` |
| Forgetting APU enable | Call `NR52_REG = 0x80` before `hUGE_init` |
| `BANKED` on `music_init`/`music_tick` | Not needed — they're in bank 0 |
| Passing `hUGEDriver.lib` as positional arg to lcc | Use `-Wl-k$(CURDIR)/lib/hUGEDriver/gbdk -Wl-lhUGEDriver.lib` — positional arg causes bankpack to corrupt the lib |
| Accessing `hUGE_current_wave` to silence CH3 | Use `hUGE_mute_channel(HT_CH3, HT_CH_MUTE)` |
