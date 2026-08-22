# Nuke Raider — omp project context

@../CLAUDE.md

The import above is load-bearing. omp's `claude` provider reads only
`<cwd>/.claude/CLAUDE.md` and its `agents-md` provider walks up for standalone
`AGENTS.md` — neither matches a repo-root `CLAUDE.md`, so without this file the
project's entire ruleset would be invisible to an omp session. The native
`.omp/` provider has the highest priority and is discovered by walking up from
the working directory, so this file loads from anywhere in the repo.

`CLAUDE.local.md` is deliberately not imported: it is machine-local and
gitignored. Read it yourself when you need the toolchain paths.

## What omp discovers on its own

- **Skills** — all 18 in `.claude/skills/` load natively
  (`skills.enableClaudeProject`, on by default). Invoke one with
  `/skill:<name>`, or read `skill://<name>` with the `read` tool.
- **Slash commands** — `.claude/commands/` via `commands.enableClaudeProject`.

## What is wired here rather than discovered

- **Agents** — `.omp/agents/*.md`. omp deliberately skips `.claude/agents` and
  `.pi/agents` because their frontmatter is not the omp task-agent contract, so
  the seven agents are re-declared here as thin wrappers. Each one still points
  at `.claude/agents/<name>.md` for its persona, so that text lives in exactly
  one place. Dispatch them with the `task` tool.
- **Hooks** — `.omp/hooks/pre/*.ts`. omp has no declarative hook block; hooks
  are TS factories. Each wrapper calls the matching `tools/*_hook.py` through
  `.omp/hooks/lib/py.ts`, which speaks the Claude Code payload shape
  (`tool_name` / `tool_input` / `cwd`) and keeps the **exit 2 blocks** contract.

The four ported hooks are the deny gate and bank pre-write check (both blocking,
on `bash` and `write`/`edit` respectively), the Emulicious window rewrite
(cosmetic, never blocks), and the post-build bank + memory gates.

## Gates that behave differently under omp — do not rely on them

- **`tools/post_build_hook.py` reports but does not enforce.** It signals budget
  failures on stdout, not by exit code, and omp's `tool_result` event fires after
  the command has already run. The wrapper appends its output to the tool result
  so a FAIL is visible, but nothing is blocked. The smoketest gate in `CLAUDE.md`
  is still what stops a push.
- **`tools/skill_overlay_hook.py` — not ported.** Both halves are Claude-shaped:
  one matches a `Skill` tool omp does not have, the other parses `/<name>` while
  omp registers skills as `/skill:<name>`. **Skill overlays never inject under
  omp**, so a project delta in `.claude/skill-overlays/` is silently missing —
  read it yourself.
- **`tools/factory_permission_hook.py` — not ported.** It is a `Notification`
  hook and omp's event surface has no equivalent, so factory's
  permission-escalation path is unguarded.
- **Approval mode is omp's own gate.** omp ships `tools.approvalMode: yolo`
  (every tool call auto-approved). The pi permission-system plugin has no
  equivalent here — `tools.approvalMode` and `tools.approval` are the whole
  mechanism. Do not assume a permission layer is watching.

## Shell

omp's `bash` tool runs Git Bash via the user-level `shellPath`, so use POSIX
syntax. The build still needs PowerShell, `GBDK_HOME`, and Git's `bin`/`usr\bin`
on `PATH` — see `CLAUDE.local.md`. That setup is machine-local and deliberately
not committed.
