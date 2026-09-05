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

## Before you rely on anything else

- **Nested instruction files are not auto-loaded here.** Before any `src/*.c` or
  `src/*.h` edit, read `src/CLAUDE.md` yourself — the bank-check hook *is*
  ported to omp, so a rule you cannot see can still block your write.
- **Dispatch agents with the `task` tool**, using the mirrors in `.omp/agents/`.
  Never hand-edit those mirrors. Skills load natively from `.claude/skills/`;
  invoke one as `/skill:<name>`.
- **`tools/skill_overlay_hook.py` is not ported.** Skill overlays never inject
  under omp, so a project delta in `.claude/skill-overlays/<name>.md` is
  silently missing — read it yourself.
- **`tools/factory_permission_hook.py` is not ported.** Factory's
  permission-escalation path is unguarded here.

Everything else about this harness — what omp discovers, how `.omp/agents/` and
`.omp/hooks/` are wired, which gates report but cannot block, approval mode, and
the shell — lives in [`../docs/omp-harness.md`](../docs/omp-harness.md). Read it
before relying on any gate.
