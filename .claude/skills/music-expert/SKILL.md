# Music Expert — Junk Runner

Use when working on any audio task: adding songs, debugging audio, writing SFX, or validating audio builds.

> **Version pinning:** hUGETracker and hUGEDriver must match exactly. This project vendors **hUGEDriver v6.1.3**. Do not update one without the other — data format changes between versions produce silent corruption or crashes.

---

## Scenarios

### Scenario 1: Adding a New Song

**Trigger:** Adding or replacing a song in the game.

**Step 1: Export from hUGETracker**

Export as "GBDK .c" format. Use the hUGETracker version matching hUGEDriver v6.1.3.

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
python3 tools/music_song_validate.py path/to/your_song.c
```
Expected: `OK: ... validated successfully`

Fix all reported errors before continuing. Common errors and fixes:
- `missing '#pragma bank 255'` → add it at line 1 of the file
- `missing 'BANKREF(name)'` → add `BANKREF(your_song_name)` after the pragma
- `variable name mismatch` → rename the `hUGESong_t` variable to match the `BANKREF` name

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
python3 tools/music_wire_check.py
```
Expected: `music_wire_check: all consistent`

Fix all errors before building. Common errors and fixes:
- `BANKREF_EXTERN(name) but no extern const hUGESong_t name` → add the extern declaration to `music_data.h`
- `name declared in music_data.h but no SET_BANK(name) in music.c` → add `SET_BANK(name)` call in `music_init()`
- `bank-manifest.json missing entry for src/music_data.c` → add the entry

**Step 9: Build**
```bash
GBDK_HOME=/home/mathdaman/gbdk make
```

---

### Scenario 2: Debugging Audio

**Trigger:** Music is silent, choppy, plays the wrong song, or audio causes a crash.

**Diagnose in order:**

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| No sound at all | APU not enabled | Verify `NR52_REG = 0x80` is called before `hUGE_init` in `music_init()` |
| Music doesn't loop | Wrong order table end marker in hUGETracker | Re-export with correct order count |
| Crash after audio starts | `music_tick()` called from VBL ISR | Move `music_tick()` to main loop — see Banking Rules |
| Wrong song plays | `SET_BANK()` references wrong song name | Run `python3 tools/music_wire_check.py` |
| Music glitches on state transition | `SWITCH_ROM` called from ISR during song switch | Call `music_start()` from main loop only |
| Silent channels after SFX | Channel left muted | Call `hUGE_mute_channel(HT_CHx, HT_CH_PLAY)` after SFX completes |
| Ticking/popping on CH3 | Wave RAM corrupted on DMG re-trigger | Follow CH3 Wave RAM safe access procedure |

**Runtime inspection in Emulicious:**
- Open Audio tab → see channel waveforms and register values live
- Set breakpoint at `music_tick` → confirm it is called once per frame
- Watch panel: `hUGE_mute_mask` (which channels are muted), `current_song_bank`

---

### Scenario 3: Adding SFX

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
- CH3 (wave) for melodic SFX — has the most complex restore; follow CH3 Wave RAM safe access
- CH1 carries sweep effects; releasing it stops any active sweep SFX from hUGEDriver

**Notes:**
- hUGE effects 5, 8, B, D, F continue processing on muted channels — factor into SFX timing
- Compatible SFX engines: VGM2GBSFX, CBT-FX, Libbet's SFX Engine

---

### Scenario 4: Validating a Build

**Trigger:** Verifying audio is correctly wired after any change to music files.

```bash
# If a new song .c was added or modified:
python3 tools/music_song_validate.py src/music_data.c

# Cross-file consistency check (always run):
python3 tools/music_wire_check.py

# Build:
GBDK_HOME=/home/mathdaman/gbdk make
```

Both scripts must exit 0 and the build must produce zero errors before treating audio as verified.

---

## Reference

### hUGEDriver v6.1.3 API

```c
#include "hUGEDriver.h"

void hUGE_init(const hUGESong_t *song);        // init driver with song; call inside __critical
void hUGE_dosound(void);                        // advance one tick; call once per VBL
void hUGE_mute_channel(enum hUGE_channel_t ch, enum hUGE_mute_t mute);
void hUGE_set_position(unsigned char pattern);  // jump to pattern index in order table
void hUGE_reset_wave(void);                     // force wave channel reload (sets current_wave=100)

extern volatile unsigned char hUGE_current_wave;
extern volatile unsigned char hUGE_mute_mask;

// Channels: HT_CH1=0, HT_CH2=1, HT_CH3=2, HT_CH4=3
// Mute:     HT_CH_PLAY=0, HT_CH_MUTE=1
```

---

### hUGESong_t Struct

