# Nuke Raider — Pi project context

@../CLAUDE.md

The import above is load-bearing. Pi does not load a repo-root `CLAUDE.md`; without this file and
its import an interactive Pi session runs with **no project rules at all** — no worktree policy,
no smoketest gate, no branch policy — while `.pi/settings.json`'s hooks still fire and block.

`CLAUDE.local.md` is deliberately not imported: it is machine-local and gitignored. Read it
yourself when you need the toolchain paths.

## Before you rely on anything else

- **The `pwsh-*` background-job tools bypass every hook** (#572). Run builds and pushes through
  the shell tool, never through a job.
- **Nested instruction files are not auto-loaded here.** Before any `src/*.c` or `src/*.h` edit,
  read `src/CLAUDE.md` yourself — the bank-check hook *is* wired in `.pi/settings.json`, so a
  rule you cannot see can still block your write.
- **`tools/skill_overlay_hook.py` is not ported.** Skill overlays never inject under Pi, so a
  project delta in `.claude/skill-overlays/<name>.md` is silently missing — read it yourself.
- **`tools/factory_permission_hook.py` is not ported.** Factory's permission-escalation path is
  unguarded here.
- **One-time step:** run `pi` from the repo root and accept the `/trust` prompt. Untrusted, Pi
  loads none of the project's skills, agents or hooks.

Everything else about this harness — skill/agent wiring, the hook matcher and exit-code rules,
and the shell — lives in [`../docs/pi-harness.md`](../docs/pi-harness.md). Read it before
relying on any gate.
