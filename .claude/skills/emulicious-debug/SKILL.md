---
name: emulicious-debug
description: Use when debugging the Wasteland Racer ROM in Emulicious — EMU_printf output, step-through debugging, breakpoints, memory/tile/sprite inspection, tracer, profiler, or romusage analysis.
---

# Emulicious Debugging — Wasteland Racer

## Quick Start

```sh
# Run ROM in Emulicious
java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/wasteland-racer.gb
```

**Further reading:**
- [Emulicious homepage](https://emulicious.net/) — full feature documentation
- [Emulicious Tracer posts](https://emulicious.net/tag/tracer/) — tracer tutorials and examples
- [Debugging your GBDK-2020 game](https://laroldsretrogameyard.com/tutorials/gb/debugging-your-gbdk-2020-game/) — practical walkthrough

---

## EMU_printf — In-ROM Debug Logging

Include `<gbdk/emu_debug.h>` to log values directly to the Emulicious debugger console.

```c
#include <gbdk/emu_debug.h>

// Log values at a key point
EMU_printf("cam_y=%u py=%u\n", cam_y, py);
```

**Supported format specifiers:**

| Specifier | Type                  |
|-----------|-----------------------|
| `%hx`     | `char` as hex         |
| `%hu`     | `unsigned char`       |
| `%hd`     | `signed char`         |
| `%c`      | character             |
| `%u`      | `unsigned int`        |
| `%d`      | `signed int`          |
| `%x`      | `unsigned int` as hex |
| `%s`      | string                |

**Warning:** excessive calls in hot paths (frame loop) degrade performance. Use in infrequently-triggered code or remove after debugging.

---

## VS Code Step-Through Debugger

### Setup

1. Install "Emulicious Debugger" extension in VS Code (Ctrl+Shift+X → search "Emulicious Debugger")
2. In VS Code preferences, set the Emulicious executable path to:
   `/home/mathdaman/.local/share/emulicious/Emulicious.jar`
3. Create `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "type": "emulicious-debugger",
            "request": "launch",
            "name": "Launch in Emulicious",
            "program": "${workspaceFolder}/build/wasteland-racer.gb",
            "port": 58870,
            "stopOnEntry": true
        }
    ]
}
```

4. Build with `-debug` flag to generate `.map`/`.noi` files (enables source-level debugging):
   ```sh
   GBDK_HOME=/home/mathdaman/gbdk make  # add -debug to LCCFLAGS in Makefile if needed
   ```

### Debugger Controls

| Action       | Effect                                    |
|--------------|-------------------------------------------|
| Play         | Run until breakpoint or exception         |
| Step Over    | Next line                                 |
| Step Into    | Enter function                            |
| Step Out     | Exit function, pause after return         |
| Step Back    | Reverse one line                          |
| Reverse      | Run backward to previous breakpoint       |
| Restart      | Reload ROM                                |
| Stop         | Disconnect                                |

**Breakpoints:** click left of line number (red dot). Variables panel shows locals when paused; hover to inspect values.

---

## Inspection Tools (Emulicious UI)

| Tool              | Use for                                                      |
|-------------------|--------------------------------------------------------------|
| Memory Editor     | Inspect/edit WRAM/VRAM/registers live                        |
| Tile Viewer       | Confirm tile data loaded correctly into VRAM                 |
| Tilemap Viewer    | Inspect background map — verify scrolling/wrapping           |
| Sprite Viewer     | Check OAM positions, tile assignments, palette               |
| Palette Viewer    | Verify CGB palette colors                                    |
| RAM Watch         | Watch specific memory addresses change each frame            |
| RAM Search        | Find addresses holding a target value (useful for variables) |
| Profiler          | Identify frame-time hotspots                                 |
| Coverage Analyzer | Color-coded: yellow=frequent, green=moderate, red=heavy      |

---

## Tracer

Records executed instructions for visualizing control flow. In Emulicious:
- Open debugger → enable Tracer
- Define optional condition expression to limit what's traced
- Results shown inline; integrate with Coverage for frequency heatmap
- Navigate trace: **Ctrl+Left / Ctrl+Right**

Useful for: confirming which code path runs, finding dead code, verifying interrupt timing.

---

## romusage — ROM/RAM Space Analysis

Included with GBDK-2020. Run after build to check space usage:

```sh
romusage build/wasteland-racer.gb -g
```

**Common flags:**

| Flag  | Output                                      |
|-------|---------------------------------------------|
| `-g`  | Small usage graph per bank                  |
| `-G`  | Large usage graph                           |
| `-a`  | Areas per bank (use `-aS` to sort by size)  |
| `-B`  | Brief output for banked regions             |
| `-sJ` | JSON output                                 |

For full symbol breakdown, build with `-debug` to generate `.cdb` file, then:
```sh
romusage build/wasteland-racer.cdb -a
```

---

## Workflow: Debugging a Bug

1. Add `EMU_printf` at the suspect location, rebuild (`/build`)
2. Launch: `java -jar /home/mathdaman/.local/share/emulicious/Emulicious.jar build/wasteland-racer.gb`
3. Observe console output; narrow the problem
4. Set VS Code breakpoints at suspect line; use Step Over/Into to inspect variables
5. Use Tilemap/Sprite Viewers to confirm visual state matches logic
6. Remove `EMU_printf` calls before committing