```c
typedef struct hUGESong_t {
    unsigned char tempo;
    const unsigned char * order_cnt;       // pointer to order count byte
    const unsigned char ** order1;         // CH1 pattern order table
    const unsigned char ** order2;         // CH2 pattern order table
    const unsigned char ** order3;         // CH3 pattern order table
    const unsigned char ** order4;         // CH4 pattern order table
    const hUGEDutyInstr_t * duty_instruments;
    const hUGEWaveInstr_t * wave_instruments;
    const hUGENoiseInstr_t * noise_instruments;
    const hUGERoutine_t ** routines;       // NULL if no custom routines
    const unsigned char * waves;           // 256-byte wave table
} hUGESong_t;
```

---

### APU Enable (required before hUGE_init)

```c
NR52_REG = 0x80;  // bit7=1: enable APU
NR51_REG = 0xFF;  // route all 4 channels to both speakers
NR50_REG = 0x77;  // max master volume: left=7, right=7
```

---

### Playback Control Patterns

#### Pause / Resume

```c
// Pause — stop advancing song position AND silence all channels
__critical { remove_VBL(hUGE_dosound); }
hUGE_mute_channel(HT_CH1, HT_CH_MUTE);
hUGE_mute_channel(HT_CH2, HT_CH_MUTE);
hUGE_mute_channel(HT_CH3, HT_CH_MUTE);
hUGE_mute_channel(HT_CH4, HT_CH_MUTE);

// Resume
hUGE_mute_channel(HT_CH1, HT_CH_PLAY);
hUGE_mute_channel(HT_CH2, HT_CH_PLAY);
hUGE_mute_channel(HT_CH3, HT_CH_PLAY);
hUGE_mute_channel(HT_CH4, HT_CH_PLAY);
__critical { add_VBL(hUGE_dosound); }
```

> **Project note:** This project calls `music_tick()` from the main loop (not `add_VBL`). For the main-loop pattern, add a `music_paused` flag and check it in `music_tick()` to skip `hUGE_dosound` when paused.
>
> Muting alone (without stopping the VBL/tick) silences audio but the driver still advances position. Use both mute + stop-tick if you need the song to resume from the same position.

#### Song Switching

`music_start()` is already implemented in `src/music.c`. Its pattern for reference:
```c
// 1. Mute all channels to silence immediately
hUGE_mute_channel(HT_CH1, HT_CH_MUTE); /* ... all four channels */

// 2. Store the new song's bank
current_song_bank = bank;  // VBL wrapper reads this to SET_BANK before hUGE_dosound

// 3. Init the new song inside __critical with manual bank switch
__critical {
    uint8_t _saved_bank = CURRENT_BANK;
    SWITCH_ROM(bank);
    hUGE_init(song);
    SWITCH_ROM(_saved_bank);
}

// 4. Unmute all channels
hUGE_mute_channel(HT_CH1, HT_CH_PLAY); /* ... all four channels */
```

#### Volume Fading

No built-in API. Manipulate NR50/NR51 directly each frame:
```c
// volume: 0..7 (decrement/increment each frame for a fade)
NR50_REG = AUDVOL_VOL_LEFT(volume) | AUDVOL_VOL_RIGHT(volume);
// NR50 = 0 is still slightly audible — set NR51 = 0 to fully silence
NR51_REG = (volume != 0) ? 0xFF : 0x00;
```

#### Position Jump

```c
hUGE_set_position(pattern_index);  // jump to pattern_index in the order table
```

---

### Banking Rules (music-specific)

**`music.c` must NOT have `#pragma bank 255`.**

`SET_BANK(var)` / `SWITCH_ROM(b)` expands to inline code that remaps the 0x4000–0x7FFF window. If `music_tick()` lived in a switched bank, calling `SWITCH_ROM` inside it would remap the window the CPU is currently executing from — the CPU's next instructions come from the data bank's bytes → garbage execution → crash.

`music.c` stays in bank 0 (0x0000–0x3FFF, always accessible). Bank 0 files must **omit** `#pragma bank` entirely.

**Never call `music_tick()` from a VBL ISR.**

`music_tick()` calls `SWITCH_ROM`, which is a two-step write: `_current_bank = b; rROMB0 = b`. If the ISR fires between these two writes while a BANKED function trampoline is in progress in the main loop, the shadow variable and MBC hardware disagree. `RESTORE_BANK` in the ISR then restores from the stale shadow value — corrupting bank state for the trampoline's epilogue. After several deep BANKED call sequences (e.g. repeated state transitions), the mismatched bank causes a crash.

