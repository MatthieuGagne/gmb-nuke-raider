---
name: grill-me
description: Interview the user relentlessly about an approved design or plan until every decision branch is resolved. Use proactively when a design has been approved (outside an active brainstorming session) and needs stress-testing. Also invoke when the user says "grill me". Do not trigger during an active brainstorming session — brainstorming invokes this skill explicitly at step 5.
---

# Grill Me

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one.

If a question can be answered by exploring the codebase, explore the codebase instead of asking.

## Before You Begin

If the user has not yet described the plan or design to be reviewed, ask them to do so now before asking any questions:

> "Please describe the plan or design you'd like me to grill you on."

## GB Constraint Question Areas

For any GBC feature plan, work through ALL of these areas. Ask one question at a time.

For non-hardware plans (refactors, tooling, workflow changes): skip hardware-specific areas (OAM, VRAM) and focus on banking, WRAM, SDCC constraints, and testability as applicable. Always probe for correctness, testability, and architectural fit.

### 1. Banking
- Which ROM bank does this code live in?
- Does it call functions in other banks? Are those cross-bank calls safe (SET_BANK used correctly)?
- Are any data arrays large enough to need banking? Which bank?
- Have you checked the current bank budget (invoke the `bank-post-build` skill)?

### 2. OAM Budget
- How many OAM sprite slots does this feature consume?
- What is the running total vs. the 40-slot budget?
- Player uses 2 slots — are those already counted?
- Do any sprites share tiles to save OAM slots?

### 3. WRAM Budget
- How many bytes of WRAM does this feature use?
- Are all large arrays declared global or static (not local, to avoid stack overflow)?
- Total WRAM budget is 8 KB — what is the current usage?

### 4. VRAM Budget
- How many tiles does this feature consume (DMG bank 0 and/or CGB bank 1)?
- Running total vs. 192 tiles per bank?
- Are there any tile-sharing opportunities?

### 5. SoA vs AoS
- Are entity pools Structure-of-Arrays (SoA), not Array-of-Structs (AoS)?
- If there is a struct per entity, why can't it be SoA?
- Hot loop access pattern — does it iterate one field at a time (SoA wins) or all fields per entity (AoS might be acceptable)?

### 6. SDCC Constraints
- Any compound literals `(const uint16_t[]){...}`? (SDCC rejects these — use named static const arrays)
- Any float or double? (Forbidden — use fixed-point)
- Any malloc/free? (Forbidden — use static allocation)
- Any large local arrays (>~64 bytes)? (Stack overflow risk — use static or global)
- Loop counters: are they uint8_t (preferred) or int (wasteful)?

### 7. Testability
- Which parts of the logic can be tested host-side with `make test` (no hardware)?
- Which parts require the emulator to verify?
- Is there a clear boundary between pure logic (testable) and hardware I/O (not testable)?

## Process

1. Ask one question at a time from the relevant constraint areas above
2. If the answer reveals a problem, ask follow-up questions to resolve it before moving on
3. Explore the codebase to answer questions where possible (don't speculate)
4. Keep asking until every branch of the decision tree is resolved

## Summary

When all areas are covered, provide a structured summary:

```
## Grill-Me Summary

### Resolved Decisions
- [Decision]: [What was decided and why]
- ...

### Unresolved / Open Questions
- [Question]: [Why it remains open, what information is needed]
- ...

### Risk Areas
- [Area]: [Specific concern to watch during implementation]
- ...
```
