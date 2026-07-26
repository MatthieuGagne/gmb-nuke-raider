# The factory run journal is the source of truth; run state is a projection

A factory run records the same three facts — current stage, gate results, decisions —
in two places: an append-only JSONL journal and a `state.json` summary. That looks like
redundancy, and the obvious simplification is to make `state.json` authoritative and
demote the journal to a human-readable log. We deliberately did the opposite: **the
journal is the truth, and `state.json` is a cached projection of it**, because the whole
point of the registry is to explain a run that *died* — and a single JSON file that was
being rewritten when the process was killed is exactly the artifact you cannot read.

## Considered Options

**State-authoritative, journal advisory.** Less code, no replay logic, no replay tests.
Rejected: a run interrupted mid-write leaves a truncated or empty `state.json` and
nothing can reconstruct it, so the failure mode the registry exists to serve is the one
it handles worst.

**Journal-only, no state file.** Honest, but every dashboard read would replay every
event of every run in the registry to render one table.

## Consequences

- `append_event()` writes the journal line **first**, then re-saves `state.json`
  atomically (temp file + `os.replace`). State can therefore lag the journal by at most
  one event and can never lead it.
- `rebuild_state()` replays the journal to reconstruct state. Readers call it whenever
  `state.json` is missing, unparseable, or older than the journal's last event, so a
  torn write self-heals instead of being fatal.
- A truncated final JSONL line is **discarded on read, not an error**. Append-only files
  fail at the tail, which is the recoverable place.
- Do not "fix" the duplication by making `state.json` authoritative. It is a cache; if
  it disagrees with the journal, the journal wins and the cache is rebuilt.
