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
| `requires_debug_rom` | `true` marks a scenario that sends a `command` step. `--all` skips it against a ROM with no mailbox; `--scenario <name>` still runs it. |

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
| `command` | `cmd` | `args`, `expect`, `max_frames` (60) | Sends one command to the debug ROM's test mailbox and waits for the game's answer. Needs the debug ROM. |
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

## The `command` action

The debug ROM carries a nine-byte mailbox. A `command` step writes one command into it, waits for
the game to answer, and reads the outcome. Every command calls a game function — the mailbox never
writes another module's variable, so a scenario cannot create a state the game will not enter.

**The debug ROM only.** Run `make build-debug` and point `--rom` at `build/debug/nuke-raider.gb`.
A scenario with a `command` step must set `"requires_debug_rom": true` at the top level;
`--all` then skips it when the ROM under test is the release ROM, and `--scenario <name>` still
runs it. Against the release ROM the first `command` step stops with the failure kind
`precondition` and the verdict `scenario-invalid`, naming the ROM you need.

### The commands and their named arguments

| `cmd` | `args` | Values |
|---|---|---|
| `add_scrap` | `amount` | 0-65535 |
| `unlock_field` | `field` | `car`, `armor`, `weapon1`, `weapon2` |
| `set_option` | `field`, `option` | `car`: `viper`/`tank`; `armor`: `light`/`heavy`; `weapon1`: `cannon`/`laser`; `weapon2`: `rocket`/`mine` |
| `damage` | `amount` | 0-255 |
| `heal` | `amount` | 0-255 |
| `force_state` | `state`, `mode` | `state`: `title`, `overmap`, `hub`, `prerace`, `playing`, `results`, `game_over`; `mode`: `push`, `pop`, `replace` |
| `spawn_turret` | `tx`, `ty` | tile coordinates |
| `despawn_turret` | `slot` | 0-7 |
| `spawn_racer` | `tx`, `ty` | reserved — always refused with `unsupported` |
| `spawn_patrol` | `tx`, `ty` | reserved — always refused with `unsupported` |

There is no command that sets an absolute HP value, because the game holds no such function.
Compose one from the readable `_hp` and a `damage` or `heal` amount.

### Refusal codes

A refusal means the game is correct. Without an `expect` field a refusal gives the verdict
`scenario-invalid`, never `fail`.

| `expect` | The game's reason |
|---|---|
| `unknown_op` | the game does not know this opcode |
| `arg_range` | an argument is outside the range the command accepts |
| `locked` | the economy has not unlocked this loadout option yet |
| `in_race` | the mailbox refuses a loadout change during a race, because the race latched its loadout when it started |
| `stack_full` | the state stack cannot take this push or pop at its current depth (detail = the depth) |
| `unsupported` | the opcode is reserved and the game has no function behind it |
| `pool_full` | the entity pool has no free slot |
| `no_effect` | the game refused the change and left the value alone |
| `not_active` | that pool slot is not active |

`unknown_op` and `arg_range` are listed for completeness, but neither is reachable as `expect`:
`_validate_command` (`tools/pyboy_scenario.py`) calls `dp.pack()` when the scenario loads, and
`dp.pack()` rejects an unknown `cmd` or an out-of-range argument before frame 0 — the scenario
never runs far enough for the game to refuse either one. Catching the typo at load time is worth
more than making these two reachable, so the validation stays as strict as it is.

`locked` is the game's own answer: the mailbox calls `loadout_is_option_unlocked`, the same
predicate the shop and the prerace menu use. `in_race` is the mailbox's own precondition — the
game has no such refusal, because its loadout menu exists only before a race. The mailbox adds it
because a race latches its loadout in `state_playing`'s `enter()`, so a mid-race change would
alter the readable variable and change nothing the player can see.

### Proving a refusal on purpose

```json
{"action": "command", "cmd": "set_option",
 "args": {"field": "weapon1", "option": "laser"}, "expect": "locked"}
```

The step passes when the game refuses for that reason, and fails when the game allows it. This is
how a scenario proves the economy still works before it unlocks anything.

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

**No scenario in this directory carries a `require` field, either — on ANY step, not only one
naming a state.** `resolve_exit_code` decides `scenario-invalid` without consulting `blocking`,
so a false `require` on a non-blocking library scenario would still fail the whole `--all` run.
Worse, a `require` that watches a game outcome (`_hp > 0`, say) turns a real game failure into a
report that says the scenario was wrong, not the game. Put a `require` only on a scenario you
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
| `precondition` | A false `require` field, or a `command` step that meets no mailbox, gets no answer, or is refused without an `expect`. |
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
from `build/game-manifest.json`. The car and the limits do NOT share one rule: the car position
is a fact the release symbol file can supply on its own, so it is reported whenever the state
held still AND is either `playing` or unreadable (no debug symbol file — the default
configuration). The limits need more — proof the game is actually racing — so they and
`at_limit` are reported only when the state held still and reads exactly `playing`. An unreadable
state is never treated as "racing": that would blame a drive limit for a freeze on a menu, which
is the misdiagnosis this block exists to prevent. When the state cannot be read, the hint says so
and names `make build-debug` instead of blaming an axis.

`at_limit` names the limits the car is pressed against, not only the ones it sits on exactly. A
limit counts when the car is within one frame of movement of it, because the clamp that stops the
car parks it just short of the edge, never exactly on it.

Two limits of the record, both deliberate:

- Without the debug symbol file every `state` field reads `null`, and `state_changes` is empty.
- `state_changes` needs one memory read per frame, which the engine does only when the state is
  readable.
