# Adversarial charter — final whole-branch review

Extracted from the `subagent-driven-development` overlay. **Append the blockquote below to the
final whole-branch review dispatch** — the one the baseline's `## Final Review` describes,
dispatched with `../requesting-code-review/code-reviewer.md` on the baseline's most capable
model, which this charter does not change.

**Precedence, stated so the reviewer is not handed two contradictory instructions.** The
five-field finding form below **replaces** the baseline charter's per-issue format (File:line /
What's wrong / Why it matters / How to fix) — its four fields all survive inside the new ones.
Everything else in the baseline charter stands unchanged: the Critical / Important / Minor
headings, the Strengths and Recommendations sections, the `Ready to merge?` verdict, and
`## Read-Only Review`.

---

> **Adversarial charter — applies to every finding you report.**
>
> A finding is a claim about this branch, not an impression of it. Report each one in this form,
> under the severity heading you judge it to belong to:
>
> - **Claim:** one sentence — the defect you assert, and why it matters.
> - **Location:** `file:line` on this branch, with the lines quoted. Quote what you actually read.
> - **Disproof attempt:** what you did to show your own claim is wrong, and what happened.
> - **Evidence:** per the bar below.
> - **Blocking:** `yes` only when the evidence bar is met; otherwise `no — unverified`.
> - **Fix:** what to change.
>
> **Try to disprove your own finding before you report it.** Re-read the cited lines in full
> context. Look for the caller, guard, default, or existing test that makes the behaviour
> correct. Ask what the author would say. **A finding you disprove is dropped, not softened** —
> re-filing it at a lower severity instead of deleting it is the exact failure this charter
> exists to prevent.
>
> **Dropping is not discarding silently.** Close your report with a `### Disproved and dropped`
> list: one line per finding you killed, naming the claim and what disproved it. A reviewer that
> drops five findings and reports one must not read the same as a reviewer that found one.
>
> **The evidence bar depends on what the finding claims.**
>
> - A **runtime-behaviour** claim — wrong output, a crash, a corrupted value, a state machine
>   that goes the wrong way — meets the bar only with a re-runnable command and its actual
>   output: a failing host test case, or a `tools/smoketest_headless.py` scenario that fails on
>   this branch. Quote the command and the failing assertion.
> - A **static** claim — a banking pragma, an allowlist rule, a missing `bank-manifest.json`
>   entry, a missing test, two documents that contradict each other — meets the bar on **citation
>   verification alone.** Open the cited location, confirm it says what your finding says it
>   says, and report it. No test and no scenario is asked of a static finding. A citation that
>   does not survive that check is a disproved finding: drop it, and list it as dropped.
>
> **Produce evidence without writing into this checkout.** The read-only rule still binds, and
> both runners below default to writing inside the tree — so redirect their output. Write your
> repro test or scenario file in a temp directory, and:
>
> - **Host test** — run the compiler **from the repository root** (every include path below is
>   root-relative) and send the binary outside the tree. These are `make test`'s own flags,
>   expanded (`Makefile:43-47, 243-249`):
>   ```
>   gcc -Itests/mocks -Itests/unity/src -Isrc -Ilib/hUGEDriver/include -Wall -Wextra \
>       -DDEBUG_MAILBOX \
>       tests/unity/src/unity.c $(ls src/*.c | grep -v 'src/main.c$') tests/mocks/*.c \
>       <tmp>/your_test.c -o <tmp>/your_test.exe
>   ```
>   `-DDEBUG_MAILBOX` is part of `TEST_FLAGS`; omit it and modules guarded by it compile away,
>   so your repro can fail for a reason that has nothing to do with your finding.
>   Every test links the whole library, so do not copy a module out and seed it — you get
>   duplicate symbols. Write a new test against the code as it stands.
> - **Scenario** — `python tools/smoketest_headless.py --scenario <tmp>/your-scenario.json
>   --out-dir <tmp>/smoketest --json`. `--out-dir` is required here: its default writes
>   screenshots, `trace.jsonl` and `results.json` into `build/smoketest` inside the checkout.
>
> **`Blocking` is a separate marker from severity, and never a cap on it.** Judge Critical /
> Important / Minor on the merits exactly as the severity section defines them, and never lower a
> severity because evidence was hard to get. `Blocking: no — unverified` says "not yet shown",
> never "not important".
>
> **An unverified finding is still reported, in full.** Say what you could not demonstrate and
> name, in one line, the test or scenario that would settle it. Staying quiet about a finding you
> could not demonstrate is worse than reporting it honestly labelled.
>
> **Nothing you report blocks anything.** No finding aborts the run, and none makes the pull
> request unmergeable — you report, and the human decides at the pull request. This is about the
> run and the merge, not about the controller: the baseline's fix wave, its scoped re-review and
> its adjudication of residual findings are unchanged.
