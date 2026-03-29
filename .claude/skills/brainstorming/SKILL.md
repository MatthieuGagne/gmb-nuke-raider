---
name: brainstorming
description: "Standalone exploration tool for turning ideas into designs — usable at any point in the dev cycle (PRD writing, plan writing, debugging, or standalone exploration). Explores user intent, requirements and design before implementation."
---

# Brainstorming Ideas Into Designs

## Overview

Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design and get user approval.

<HARD-GATE>
Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it. This applies to EVERY project regardless of perceived simplicity.
</HARD-GATE>

## Anti-Pattern: "This Is Too Simple To Need A Design"

Every project goes through this process. A todo list, a single-function utility, a config change — all of them. "Simple" projects are where unexamined assumptions cause the most wasted work. The design can be short (a few sentences for truly simple projects), but you MUST present it and get approval.

## Checklist

You MUST create a task for each of these items and complete them in order:

1. **Explore project context** — check files, docs, recent commits
2. **Ask clarifying questions** — one at a time, understand purpose/constraints/success criteria
3. **Propose 2-3 approaches** — with trade-offs and your recommendation
4. **Present design** — in sections scaled to their complexity, get user approval after each section
   - **Design-It-Twice** (required for any new `src/*.c` module): invoke the `design-an-interface` skill (`Skill` tool, `skill: "design-an-interface"`) to spawn 4 parallel sub-agents each exploring a different design constraint; compare their results and choose the best
5. **Invoke grill-me** — use the `grill-me` skill (`Skill` tool, `skill: "grill-me"`) to stress-test the approved design. `grill-me` will NOT re-invoke brainstorming — it produces a Resolved/Unresolved/Risk summary only. Continue only after that summary is generated.
6. **Resolved / Unresolved / Deferred summary** — output a short bullet list per category:
   - **Resolved:** decisions that are settled
   - **Unresolved:** open questions that must be answered before implementation begins
   - **Deferred:** items deliberately set aside (not blocking now)
   If Unresolved is non-empty, stop and resolve those questions before continuing.

**Brainstorming ends here.** After the resolved/unresolved/deferred summary is presented, the session is complete. The user will invoke `/prd` and `writing-plans` when they are ready — do not auto-invoke them.

## GB Constraint Checklist

When designing any GBC feature, explicitly address all of these in your design:

| Constraint | Question to answer |
|------------|-------------------|
| **Banking** | Which ROM bank does this code live in? Does it call code in other banks? Are SET_BANK calls safe? |
| **OAM** | How many OAM sprite slots does this use? Running total vs. budget of 40? |
| **WRAM** | How many bytes of WRAM does this use? Are all large arrays global/static (not local)? |
| **VRAM** | How many tiles does this consume? Running total vs. budget of 192 (bank 0) + 192 (bank 1)? |
| **SoA** | Are entity pools Structure-of-Arrays (not Array-of-Structs)? |
| **SDCC** | Any compound literals, float, malloc, large locals, or non-uint8_t loop counters? |
| **Testability** | Which logic can be host-side tested with `make test` (no hardware)? |

## Process Flow

```dot
digraph brainstorming {
    "Explore project context" [shape=box];
    "Ask clarifying questions" [shape=box];
    "Propose 2-3 approaches" [shape=box];
    "Present design sections + Design-It-Twice" [shape=box];
    "User approves design?" [shape=diamond];
    "Invoke grill-me skill" [shape=box];
    "Resolved/Unresolved/Deferred summary" [shape=box];
    "Unresolved items?" [shape=diamond];
    "Done (user invokes /prd or writing-plans when ready)" [shape=doublecircle];

    "Explore project context" -> "Ask clarifying questions";
    "Ask clarifying questions" -> "Propose 2-3 approaches";
    "Propose 2-3 approaches" -> "Present design sections + Design-It-Twice";
    "Present design sections + Design-It-Twice" -> "User approves design?";
    "User approves design?" -> "Present design sections + Design-It-Twice" [label="no, revise"];
    "User approves design?" -> "Invoke grill-me skill" [label="yes"];
    "Invoke grill-me skill" -> "Resolved/Unresolved/Deferred summary";
    "Resolved/Unresolved/Deferred summary" -> "Unresolved items?";
    "Unresolved items?" -> "Ask clarifying questions" [label="yes, resolve first"];
    "Unresolved items?" -> "Done (user invokes /prd or writing-plans when ready)" [label="no"];
}
```

## The Process

**Understanding the idea:**
- Check out the current project state first (files, docs, recent commits)
- Ask questions one at a time to refine the idea
- Prefer multiple choice questions when possible, but open-ended is fine too
- Only one question per message — if a topic needs more exploration, break it into multiple questions
- Focus on understanding: purpose, constraints, success criteria

**Exploring approaches:**
- Propose 2-3 different approaches with trade-offs
- Present options conversationally with your recommendation and reasoning
- Lead with your recommended option and explain why

**Presenting the design:**
- Once you believe you understand what you're building, present the design
- Scale each section to its complexity: a few sentences if straightforward, up to 200-300 words if nuanced
- Ask after each section whether it looks right so far
- Cover: architecture, components, data flow, error handling, testing
- For any new `src/*.c` module: invoke the `design-an-interface` skill to spawn 4 parallel sub-agents
  (minimal API, testability, caller ergonomics, GB efficiency); compare results, choose the best — document why
- Work through the GB Constraint Checklist explicitly for any GBC feature
- Be ready to go back and clarify if something doesn't make sense

## Key Principles

- **One question at a time** — don't overwhelm with multiple questions
- **Multiple choice preferred** — easier to answer than open-ended when possible
- **YAGNI ruthlessly** — remove unnecessary features from all designs
- **Explore alternatives** — always propose 2-3 approaches before settling
- **Incremental validation** — present design, get approval before moving on
- **Be flexible** — go back and clarify when something doesn't make sense
- **GB constraints first** — work through the constraint checklist before finalizing any GBC design
