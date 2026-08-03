#!/usr/bin/env python3
"""ste_lint.py — report ASD-STE100 writing-rule violations in Markdown (#517).

Two finding classes, two outcomes:

  * An ASD-STE100 rule finding never fails the linter (R9). The detectors are
    approximations and they will produce false positives; a finding a reader
    dismisses costs less than a gate a reader learns to bypass.
  * A banned-synonym hit fails with exit 1 (R10). The banned words come out of
    the ``_Avoid_`` lists in CONTEXT.md, which outranks ASD-STE100 on word
    choice (R4) because it is this project's own glossary.

Usage:
    python tools/ste_lint.py FILE [FILE ...]
    python tools/ste_lint.py --all
    python tools/ste_lint.py --all --write-baseline
    python tools/ste_lint.py --issue 517
"""
import argparse
import collections
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys

REPO = "MatthieuGagne/gmb-nuke-raider"

RULE_LONG_INSTRUCTION = "long-instruction"
RULE_LONG_DESCRIPTION = "long-description"
RULE_PERFECT_TENSE = "perfect-tense"
RULE_PASSIVE = "passive-voice"
RULE_NOUN_CLUSTER = "noun-cluster"
RULE_MULTI_INSTRUCTION = "multi-instruction"
RULE_LONG_PARAGRAPH = "long-paragraph"
RULE_BANNED = "banned-synonym"

# The seven reporting rules (R8). RULE_BANNED is deliberately absent: it is the
# one finding class that fails the linter, so it is never "an ASD-STE100 rule".
RULES = (RULE_LONG_INSTRUCTION, RULE_LONG_DESCRIPTION, RULE_PERFECT_TENSE,
         RULE_PASSIVE, RULE_NOUN_CLUSTER, RULE_MULTI_INSTRUCTION,
         RULE_LONG_PARAGRAPH)

INSTRUCTION_CAP = 20
DESCRIPTION_CAP = 25
PARAGRAPH_CAP = 6
CLUSTER_CAP = 4

Finding = collections.namedtuple("Finding", "path line rule text message")

# A sentence whose first word is one of these reads as an instruction, so it
# takes the tighter 20-word cap. Deliberately a small list: an imperative this
# misses only relaxes the cap by five words.
IMPERATIVES = frozenset("""
add append apply avoid build call check close commit copy create delete
dispatch do drop edit ensure fetch find fix follow give go install invoke keep
launch let list load make merge move name never note open pass prefer print
put read record remove rename replace report resolve return run save scan see
send set show start stop treat update use verify wrap write always
""".split())

# Words that break a noun cluster. Anything not here counts as a cluster
# member, which over-reports; R9 makes that harmless.
FUNCTION_WORDS = frozenset("""
a an the and or but nor so yet for of to in on at by with from into over under
is are was were be been being am do does did has have had can could may might
must shall should will would not no if then than that this these those it its
their his her our your my as also when while because per via up out off about
""".split())

PASSIVE_RE = re.compile(
    r"\b(is|are|was|were|be|been|being)\s+(?:not\s+|never\s+|already\s+)?"
    r"(\w+ed|written|given|taken|made|done|set|put|kept|held|read|built|sent|"
    r"left|lost|found|known|shown|seen|run|drawn|thrown|torn|shed)\b",
    re.I)

PERFECT_RE = re.compile(
    r"\b(has|have|had)\s+(?:not\s+|never\s+|already\s+)?"
    r"(been|\w+ed|written|given|taken|made|done|gone|come|seen|shown|known|"
    r"built|kept|held|sent|left|lost|found|run|read|put|set)\b",
    re.I)

MULTI_RE = re.compile(r",\s+(?:and|then|or)\s+|\s+and\s+then\s+|;\s+", re.I)

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\u2019-]*")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


# --------------------------------------------------------------------------
# Glossary
# --------------------------------------------------------------------------

TERM_RE = re.compile(r"^\*\*(.+?)\*\*:\s*$", re.M)
AVOID_RE = re.compile(r"^_Avoid_:\s*(.*(?:\n(?!\n|\*\*|#|_Avoid_).*)*)", re.M)


