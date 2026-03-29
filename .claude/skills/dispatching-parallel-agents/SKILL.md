---
name: dispatching-parallel-agents
description: Single source of truth for when and how to offload work to agents and fire them in parallel. Invoke whenever deciding whether to use Agent tool calls, parallelize tasks, or keep work inline.
---

# Dispatching Parallel Agents

**Core principle:** Keep the orchestrator context lean. Offload heavy exploration and independent reviews to agents. Fire independent agents in a single message.

## Always Offload (never run inline)

| Work type | Why offload |
|-----------|-------------|
| Codebase exploration > 2 files | Pollutes orchestrator context with file noise |
| Open-ended search (keyword, pattern, "find where X is used") | Unpredictable result volume |
| Code review (spec compliance, code quality) | Needs isolated judgment, not orchestrator state |
| Asset pipeline runs (png_to_tiles, tmx_to_c) | Long output, no orchestrator value |
| Any Explore agent task | Open-ended multi-file investigation tasks (the Explore agent subagent_type handles these) |

**Rule:** If you are about to call Read, Glob, or Grep more than twice in a row to explore unfamiliar territory, STOP — dispatch an Explore agent instead.

## Safe to Parallelize (fire in a single message)

Multiple Agent calls in one message run concurrently. Parallelize when ALL of these are true:

1. Tasks write different output files (no shared write target)
2. Tasks have no sequential data dependency (B does not need A's output)
3. Tasks do not commit to the same branch simultaneously

| Pattern | Example |
|---------|---------|
| Multiple file audits | Review `player.c` and `enemy.c` simultaneously |
| Spec + quality reviewers | Fire both review agents in one message after implementer commits |
| Independent implementers (tasks the plan has explicitly marked as safe to parallelize) | Tasks A and B each write a different file, no shared state |
| Skill/agent doc updates | Updating `sprite-expert` and `map-expert` in the same message |
| Read-only exploration | Dispatching two Explore agents on different subsystems |

## Never Parallelize

| Prohibited pattern | Why |
|--------------------|-----|
| Multiple agents writing the same file | Last write wins — earlier work silently overwritten |
| Multiple implementers committing to the same branch simultaneously | Merge conflicts, lost commits |
| Tasks with sequential data dependency | B needs A's output — fire B after A returns |
| Spec review before implementer commits | Nothing to review yet |
| Quality review before spec review passes | Quality is meaningless on non-compliant code |

## Parallel Reviewer Pattern (mandatory after each implementer commit)

After every implementer subagent commits, dispatch BOTH reviewers in a single message:

```
[Single message with two concurrent Agent calls]
  Agent 1: spec-compliance reviewer
  Agent 2: code-quality reviewer
```

Wait for BOTH to return before proceeding. If either flags issues: implementer fixes → re-dispatch the failing reviewer (single message). Repeat until both pass.

## Parallel Implementer Batch Pattern

When a plan flags tasks as parallelizable (different output files, no shared state):

1. Orchestrator dispatches 2–3 implementer agents in a single message
2. Each implementer works in isolation (different files)
3. Orchestrator waits for ALL in the batch to commit
4. Orchestrator then dispatches spec + quality reviewers in a single parallel message (one reviewer pair per implementer, or one shared reviewer pair for the whole batch if each task touches a single file)
5. Any failures → targeted fix → re-review

**Batch size limit:** Max 3 concurrent implementers. More than 3 creates coordination overhead that exceeds the parallelism benefit.

## Red Flags

These thoughts mean STOP and check this skill:

| Thought | Reality |
|---------|---------|
| "I'll just read a few more files to understand the codebase" | > 2 files → Explore agent |
| "I'll grep for this pattern myself" | Open-ended search → Explore agent |
| "I'll dispatch the quality reviewer after the spec reviewer finishes" | Fire both in one message |
| "These two tasks write different files, I'll run them sequentially" | They're parallelizable — single message |
| "I'll let both implementers commit to the branch at once" | Race condition — coordinate |

## Integration

Skills that apply this skill's rules:
- **subagent-driven-development** — parallel reviewer dispatch + parallel implementer batches
- **executing-plans** — parallel reviewer rule within each batch
- **CLAUDE.md** — Explore agent mandate for codebase exploration
