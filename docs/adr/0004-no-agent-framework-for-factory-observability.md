# No agent framework for factory observability; the registry stays hand-rolled

A reasonable reader will look at `.factory/` — a hand-rolled JSONL journal, a `state.json`
projection, a stdlib-generated HTML page — and ask why this project wrote its own
observability layer in 2026 instead of adopting LangGraph checkpointers and LangSmith
tracing. We evaluated exactly that and rejected it, for a reason that is easy to miss:
**LangSmith can only trace LLM calls made through its own SDK, and this factory makes
none.** Every LLM call happens inside Claude Code, in skill prose and subagent dispatch;
`spec_lint.py`, `smoketest_headless.py`, `memory_check.py`, and `factory_run.py` are
deterministic Python. There is nothing for it to instrument short of re-architecting the
BUILD and PLAN stages to run the agent loop in Python — which would discard every GB hard
gate, hook, and overlay the factory is built on.

The second reason is that the two systems model different things. The gap a tracing
product fills — tokens, cost, per-call latency — is precisely what PRD-4 (#436) declared
out of scope. The need PRD-4 defines — **Gate result**, **Autopsy bundle**, **Stale run**,
**Idle run**, plus WRAM traces, PyBoy screenshots, and ROM checksums — has no counterpart
in any tracing product's data model, and no product has anywhere to put a screenshot
bundle. `.factory/` would survive adoption regardless, leaving two systems where there had
been one.

So the registry stays as specified, and the dimension it genuinely lacks is filled by
**Claude Code's own OpenTelemetry export** into a self-hosted sink (#455) — strictly less
adaptation than any framework, because Claude Code instruments itself and no repository
code participates.

## Considered options

**LangSmith for tracing.** The nominal like-for-like. Rejected on the instrumentation gap
above, and independently on three project constraints: it requires network and an account
at exactly the moment a dead run needs explaining offline (self-hosting is a paid
enterprise tier); it has no home for the GB-specific evidence artifacts; and its value
curve starts at many runs, many people, and prompt-version comparison, which is not a solo
developer running one factory run at a time.

**LangGraph checkpointers for run state and resume.** The one genuinely comparable piece —
durable state, replay, time travel, and resume-from-checkpoint would subsume PRD-4's R1 and
R2 and the `rebuild_state()` replay logic. Rejected because checkpointing requires the
*orchestrator* to be a LangGraph state graph, which the `/factory` skill is not, and
because it buys roughly 200 lines of already-specified stdlib at the cost of a dependency
tree — `langgraph`, `langchain-core`, `pydantic`, `httpx` — in a repository whose Python
tooling has, PyBoy aside, zero third-party runtime dependencies and a stdlib-only
convention (#436 R7). It also puts the byte-exact determinism contract (#436 R6) behind a
framework boundary we do not control.

**Prefect for stage state and resume.** Lower adaptation than LangGraph — it decorates
existing functions rather than demanding a graph, and ships a local SQLite backend with a
UI. Rejected on the same dependency and domain-mismatch grounds, and because a daemon plus
a database is a heavier substrate than an append-only JSONL file for a pipeline that runs
one issue at a time.

**Claude Agent SDK as the PRD-6 driver.** Genuinely the least-adaptation way to get a
structured agent event stream, because it *is* the Claude Code harness as a library —
skills, hooks, subagents, and permissions all preserved rather than replaced. Deferred, not
rejected: it moves the driver into the Claude-specific surface that #432's portability
requirement deliberately confines to skill prose, hook wiring, and subagent dispatch. Worth
revisiting when PRD-5's stage contracts are real.

**An export seam in `append_event()`.** A fail-open, env-gated sink callback, ~20 lines,
preserving the option to emit pipeline events externally later. Deferred: native OTel
covers the dimension that motivated it, and no external consumer is asking for pipeline
events.

## Consequences

**Observability is two lenses, not one, and they must not converge.** The registry owns
stage, gate, decision, and autopsy facts; telemetry owns token, cost, and tool-call facts.
Pipeline events do not go over OpenTelemetry and telemetry does not become an input to run
state — a future change that routes either through the other re-creates the vendor coupling
this decision avoids.

**Telemetry is additive and must fail soft.** A run with no telemetry configured has to
behave identically and render as normal rather than degraded (#455 R3). This mirrors the
posture #436 R9 already takes for permission events, and it is what keeps the factory
agent-agnostic: OpenTelemetry data is vendor-neutral and survives a migration, but the
*producer* is Claude-specific, so under another agent there is simply nothing recorded.

**We own the replay logic, including its failure modes.** Torn writes, truncated final
JSONL lines, and state-behind-journal recovery are ours to implement and test
(`docs/adr/0003`). That is the accepted cost of not delegating to a checkpointer.

**This is a rejection with a shelf life.** It rests on the factory's LLM calls living
inside Claude Code. If BUILD or PLAN ever moves its agent loop into Python — the Agent SDK
path above being the most likely route — the instrumentation gap closes and the trade-off
should be re-run rather than assumed settled.