def parse_glossary(text):
    """Return [(banned_word_lowercase, glossary_term)] from CONTEXT.md text.

    An ``_Avoid_`` line is a comma-separated list, sometimes followed by prose
    after an em dash ("history — and never a **Stage log**, which holds ...").
    The prose is explanation, not a ban, so everything from the first em dash on
    is dropped. Entries carrying bold markup are cross-references, not words.
    """
    terms = TERM_RE.findall(text)
    avoids = AVOID_RE.findall(text)
    out = []
    for term, avoid in zip(terms, avoids):
        flat = " ".join(avoid.split()).split("\u2014")[0]
        for word in flat.split(","):
            word = word.strip().strip(".").lower()
            if word and "**" not in word:
                out.append((word, term))
    return out


def load_glossary(root):
    path = os.path.join(root, "CONTEXT.md")
    try:
        with open(path, encoding="utf-8") as fh:
            return parse_glossary(fh.read())
    except OSError:
        return []


# --------------------------------------------------------------------------
# Markdown
# --------------------------------------------------------------------------

def strip_code(text):
    """Blank out fenced code blocks, keeping the line count intact.

    Line numbers stay usable and a command in a code block never trips a prose
    rule. Out of scope keeps this to Markdown, so nothing here reads Python.
    """
    out = []
    fenced = False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            out.append("")
            continue
        out.append("" if fenced else line)
    return out


def _is_prose(line):
    # The indent test reads the raw line: `line.strip().startswith("    ")` can
    # never be true, so an indented code block would scan as prose.
    if line.startswith("    ") or line.startswith("\t"):
        return False
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(("|", "#", ">", "---", "===")):
        return False
    return True


def paragraphs(lines):
    """Yield (start_line_number, joined_text) for each prose paragraph."""
    buf = []
    start = 0
    for number, line in enumerate(lines, 1):
        if _is_prose(line):
            if not buf:
                start = number
            buf.append(line.strip())
        elif buf:
            yield start, " ".join(buf)
            buf = []
    if buf:
        yield start, " ".join(buf)


def _bullet_text(sentence):
    """Strip a leading list marker so 'Run x.' and '- Run x.' agree."""
    return re.sub(r"^(?:[-*+]|\d+\.)\s+", "", sentence).strip()


def sentences(paragraph):
    for raw in SENTENCE_SPLIT_RE.split(paragraph):
        raw = raw.strip()
        if raw:
            yield raw


def is_instruction(sentence):
    words = WORD_RE.findall(_bullet_text(sentence))
    return bool(words) and words[0].lower() in IMPERATIVES


def noun_cluster(sentence):
    """Longest run of consecutive non-function words."""
    best = 0
    run = 0
    for word in WORD_RE.findall(sentence):
        low = word.lower()
        if low in FUNCTION_WORDS or low.endswith("ly") or low in IMPERATIVES:
            run = 0
        else:
            run += 1
            best = max(best, run)
    return best


# --------------------------------------------------------------------------
# Scanning
# --------------------------------------------------------------------------

def _finding(path, line, rule, text, message):
    return Finding(path=path, line=line, rule=rule, text=text, message=message)


