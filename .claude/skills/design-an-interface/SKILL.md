---
name: design-an-interface
description: "Design It Twice for a module interface: spawns 4 parallel sub-agents each constrained to a different design lens (minimal API, testability, caller ergonomics, GB efficiency). Use when designing any new src/*.c module interface. Invoked automatically by the brainstorming skill's Design-It-Twice step."
---

# Design an Interface

## Overview

Apply "Design It Twice" to module interface decisions by exploring four orthogonal design constraints in parallel. Each constraint is given to a separate sub-agent. Compare the four results and synthesize the best interface.

**When to use:** Any new `src/*.c` module. Invoked from the `brainstorming` skill's Design-It-Twice step.

## Before You Begin

Gather the following from the current conversation context:
1. **Module name** — e.g., `enemy`, `projectile`, `hud`
2. **What the module does** — one sentence
3. **Who calls it** — which other modules / states invoke it
4. **Key operations** — the 3-5 things callers need to do with it

If any of these are unclear, ask the user before dispatching agents.

## Dispatch: 4 Parallel Sub-Agents

Dispatch all four agents simultaneously using the Agent tool in a single message. Give each agent the same module description and codebase context, but constrain them to explore only their assigned lens.

### Agent 1 — Minimal API Surface

**Constraint:** Propose the fewest possible exported functions that still satisfy all caller needs. Every exported symbol must earn its place. Prefer combining operations over splitting them. Prefer flags/modes over separate functions.

**Output:** A `.h`-style header (function signatures + brief comment per function). Justify any function with more than one argument.

### Agent 2 — Maximum Testability

**Constraint:** Design the interface so that all logic can be tested host-side with `make test` (no GBDK hardware). Separate pure logic from hardware I/O. All stateful functions should accept explicit state or return values rather than reading globals. Prefer functions that take inputs and return outputs over functions that mutate hidden state.

**Output:** A `.h`-style header. For each function, note whether it is pure (testable host-side) or hardware-bound (requires emulator).

### Agent 3 — Caller Ergonomics

**Constraint:** Design the interface to be the easiest possible for callers to use correctly and hardest to use incorrectly. Minimize setup burden. Prefer one-call workflows over multi-step init sequences. Name functions to read naturally at the call site in `main.c` or a state handler.

**Output:** A `.h`-style header plus 3-5 example call-site snippets showing realistic usage.

### Agent 4 — GB Efficiency (SoA / WRAM / SM83)

**Constraint:** Design the interface assuming the implementation will use Structure-of-Arrays (SoA) entity pools. The public API must not expose struct pointers that imply AoS layout. Minimize WRAM footprint. Prefer `uint8_t` for all index/count parameters — SM83 has 8-bit registers and `int` parameters require 16-bit loads. Avoid passing large structs by value.

**Output:** A `.h`-style header. For each function, note the parameter types and why they are GB-efficient. Note the expected SoA backing arrays and their WRAM cost (bytes).

## Synthesis Step

After all four agents respond, compare the proposals side by side:

| Aspect | Agent 1 (Minimal) | Agent 2 (Testable) | Agent 3 (Ergonomic) | Agent 4 (GB Efficient) |
|--------|------------------|--------------------|---------------------|----------------------|
| Function count | | | | |
| Testability | | | | |
| Call-site clarity | | | | |
| WRAM cost | | | | |
| SoA compatibility | | | | |

Then propose a **synthesized interface** that takes the best aspects of each. Document tradeoffs explicitly.

Present the synthesized interface to the user and get approval before proceeding. If the user wants changes, revise and re-present.

## Output

Return the approved `.h`-style header to the brainstorming session. This becomes the Design-It-Twice artifact in the PRD.
