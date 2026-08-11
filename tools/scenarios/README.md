# Scenario format

A scenario drives the built ROM under PyBoy. `tools/pyboy_scenario.py` runs the steps and
`tools/smoketest_headless.py` decides the verdict. `tools/screenshot.py` runs the same steps.

A scenario file is a JSON object:

```json
{
  "name": "generic-smoke",
  "blocking": true,
  "watch": ["_hp", "_px", "_py"],
  "steps": [ ... ]
}
```

| Field | Meaning |
|---|---|
| `name` | The scenario name. The output directory uses it. |
| `blocking` | `true` makes a failure fail the gate. `false` makes the run evidence only. |
| `watch` | WRAM symbols sampled into `trace.jsonl`. |
| `steps` | The action list. A bare JSON array is also accepted, and it means `steps`. |

## Actions

| Action | Required fields | Optional fields | What it does |
|---|---|---|---|
| `advance` | `frames` | — | Runs the given number of frames. |
| `press` | `buttons` | `delay` | Holds every named button together for `delay` frames. |
| `nav` | `to`, `id` | `settle` | Walks the overmap path the build computed. `to` is `track` or `hub`. |
| `wait_memory` | `address`, `value` | `op`, `width`, `max_frames` | Runs frames until the comparison is true. Default budget 600 frames. |
| `wait_state` | `state` | `max_frames` | Runs frames until the game reaches the named state. Default budget 600 frames. |
| `assert_memory` | `address`, `value` | `op`, `width` | Compares one WRAM value now. |
| `assert_state` | `state` | — | Checks the game is in the named state now. |
| `assert_changes` | `symbols` | `frames` | Checks every named symbol changes inside `frames`. Default 60. |
| `assert_screen_changes` | — | `frames` | Checks the screen changes inside `frames`. Default 60. |
| `assert_live` | — | `symbols`, `screen`, `frames` | Both checks above. `screen` defaults to `true`. |
| `screenshot` | — | `out` | Writes one PNG. |
| `include` | `name` | — | Inlines another scenario at load time. |

Every action accepts `require`, except `include`. An `include` step is replaced by the steps it
names, so a `require` field on it would be discarded; the loader rejects it instead. Put the
`require` on the first step after the include.

## The `require` field

`require` states what must hold BEFORE the action runs. A false requirement means the scenario
asked the wrong question, so the harness reports the verdict `scenario-invalid`, never `fail`.

```json
{"action": "assert_live", "symbols": ["_py"],
 "require": {"address": "_hp", "op": "gt", "value": 0}}
{"action": "assert_memory", "address": "_rs_laps", "value": 1,
 "require": {"state": "playing"}}
```

| Field | Meaning |
|---|---|
| `state` | The state name the game must be in. |
| `address` | A WRAM symbol or a hexadecimal address. |
| `value` | The number to compare against. Required with `address`. |
| `op` | `eq`, `ne`, `lt`, `le`, `gt`, `ge`. The default is `eq`. |
| `width` | 1 or 2 bytes. The default comes from the symbol. |

## State names

A state name is the short form of a `const State` object: `title`, `overmap`, `prerace`,
`playing`, `results`, `game_over`, `hub`. The long forms `state_playing` and `_state_playing`
also work.

The harness reads the state out of the WRAM state stack, and matches the address and the bank
against the `_state_*` names in the `.noi` file. Those WRAM variables stay `static` in the
release ROM, so a scenario that names a state needs the debug symbol file:

```sh
make build-debug
python tools/smoketest_headless.py --all --debug-noi build/debug/nuke-raider.noi
```

A scenario that names a state without those symbols stops before frame 0 with a usage error.

**No scenario in this directory names a state, and none may.** Two reasons. The exit code for
`scenario-invalid` ignores the `blocking` flag, so an evidence scenario would fail the whole
gate. And nothing in the build pipeline produces the debug symbol file, so the pre-flight would
reject the whole library. Use `assert_state`, `wait_state` and `require.state` in a scenario you
pass by path.

## Verdicts

| Verdict | Exit code | Meaning |
|---|---|---|
| `pass` | 0 | Every step succeeded. |
| `fail` | 1 | The game failed a step. The exit code is 1 for a blocking scenario only. |
| `scenario-invalid` | 3 | The scenario is wrong, not the game. |
| — | 2 | A usage error. The emulator did not start. |

A run reports `scenario-invalid` when a `require` field is false, or when the same scenario fails
against the reference ROM as well.

## Failure kinds

| Kind | Raised by |
|---|---|
| `precondition` | A false `require` field. |
| `assert` | `assert_memory`. |
| `state` | `assert_state`. |
| `timeout` | `wait_memory`, `wait_state`. |
| `stale-symbol` | `assert_changes`, `assert_live`. A watched symbol did not change. |
| `stale-screen` | `assert_screen_changes`, `assert_live`. The screen did not change. |
| `freeze` | The screen watchdog. The screen held for the whole threshold. |
| `scenario` | A scenario error raised during the run: an unknown symbol, an unknown operator, or a navigation id the manifest does not carry (#507). The run continues with the next scenario. |

## The `context` block

Every failure record carries a `context` block that names the cause:

```json
"context": {
  "state_at_start": "playing",
  "state_at_failure": "results",
  "state_changes": [{"frame": 1284, "from": "playing", "to": "results"}],
  "car": null,
  "drive_limits": null,
  "at_limit": [],
  "hint": "the game left _state_playing for _state_results at frame 1284, ..."
}
```

When the state held still during a race, the block reports the car instead:

```json
"car": {"px": 64, "py": 0, "tx": 8, "ty": 0},
"drive_limits": {"x_min": 0, "x_max": 144, "y_min": 0, "y_max": 784,
                 "source": "wram"},
"at_limit": ["y_min"]
```

`source` is `wram` when the limits come from the live map size, and `manifest` when they come
from `build/game-manifest.json`. The block omits the car and the limits outside a race, because
the loader sets the same map size for the overmap and the hub.

Two limits of the record, both deliberate:

- Without the debug symbol file every `state` field reads `null`, and `state_changes` is empty.
- `state_changes` needs one memory read per frame, which the engine does only when the state is
  readable.