**Rule:** The VBL ISR does display work only (`move_bkg`, sprite updates). All `SWITCH_ROM` activity — including `music_tick()` — runs in the main loop after `frame_ready = 0`.

---

### APU Hardware Reference

#### Register Map (FF10–FF3F)

```
Name  Addr  Bits        Function
-----------------------------------------------------------------------
NR10  FF10  -PPP NSSS   CH1 sweep: pace, negate, shift
NR11  FF11  DDLL LLLL   CH1 duty + length load (64-L)
NR12  FF12  VVVV APPP   CH1 volume envelope: init vol, add, period
NR13  FF13  FFFF FFFF   CH1 period low (write-only)
NR14  FF14  TL-- -FFF   CH1 trigger (bit7), length enable, period high

NR21  FF16  DDLL LLLL   CH2 duty + length load
NR22  FF17  VVVV APPP   CH2 volume envelope
NR23  FF18  FFFF FFFF   CH2 period low (write-only)
NR24  FF19  TL-- -FFF   CH2 trigger, length enable, period high

NR30  FF1A  E--- ----   CH3 DAC enable (bit 7)
NR31  FF1B  LLLL LLLL   CH3 length load (256-L)
NR32  FF1C  -VV- ----   CH3 volume: 00=0%, 01=100%, 10=50%, 11=25%
NR33  FF1D  FFFF FFFF   CH3 period low (write-only)
NR34  FF1E  TL-- -FFF   CH3 trigger, length enable, period high

NR41  FF20  --LL LLLL   CH4 length load
NR42  FF21  VVVV APPP   CH4 volume envelope
NR43  FF22  SSSS WDDD   CH4 clock shift, LFSR width, divisor code
NR44  FF23  TL-- ----   CH4 trigger, length enable

NR50  FF24  ALLL BRRR   Master vol: Vin-L, left vol (7=max), Vin-R, right vol
NR51  FF25  NW21 NW21   Panning: upper nibble=left, lower nibble=right per channel
NR52  FF26  P--- NW21   APU power (bit 7); channel active flags (read-only bits 0-3)

FF30–FF3F               Wave RAM: 16 bytes = 32 four-bit samples (high nibble first)
```

Read-back mask (ORed with written value):
CH1: `$80/$3F/$00/$FF/$BF` — CH2: `$FF/$3F/$00/$FF/$BF` — CH3: `$7F/$FF/$9F/$FF/$BF` — CH4: `$FF/$FF/$00/$00/$BF`

#### Trigger Event Atomics

Writing bit 7 of NRx4 atomically does all of the following in one cycle:

1. Channel enabled flag set
2. Length counter: if zero, loaded to 64 (256 for CH3)
3. Frequency timer reloaded with period
4. Volume envelope timer + volume reloaded from NRx2
5. CH4 LFSR: all bits set to 1
6. CH3: position reset to 0; sample buffer NOT refilled (first wave nibble skipped until loop)
7. CH1 sweep: frequency copied to shadow register, timer reloaded, overflow check run if shift ≠ 0

**Critical:** If DAC is off at trigger time, the channel is immediately disabled again after trigger.
- CH1/CH2/CH4: DAC is off when upper 5 bits of NRx2 are all zero
- CH3: DAC is off when NR30 bit 7 = 0

#### CH1 Sweep Shadow Register

CH1 has a frequency shadow register used by the sweep unit. On trigger, the current period is copied into the shadow. The sweep unit reads from and writes back to the shadow; the actual NR13/NR14 period registers are only updated when the sweep unit runs. Writing NR13/NR14 during playback updates the real registers but not the shadow — the sweep unit will overwrite with the shadow value on next sweep step.

#### Envelope DAC-Off Behavior

A channel's DAC is controlled by NRx2 (bits 7–3 = initial volume + envelope direction). If all five bits are zero:
- DAC is off
- Triggering the channel immediately disables it again
- The channel cannot produce sound regardless of other register values

Always ensure `NRx2 & 0xF8 != 0` before triggering CH1/CH2/CH4.

#### Frame Sequencer Off-by-One

The 512 Hz frame sequencer is driven by the DIV register bit 4 falling edge. It steps 0–7 continuously:

```
Step  Length Ctr  Vol Env  Sweep
---------------------------------
0     Clock       -        -
1     -           -        -
2     Clock       -        Clock
3     -           -        -
4     Clock       -        -
5     -           -        -
6     Clock       -        Clock
7     -           Clock    -
---------------------------------
Rate  256 Hz      64 Hz    128 Hz
```

**Off-by-one hazard:** The step active at trigger time affects whether length/envelope timers are reloaded ±1 tick. Triggering during step 7 (envelope clock step) vs any other step produces slightly different initial envelope behavior. This causes subtle timing bugs when re-triggering channels rapidly (e.g. fast arpeggios). Not affected by CGB double-speed mode.