def scan_text(path, text, banned):
    """Every finding in one Markdown document, in file order."""
    lines = strip_code(text)
    out = []

    lowered = [line.lower() for line in lines]
    for word, term in banned:
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])")
        for number, line in enumerate(lowered, 1):
            for _ in pattern.finditer(line):
                out.append(_finding(
                    path, number, RULE_BANNED, word,
                    'banned word "%s" — CONTEXT.md reserves this meaning for '
                    '"%s"' % (word, term)))

    for start, para in paragraphs(lines):
        found = list(sentences(para))
        if len(found) > PARAGRAPH_CAP:
            out.append(_finding(
                path, start, RULE_LONG_PARAGRAPH, para[:200],
                "paragraph has %d sentences (limit %d)"
                % (len(found), PARAGRAPH_CAP)))
        for sentence in found:
            body = _bullet_text(sentence)
            count = len(WORD_RE.findall(body))
            instruction = is_instruction(sentence)
            cap = INSTRUCTION_CAP if instruction else DESCRIPTION_CAP
            rule = (RULE_LONG_INSTRUCTION if instruction
                    else RULE_LONG_DESCRIPTION)
            if count > cap:
                out.append(_finding(
                    path, start, rule, body,
                    "sentence has %d words (limit %d)" % (count, cap)))
            if PERFECT_RE.search(body):
                out.append(_finding(path, start, RULE_PERFECT_TENSE, body,
                                    "perfect tense — use the simple tense"))
            if PASSIVE_RE.search(body):
                out.append(_finding(path, start, RULE_PASSIVE, body,
                                    "passive voice — name the actor"))
            cluster = noun_cluster(body)
            if cluster >= CLUSTER_CAP:
                out.append(_finding(
                    path, start, RULE_NOUN_CLUSTER, body,
                    "noun cluster of %d words" % cluster))
            if instruction and MULTI_RE.search(body):
                out.append(_finding(path, start, RULE_MULTI_INSTRUCTION, body,
                                    "more than one instruction in a sentence"))
    return out


def scan_file(path, banned, display=None):
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    return scan_text(display or path, text, banned)


def key_of(finding):
    """Baseline identity: rule plus a hash of the offending text.

    The line number is left out on purpose. Editing the top of a file must not
    resurface every finding below it.
    """
    digest = hashlib.sha1(finding.text.encode("utf-8")).hexdigest()[:12]
    return "%s:%s" % (finding.rule, digest)


def render(finding):
    return "%s:%d: %s: %s" % (finding.path, finding.line, finding.rule,
                              finding.message)


# --------------------------------------------------------------------------
# Discovery and baseline
# --------------------------------------------------------------------------

# R12. The set is intersected with `git ls-files` (P1): docs/plans/ is
# gitignored but carries two tracked legacy plans, so a bare glob would mix
# tracked documents with whatever local plans a machine happens to hold, and
# the baseline would stop being reproducible.
# A bare "*.md" is NOT usable here: fnmatch translates `*` to `.*`, which
# matches `/`, so it would sweep tests/unity/docs/, .pi/agents/, src/CLAUDE.md
# and every other Markdown file in the tree — 82 files instead of the R12 set,
# and a 172 KB baseline mostly made of vendored Unity documentation. The
# repository-root rule is expressed as "no slash in the path" instead.
INCLUDE_GLOBS = (
    "docs/**/*.md",
    ".claude/skills/**/*.md",
    ".claude/agents/**/*.md",
    "tests/fixtures/factory/expected_*.md",
)
EXCLUDE_PATHS = ("docs/STORY_BIBLE.md", "CLAUDE.local.md")
EXCLUDE_PREFIXES = ("docs/game/", ".claude/skill-overlays/",
                    ".claude/skills/simplified-technical-english/")

BASELINE_NAME = os.path.join("tools", "ste_baseline.json")
BASELINE_VERSION = 1


