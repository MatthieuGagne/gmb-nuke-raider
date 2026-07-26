---
name: dispatching-parallel-agents
baseline: superpowers@6.2.0
---

Project (Nuke Raider) additions and overrides for the baseline dispatching-parallel-agents skill. On conflict, this overlay wins.

## Project additions

### Explore agent mandate

For ANY codebase exploration involving **more than 2 files**, or any open-ended search ("find where X is used", "what calls Y", "search for pattern Z"), dispatch the **Explore** agent. Do NOT accumulate inline Read/Glob/Grep calls. Inline file reads are reserved for targeted lookups of known file paths.

**Rule:** if you are about to call Read, Glob, or Grep more than twice in a row to explore unfamiliar territory, STOP and dispatch an Explore agent instead.

### Always offload (never run inline)

| Work type | Why offload |
|-----------|-------------|
| Codebase exploration > 2 files | Pollutes orchestrator context with file noise |
| Open-ended search (keyword, pattern, "find where X is used") | Unpredictable result volume |
| Code review (spec compliance, code quality) | Needs isolated judgment, not orchestrator state |
| Asset pipeline runs (`png_to_tiles`, `tmx_to_c`) | Long output, no orchestrator value |
| Any open-ended multi-file investigation | That is what the Explore agent exists for |

### Project agent roster and routing

| Agent | Dispatch when |
|-------|---------------|
| `gbdk-expert` — **consultation mode** | GBDK API questions: hardware registers, sprite/tile/palette setup, CGB palettes, VBlank timing, interrupts, compile errors |
| `gbdk-expert` — **implementation mode** | Any C implementation task. Dispatch with `"implement this task: <full task text>"` — it owns TDD, bank gates, build, `gb-c-optimizer` review and fix, and the commit |
| `music-expert` | Anything touching `src/music_data.c` / `.h` or a new song `.c`; hUGEDriver, SFX routing, audio debugging |
| `map-expert` | New/edited maps, TMX conversion pipeline, BG tilemap hardware |
| `sprite-expert` | New sprite types, Aseprite pipeline, OAM slot allocation, sprite rendering |
| `gb-c-optimizer` | ROM/RAM size questions, hot-path optimization, GBDK anti-pattern review |
| `emulicious-debug` | Runtime crash, visual glitch, wrong values at runtime — when interactive step-through/breakpoints are needed |
| `pyboy-debug` | Headless automated diagnosis, no GUI, no-interaction alternative to `emulicious-debug` |
| `Explore` | Any exploration > 2 files or open-ended search |

Banking questions go to the `bank-pre-write` / `bank-post-build` **skills**, not an agent.

### Subagent shell denial

Dispatched implementer subagents have historically had **Bash and PowerShell denied** — they can edit files but cannot run commands. The **orchestrator runs all `make`, `git`, and test commands itself** and commits on the subagents' behalf. Read-only reviewer subagents still work normally. Never treat a subagent's report as proof that a build, test, or commit actually happened — verify with `git log --oneline -1`.

### Hard prohibitions — never parallelize

| Prohibited pattern | Why |
|--------------------|-----|
| Multiple agents writing the same file | Last write wins — earlier work silently overwritten |
| Multiple implementers committing to the same branch simultaneously | Merge conflicts, lost commits |
| Tasks with a sequential data dependency | B needs A's output — fire B only after A returns |
| Spec review before the implementer commits | Nothing to review yet |
| Quality review before spec review passes | Quality is meaningless on non-compliant code |

**Batch size limit:** max 3 concurrent implementers. Beyond that, coordination overhead exceeds the parallelism benefit.

### Parallel reviewer pattern (mandatory after each implementer commit)

Dispatch BOTH reviewers — spec-compliance and code-quality — as two concurrent Agent calls **in a single message**. Wait for both to return. If either flags issues: implementer fixes → re-dispatch only the failing reviewer. Repeat until both pass. Never run them sequentially in separate messages.

### Look-ahead batch rule

**Before firing ANY agent** — formal plan or ad-hoc work — scan the next 1–2 steps: do they produce different output files, with no sequential data dependency? If yes, **batch them into the same message.** This applies to ALL sequential multi-step work, not just tasks a plan flagged as parallelizable — ad-hoc investigations, doc edits, read-only explorations, and review dispatches all qualify.

### Red flags

| Thought | Reality |
|---------|---------|
| "I'll just read a few more files to understand the codebase" | > 2 files → Explore agent |
| "I'll grep for this pattern myself" | Open-ended search → Explore agent |
| "I'll dispatch the quality reviewer after the spec reviewer finishes" | Fire both in one message |
| "These two tasks write different files, I'll run them sequentially" | They're parallelizable — single message |
| "I'll let both implementers commit to the branch at once" | Race condition — coordinate |
| "This is ad-hoc work, not a formal plan, so I don't need to parallelize" | The look-ahead batch rule applies to ALL multi-step work |
