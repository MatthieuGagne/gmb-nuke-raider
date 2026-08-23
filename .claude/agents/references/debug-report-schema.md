# Debug report schema (shared)

Read by the `emulicious-debug` and `pyboy-debug` agents. Each agent's own definition states its
deltas from this baseline (which fields it always leaves empty, which extra fields it adds).

## Placement rule

After every debug session, append a fenced ` ```json ` block as the **last element** of the
response. Downstream automation finds the report by locating the *last* ` ```json ` block — put
no text after it.

## Base schema

```json
{
  "bank": <int | null>,
  "address": <hex string | null>,
  "symptom": <string>,
  "registers": [<objects>],
  "stack_trace": [<frames> | null],
  "hypothesis": <string>
}
```

| Field | Type | Description |
|-------|------|-------------|
| `bank` | `int \| null` | ROM bank where the crash or anomaly occurred. `null` if it cannot be determined. |
| `address` | `hex string \| null` | Address of the crash site or suspect variable (e.g. `"0xC123"`). `null` if none is implicated. |
| `symptom` | `string` | Plain-English description of what was observed (e.g. `"blank screen ~3s after race start"`). Always populated. |
| `registers` | `array of objects` | CPU register values at the point of interest; each object has `"name"` and `"value"`. `[]` when unavailable. |
| `stack_trace` | `array of frames \| null` | Call-stack frames from the debugger. `null` when unavailable. |
| `hypothesis` | `string` | A *synthesized* plain-English inference from the evidence — never raw emulator output and never a pattern-matched tag. |

## Null semantics

A field that cannot be determined **must emit `null`**. Do not omit the field and do not use an
empty string — automation distinguishes "unknown" from "empty"/"not applicable".

## Example

```json
{
  "bank": 2,
  "address": "0xC042",
  "symptom": "game freezes 3 seconds after entering race state",
  "registers": [
    {"name": "A", "value": "0x00"},
    {"name": "HL", "value": "0xC042"},
    {"name": "SP", "value": "0xDFE0"}
  ],
  "stack_trace": [
    {"frame": 0, "address": "0x4123", "label": "_enemy_update"},
    {"frame": 1, "address": "0x0234", "label": "_game_update"}
  ],
  "hypothesis": "HL points into WRAM at 0xC042 which is likely an uninitialized enemy pointer; enemy_update dereferences it unconditionally"
}
```