def tracked_files(root):
    proc = subprocess.run(["git", "-C", root, "ls-files"],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("git ls-files failed: %s" % proc.stderr.strip())
    return [line.strip() for line in proc.stdout.split("\n") if line.strip()]


def _included(path):
    if not path.endswith(".md"):
        return False
    if path in EXCLUDE_PATHS:
        return False
    if any(path.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
        return False
    if "/" not in path:                 # R12: repository-root *.md
        return True
    for glob in INCLUDE_GLOBS:
        if "**" in glob:
            head, _, tail = glob.partition("**/")
            if path.startswith(head) and fnmatch.fnmatch(
                    os.path.basename(path), tail):
                return True
        elif fnmatch.fnmatch(path, glob):
            return True
    return False


def discover(root, tracked=None):
    """The `--all` file set: repo-relative POSIX paths, sorted, deduplicated."""
    if tracked is None:
        tracked = tracked_files(root)
    found = {p.replace("\\", "/") for p in tracked}
    return sorted(p for p in found if _included(p))


def load_baseline(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data.get("findings") or {}


def write_baseline(path, findings):
    counts = {}
    for finding in findings:
        counts.setdefault(finding.path, {})
        key = key_of(finding)
        counts[finding.path][key] = counts[finding.path].get(key, 0) + 1
    payload = {"version": BASELINE_VERSION,
               "note": "Pre-existing findings (#517 R11). Forward-only: this "
                       "file records what the tree already said, it does not "
                       "excuse new prose.",
               "findings": {path: dict(sorted(keys.items()))
                            for path, keys in sorted(counts.items())}}
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def suppress(findings, baseline):
    """Drop findings the baseline already records, counting repeats."""
    budget = {path: dict(keys) for path, keys in baseline.items()}
    out = []
    for finding in findings:
        key = key_of(finding)
        left = budget.get(finding.path, {}).get(key, 0)
        if left > 0:
            budget[finding.path][key] = left - 1
            continue
        out.append(finding)
    return out


def run_all(root, banned, write=False, baseline_path=None, tracked=None):
    """Lint the tracked documentation set. Always exits 0 (P7).

    `--all` runs inside `make test-tools`, which CI gates on; the pre-commit
    hook runs the unittest suite directly and reaches `--all` through the
    `RunAllTests` test rather than through `make`. Baseline suppression is
    keyed on the offending text, so one more
    ``step`` or ``build`` in any scanned document is a non-baselined
    banned-synonym hit — 750 and 431 of those words already sit in the tree.
    Failing here would turn the next ordinary documentation change red for a
    word nobody can avoid. The hit still prints, and the file-path and
    ``--issue`` forms still exit 1, which is where an author can act on it.
    """
    baseline_path = baseline_path or os.path.join(root, BASELINE_NAME)
    findings = []
    for rel in discover(root, tracked=tracked):
        findings += scan_file(os.path.join(root, rel), banned, display=rel)
    if write:
        write_baseline(baseline_path, findings)
        print("ste_lint: baseline written to %s (%d findings)"
              % (baseline_path, len(findings)))
        return 0
    fresh = suppress(findings, load_baseline(baseline_path))
    _report(fresh)
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _fetch_issue_body(issue_number):
    """Fetch a GitHub issue body via gh. Raise RuntimeError on failure."""
    result = subprocess.run(
        ["gh", "issue", "view", str(issue_number),
         "--repo", REPO, "--json", "body"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError("gh failed: %s" % result.stderr.strip())
    return json.loads(result.stdout)["body"]


def _report(findings, stream=None):
    # `stream=None`, resolved per call. A `stream=sys.stdout` default binds the
    # stream once at import time, so contextlib.redirect_stdout never sees the
    # output and every test that captures it asserts against an empty string.
    stream = sys.stdout if stream is None else stream
    for finding in findings:
        print(render(finding), file=stream)
    return 1 if any(f.rule == RULE_BANNED for f in findings) else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Report ASD-STE100 findings in Markdown (#517).")
    parser.add_argument("paths", nargs="*", help="Markdown files to lint")
    parser.add_argument("--all", action="store_true", dest="scan_all",
                        help="lint the tracked documentation set")
    parser.add_argument("--issue", type=int,
                        help="lint a GitHub issue body (via gh)")
    parser.add_argument("--write-baseline", action="store_true",
                        help="with --all, rewrite tools/ste_baseline.json")
    parser.add_argument("--root", default=".",
                        help="repository root (default: the current directory)")
    args = parser.parse_args(argv)

    banned = load_glossary(args.root)

    if args.issue is not None:
        try:
            body = _fetch_issue_body(args.issue)
        except (RuntimeError, ValueError, KeyError) as exc:
            print("ste_lint: %s" % exc, file=sys.stderr)
            return 2
        return _report(scan_text("issue #%d" % args.issue, body, banned))

    if args.scan_all:
        return run_all(args.root, banned, write=args.write_baseline)

    if not args.paths:
        parser.error("give one or more file paths, --all, or --issue N")

    findings = []
    for path in args.paths:
        try:
            findings += scan_file(path, banned)
        except OSError as exc:
            print("ste_lint: %s" % exc, file=sys.stderr)
            return 2
    return _report(findings)


if __name__ == "__main__":
    sys.exit(main())
