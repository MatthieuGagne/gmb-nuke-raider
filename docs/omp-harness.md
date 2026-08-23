# omp harness

Linked from [`CLAUDE.md`](../CLAUDE.md). Relevant only when running the omp coding agent
(`omp`, [oh-my-pi](https://github.com/can1357/oh-my-pi)); under Claude Code or Pi none of this
applies. omp is a fork of Pi, but its extension model is different enough that almost nothing
in [`pi-harness.md`](pi-harness.md) carries over — read this file, not that one.

## What omp discovers on its own

Unlike Pi, omp needs no `skills:` wiring. All 18 project skills in `.claude/skills/` load
natively via `skills.enableClaudeProject`, and `.claude/commands/` via
`commands.enableClaudeProject` — both default to `true`. Invoke a skill as `/skill:<name>`, or
read `skill://<name>` with the `read` tool. There is no `Skill` tool.

Most of what `.pi/settings.json` installs as packages is built into omp and must **not** be
re-added: `task` (subagents), `todo`, `web_search` / `fetch`, `ask`, native MCP, and
`plan`. A skill that says "dispatch a subagent" or "use TodoWrite" means those tools.

## What `.omp/` wires, and why

### `.omp/AGENTS.md` — the import is load-bearing

omp's `claude` context provider reads only `<cwd>/.claude/CLAUDE.md` (no ancestor walk-up), and
its `agents-md` provider walks up for standalone `AGENTS.md` files only. **A repo-root
`CLAUDE.md` matches neither and is never loaded.** Without `.omp/AGENTS.md` and its
`@../CLAUDE.md` import, an omp session in this repo would run with no project rules at all —
no worktree policy, no smoketest gate, no bank discipline.

The native `.omp/` provider is priority 100 and is found by walking up from the working
directory, so that one file reaches every subdirectory and every worktree. `CLAUDE.local.md` is
deliberately **not** imported: it is machine-local and gitignored.

An `@` import that cannot resolve leaves its literal token in the text rather than erroring, so
a broken path fails silently. If a session seems ignorant of the project, check that import first.

### `.omp/agents/*.md` — re-declared, not discovered

omp **intentionally skips** `.claude/agents` and `.pi/agents`; their frontmatter is not omp's
task-agent contract. The seven agents are therefore re-declared here. Frontmatter carries `name`
and `description` (both required) plus `tools`; the **body becomes the system prompt**. Each body
is a thin wrapper pointing at `.claude/agents/<name>.md`, so persona text still lives in exactly
one place.

Tool names differ from Claude Code's: `glob` not `Glob`, `bash` covers both `Bash` and
`PowerShell`, and there is no `ls`. Dispatch with the `task` tool.

### `.omp/hooks/pre/*.ts` — TS factories over the Python scripts

omp has **no declarative hook block**. Hooks are TypeScript modules under `.omp/hooks/pre/`
that default-export a factory receiving a `HookAPI`, registering handlers with `pi.on(...)`.
Each wrapper calls its matching `tools/*_hook.py` through `.omp/hooks/lib/py.ts`, which builds
the Claude-Code-shaped payload (`tool_name` / `tool_input` / `cwd`) those scripts already parse
and preserves the **exit 2 blocks** contract. `lib/` sits outside `pre/` so it is not itself
discovered as a hook.

| Wrapper | Event | Tools | Blocks? |
|---|---|---|---|
| `deny-gate.ts` | `tool_call` | `bash` | yes |
| `bank-check.ts` | `tool_call` | `write`, `edit` | yes |
| `emulicious-window.ts` | `tool_call` | `bash` | never — cosmetic |
| `post-build.ts` | `tool_result` | `bash` | **cannot** — see below |

The bridge fails **open**: no interpreter, a spawn error, or a missing script allows the call,
matching the fail-open convention of the Python hooks themselves. A handler that *throws*,
however, fails closed — omp blocks the tool call — so keep the wrappers free of unguarded work.

## Gates that behave differently under omp — do not rely on them

- **`post_build_hook.py` reports but does not enforce.** It signals budget failures on stdout
  rather than by exit code, and omp's `tool_result` event fires *after* the command has already
  run, so nothing can be blocked at that point. The wrapper appends the hook's output to the tool
  result, which makes a FAIL visible to the agent but not binding. The smoketest gate in
  `CLAUDE.md` remains what stops a push.
- **`tools/skill_overlay_hook.py` — not ported.** Both halves are Claude-shaped: one matches a
  `Skill` tool omp does not have, the other parses `/<name>` while omp registers skills as
  `/skill:<name>`. **Skill overlays never inject under omp**, so a project delta in
  `.claude/skill-overlays/` is silently missing — read it yourself.
- **`tools/factory_permission_hook.py` — not ported.** It is a `Notification` hook and omp's
  event surface has no equivalent, so factory's permission-escalation path is unguarded.
- **`tools.approvalMode` is the entire permission mechanism.** There is no equivalent of Pi's
  `@gotgenes/pi-permission-system`. omp ships `yolo` (every tool call auto-approved) as the
  **default**, which is strictly weaker than either other harness — a fresh machine must set
  `tools.approvalMode` to `write` or `always-ask` before the repo's gates mean anything.

## Shell

omp's `bash` tool runs Git Bash through the user-level `shellPath`, so use POSIX syntax — the
same inversion that applies under Pi. Build setup stays **machine-local and uncommitted**: the
build needs PowerShell, `GBDK_HOME`, and Git's `bin`/`usr\bin` on `PATH`, which takes absolute
paths. Configure that in `~/.omp/agent/config.yml`, not here.

Note there is no `pwsh-*` background-job escape hatch under omp — the ungated-job hole that
affects Pi (#572) does not exist here, because omp exposes one shell tool and every hook
matches on it.
