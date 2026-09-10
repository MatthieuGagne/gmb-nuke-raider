#!/usr/bin/env python3
"""
sync_agents.py — mirror .claude/agents/*.md into .omp/agents/*.md.

Claude Code reads .claude/agents/ and omp reads .omp/agents/; neither reads the
other's directory, so the canonical agent files under .claude/agents/ are
mirrored here on every commit. The generator translates the YAML frontmatter to
omp's dialect and copies the markdown body verbatim, then deletes any
.omp/agents/*.md whose canonical source is gone — an exact mirror, so the two
directories cannot drift.

Frontmatter translation:
    model:  opus  -> "@default"     sonnet -> "@smol"
    tools:  Read->read  Write->write  Edit->edit  Grep->grep  Glob->glob
            Bash->bash  WebSearch->web_search
            dropped: PowerShell, WebFetch, Skill, TodoWrite
    color:  dropped

Body translation:
    The body is copied verbatim, then OMP_ADJUSTMENTS is appended once at the
    end of every mirror. The canonical bodies are written for Claude Code and
    name tools omp does not have ("invoke the `bank-pre-write` skill", "use the
    PowerShell tool"); the appended block tells the omp subagent how to read
    those instructions with the tools it actually has.

Exit codes:
    0  sync completed
    1  operational error (canonical directory missing, or a file failed to parse)

Usage:
    python tools/sync_agents.py [repo_root]
"""
import argparse
import os
import sys

SRC_DIR = ".claude/agents"
DST_DIR = ".omp/agents"

MODEL_MAP = {"opus": '"@default"', "sonnet": '"@smol"'}

TOOL_MAP = {
    "Read": "read",
    "Write": "write",
    "Edit": "edit",
    "Grep": "grep",
    "Glob": "glob",
    "Bash": "bash",
    "WebSearch": "web_search",
}

DROPPED_TOOLS = {"PowerShell", "WebFetch", "Skill", "TodoWrite"}
DROPPED_KEYS = {"color"}

# Appended verbatim to the end of every generated .omp/agents/*.md body. The
# canonical bodies are written for Claude Code, so they issue instructions omp
# cannot follow literally; this block re-maps them onto omp's tool set.
OMP_ADJUSTMENT_HEADING = "## omp harness adjustments"
OMP_ADJUSTMENTS = """---

## omp harness adjustments

Everything above is the canonical Claude Code agent file, copied verbatim. Three
adjustments apply when you follow it under omp:

- **There is no `Skill` tool.** Where the body tells you to invoke, use or run a
  project skill (`bank-pre-write`, `build`, `test`, `aseprite`, `screenshot`, …),
  read that skill's `.claude/skills/<name>/SKILL.md` and follow it directly.
- **`bash` is your only shell tool, and it runs PowerShell 7 (`pwsh`).** It
  subsumes both Claude Code's `Bash` and its `PowerShell` tool, so run commands
  with PowerShell syntax (`$env:VAR`, `2>$null`). Where the body says to use the
  PowerShell tool or `Start-Process`, use the bash tool with the PowerShell
  equivalent instead.
- **Ignore the body's `tools:` frontmatter line.** Those are Claude Code tool
  names; your tools are the omp ones in this file's frontmatter above.
"""


def split_frontmatter(text):
    """Return (frontmatter_lines, body_lines) for a frontmatter-delimited file.

    The file must start with a '---' line and contain a second '---' line.
    Body lines are everything after that second delimiter, preserved exactly.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("file does not start with a '---' frontmatter line")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError("unterminated frontmatter: no closing '---' line")
    return lines[1:end], lines[end + 1:]


def parse_frontmatter(front_lines):
    """Parse 'key: value' frontmatter lines into an ordered (key, value) list.

    The value is the text after the first colon, whitespace-stripped — so a
    quoted description round-trips verbatim, including any colons it contains.
    """
    fields = []
    for line in front_lines:
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError("malformed frontmatter line: %r" % line)
        fields.append((key.strip(), value.strip()))
    return fields


def translate_model(value):
    """Translate a Claude model tier to an omp role alias."""
    return MODEL_MAP.get(value, value)


def translate_tools(value):
    """Translate a comma-separated Claude tool list to omp tool names.

    Tools in DROPPED_TOOLS are removed; every other name maps through TOOL_MAP,
    falling back to the name unchanged when it is unknown.
    """
    out = []
    for name in (n.strip() for n in value.split(",")):
        if not name:
            continue
        if name in DROPPED_TOOLS:
            continue
        out.append(TOOL_MAP.get(name, name))
    return ", ".join(out)


def render(source_text):
    """Render the omp mirror of one canonical agent file's text.

    The frontmatter is translated to omp's dialect and the body is copied
    verbatim, with OMP_ADJUSTMENTS appended once at the end so the omp subagent
    can act on instructions written against Claude Code's tool set.
    """
    front_lines, body_lines = split_frontmatter(source_text)
    out = ["---"]
    for key, value in parse_frontmatter(front_lines):
        if key in DROPPED_KEYS:
            continue
        if key == "model":
            out.append("model: %s" % translate_model(value))
        elif key == "tools":
            out.append("tools: %s" % translate_tools(value))
        else:
            out.append("%s: %s" % (key, value))
    out.append("---")
    mirrored = "\n".join(out + body_lines).rstrip("\n")
    return "%s\n\n%s" % (mirrored, OMP_ADJUSTMENTS)


def write_if_changed(path, content):
    """Write *content* to *path* only when it differs; return True when written.

    Always writes LF endings regardless of platform (newline='\\n'), so the
    generated files stay byte-stable on Windows and in the git index.
    """
    if os.path.isfile(path):
        # newline="" reads raw bytes (no \r\n -> \n translation), so a mirror
        # that landed on disk with CRLF endings compares unequal and is rewritten
        # with LF — matching the newline="\n" write path below (#729 review).
        with open(path, encoding="utf-8", newline="") as fh:
            if fh.read() == content:
                return False
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    return True


def sync(repo_root):
    """Mirror SRC_DIR into DST_DIR under *repo_root*.

    Returns the sorted list of mirrored filenames. Only the *.md files directly
    under SRC_DIR are mirrors; the references/ subdirectory is single-sourced
    and deliberately not copied (its paths stay valid in the repo for the omp
    subagents' read/grep).
    """
    src = os.path.join(repo_root, SRC_DIR)
    dst = os.path.join(repo_root, DST_DIR)
    if not os.path.isdir(src):
        raise ValueError("%s/ is missing — nothing to mirror" % SRC_DIR)

    expected = {}
    for name in sorted(os.listdir(src)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(src, name), encoding="utf-8") as fh:
            expected[name] = render(fh.read())

    os.makedirs(dst, exist_ok=True)
    for name, content in sorted(expected.items()):
        write_if_changed(os.path.join(dst, name), content)

    for name in sorted(os.listdir(dst)):
        if name.endswith(".md") and name not in expected:
            os.remove(os.path.join(dst, name))

    return sorted(expected)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Mirror .claude/agents/*.md into .omp/agents/*.md.")
    parser.add_argument("repo_root", nargs="?", default=".",
                        help="repository root (default: current directory)")
    args = parser.parse_args(argv)

    try:
        synced = sync(args.repo_root)
    except (OSError, ValueError) as exc:
        print("sync_agents: %s" % exc, file=sys.stderr)
        return 1
    print("sync_agents: mirrored %d agent(s)" % len(synced))
    return 0


if __name__ == "__main__":
    sys.exit(main())
