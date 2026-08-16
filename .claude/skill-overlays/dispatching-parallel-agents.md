---
name: dispatching-parallel-agents
baseline: superpowers@6.2.0
---

Project (Nuke Raider) additions and overrides for the baseline dispatching-parallel-agents
skill. On conflict, this overlay wins — but an override earns that only by stating what the
baseline cannot know. Every section carries a `**Why:**` line (#527 R7).

**Baseline audit:** content of `superpowers@6.2.0` read and compared on 2026-08-02 (#527 R6).

## Project additions

### Explore agent mandate

**Why:** the baseline shares the context-preservation motive but scopes dispatch to *multiple
independent failures*; it names no threshold for ordinary exploration. The 2-file trigger and
the `Explore` agent are this project's.

For ANY codebase exploration involving **more than 2 files**, or any open-ended search ("find
where X is used", "what calls Y", "search for pattern Z"), dispatch the **Explore** agent. Do NOT
accumulate inline Read/Glob/Grep calls. Inline file reads are reserved for targeted lookups of
known file paths.

**Rule:** if you are about to call Read, Glob, or Grep more than twice in a row to explore
unfamiliar territory, STOP and dispatch an Explore agent instead.

### Always offload (never run inline)

**Why:** the pipeline rows are project-specific; the general principle is the baseline's.

| Work type | Why offload |
|-----------|-------------|
| Codebase exploration > 2 files | Pollutes orchestrator context with file noise |
| Open-ended search (keyword, pattern, "find where X is used") | Unpredictable result volume |
| Code review | Needs isolated judgment, not orchestrator state |
| Asset pipeline runs (`png_to_tiles`, `tmx_to_c`) | Long output, no orchestrator value |
| Any open-ended multi-file investigation | That is what the Explore agent exists for |

### Project agent roster and routing

**Why:** this project's agents do not exist upstream.

| Agent | Dispatch when |
|-------|---------------|
| `gbdk-expert` — **consultation mode** | GBDK API questions: hardware registers, sprite/tile/palette setup, CGB palettes, VBlank timing, interrupts, compile errors |
| `gbdk-expert` — **implementation mode** | Any C implementation task. Dispatch with `"implement this task: <full task text>"` — it owns TDD, the bank gates, the build, `gb-c-optimizer` review and fix, and the commit |
| `music-expert` | Anything touching `src/music_data.c` / `.h` or a new song `.c`; hUGEDriver, SFX routing, audio debugging |
| `map-expert` | New/edited maps, TMX conversion pipeline, BG tilemap hardware |
| `sprite-expert` | New sprite types, Aseprite pipeline, OAM slot allocation, sprite rendering |
| `gb-c-optimizer` | ROM/RAM size questions, hot-path optimization, GBDK anti-pattern review |
| `emulicious-debug` | Runtime crash, visual glitch, wrong values at runtime — when interactive step-through/breakpoints are needed |
| `pyboy-debug` | Headless automated diagnosis, no GUI, no-interaction alternative to `emulicious-debug` |
| `Explore` | Any exploration > 2 files or open-ended search |

Banking questions go to the `bank-pre-write` / `bank-post-build` **skills**, not an agent.

### Verify subagent claims against version control

**Why:** the baseline's verification step checks that the *fixes* work; it does not warn that
the report itself may be false. This project has seen reports name commits that did not exist.

Never treat a subagent's report as proof that a build, a test, or a commit actually happened —
verify with `git log --oneline -1`. Subagents run their own build, test, and commit commands;
running them on a subagent's behalf pulls every command's output into the orchestrator's
context.

### Hard prohibitions — never parallelize

**Why:** the baseline names shared state as a hazard; these are the concrete shapes it takes
here.

| Prohibited pattern | Why |
|--------------------|-----|
| Multiple agents writing the same file | Last write wins — earlier work silently overwritten |
| Multiple implementers committing to the same branch simultaneously | Merge conflicts, lost commits |
| Tasks with a sequential data dependency | B needs A's output — fire B only after A returns |
| Task review before the implementer commits | Nothing to review yet |

**Implementers are never batched.** Whatever else this file says about batching, an
implementer dispatch is one at a time — see the `subagent-driven-development` overlay's
`### Dispatch order`. The prohibition two rows above ("multiple implementers committing to
the same branch simultaneously") is the binding rule, and this file used to give a batch
size that contradicted it. For non-committing agents — reviewers on different files,
read-only exploration — the practical ceiling is 3 concurrent dispatches, beyond which
coordination overhead exceeds the benefit.

The task review itself is **one dispatch, not two** — see the `subagent-driven-development`
baseline: a single task review carries both the spec-compliance and the code-quality verdict.

### Look-ahead batch rule

**Why:** the baseline scopes parallel dispatch to multiple *known* independent failures; this
extends the same reasoning to ordinary sequential work.

**Before firing ANY agent** — formal plan or ad-hoc work — scan the next 1–2 steps: do they
produce different output files, with no sequential data dependency? If yes, **batch them into
the same message.** This applies to ALL sequential multi-step work — ad-hoc investigations, doc
edits, read-only explorations, and review dispatches all qualify. Implementer dispatches never
qualify — see the `subagent-driven-development` overlay's `### Dispatch order`.

### Red flags

**Why:** each row is the failure mode of a project rule above — they are not general advice, and
the baseline has no equivalent table.

| Thought | Reality |
|---------|---------|
| "I'll just read a few more files to understand the codebase" | > 2 files → Explore agent |
| "I'll grep for this pattern myself" | Open-ended search → Explore agent |
| "I'll split the review into a spec pass and a quality pass" | One task review carries both verdicts — splitting doubles the cost for the same answer |
| "These two tasks write different files, I'll run them sequentially" | They're parallelizable — single message, unless they are implementers (see `### Dispatch order`) |
| "I'll let both implementers commit to the branch at once" | Race condition — coordinate |
| "This is ad-hoc work, not a formal plan, so I don't need to parallelize" | The look-ahead batch rule applies to ALL multi-step work |
| "The subagent said it committed" | Not proof — `git log --oneline -1` |