**APU timing is NOT affected by CGB double-speed mode** — same rates regardless of CPU speed.

#### NR43 Divisor Table (CH4 noise frequency)

| Code | Divisor | Code | Divisor |
|------|---------|------|---------|
| 0    | 8       | 4    | 64      |
| 1    | 16      | 5    | 80      |
| 2    | 32      | 6    | 96      |
| 3    | 48      | 7    | 112     |

Timer period = `divisor << clock_shift`. Clock shifts 14 or 15 produce no clocks (silence). LFSR width mode (`NR43 bit 3 = 1`) = 7-bit LFSR → more tonal/periodic noise.

#### CGB Zombie Mode (NRx2 mid-playback writes)

Writing NRx2 while a channel is active has unpredictable behavior on DMG that varies by hardware revision. The only reliably portable trick across all GB models:

- Before trigger: write `(volume << 4) | 0x08` to NRx2 to set starting volume
- During playback: write `0x08` to NRx2 to increment volume by 1

Avoid all other mid-playback NRx2 manipulation unless targeting CGB only.

#### CH3 Wave RAM — Safe Access Rules

**DMG hardware only:** Re-triggering CH3 while it is actively reading Wave RAM corrupts the first 4 bytes of Wave RAM.

Safe procedure for re-triggering CH3:
1. Disable DAC: `NR30_REG = 0`
2. Write new Wave RAM data (FF30–FF3F)
3. Re-enable DAC: `NR30_REG = 0x80`
4. Trigger: write trigger bit to NR34

When NOT using hUGEDriver for CH3 (after `hUGE_mute_channel(HT_CH3, HT_CH_MUTE)`), always follow this sequence to avoid corruption on real DMG hardware.

#### Model Differences (DMG vs CGB)

| Behavior | DMG | CGB |
|----------|-----|-----|
| Wave RAM access while CH3 active | Only works within a few clocks of wave read | Any time |
| CH3 retrigger without disabling NR30 | Corrupts first 4 bytes of Wave RAM | Works normally |
| Length counters at power-off | Preserved | Zero'd at power-on |
| High-pass filter charge factor | 0.999958 | 0.998943 |

---

### Common Mistakes

| Mistake | Fix |
|---------|-----|
| `#pragma bank 255` in `music.c` | Remove it — `music.c` must be in bank 0 (no `#pragma bank`) |
| `add_VBL(hUGE_dosound)` directly | Use a wrapper that calls `SWITCH_ROM` first (or use `music_tick()` in main loop) |
| Calling `hUGE_init` without `__critical` | Wrap in `__critical { ... }` |
| Forgetting APU enable | Call `NR52_REG = 0x80` before `hUGE_init` |
| `BANKED` on `music_init`/`music_tick` | Not needed — they're in bank 0 |
| Passing `hUGEDriver.lib` as positional arg to lcc | Use `-Wl-k$(CURDIR)/lib/hUGEDriver/gbdk -Wl-lhUGEDriver.lib` — positional arg causes bankpack to corrupt the lib |
| Calling `music_tick()` inside `vbl_isr()` | Call it in the main loop after `frame_ready = 0` — `SWITCH_ROM` inside an ISR corrupts MBC shadow state, causing crashes after several deep BANKED call sequences |
| Song variable name doesn't match BANKREF | Run `music_song_validate.py` — it catches this |
| Inconsistency between music_data.h, music.c, or bank-manifest.json | Run `music_wire_check.py` — it catches cross-file mismatches |

---

### Makefile

```makefile
# Add to CFLAGS:
CFLAGS := ... -Ilib/hUGEDriver/include

# Link rule — route lib via -Wl-k/-Wl-l (NOT as positional arg):
$(TARGET): $(OBJS) | build
	$(LCC) $(CFLAGS) $(ROMFLAGS) -o $@ $(OBJS) \
	    -Wl-k$(CURDIR)/lib/hUGEDriver/gbdk -Wl-lhUGEDriver.lib
```

`-Wl-k<dir>` adds a library search directory; `-Wl-l<name>` names the lib. Positional arg causes bankpack to process the `.lib` and overwrite `hUGEDriver.rel` with just the 68-byte ar symbol index — `_hUGE_init`/`_hUGE_dosound` become undefined.

---

### Version Pinning

hUGETracker and hUGEDriver **must match exactly** (e.g. hUGETracker 1.0b10 requires hUGEDriver 1.0b10). The data format changes between versions — mismatches produce silent corruption or crashes. This project vendors **v6.1.3**. Do not update one without the other.
