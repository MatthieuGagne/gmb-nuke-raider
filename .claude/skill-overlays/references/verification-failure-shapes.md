# Verifying Verification Steps — the three failure shapes

Extracted from the `writing-plans` overlay.

Every verification command in a plan must be paired with evidence it *can* fail, not only that
it passes. A check that always passes on the correct file is not a check — it is a statement of
the file's current state, and it will never catch a regression.

For each verification command in a plan, the plan must name either (a) the input flip that makes
the check fail, or (b) a probe file that triggers the failure.

Three failure shapes, observed in
[#441](https://github.com/MatthieuGagne/gmb-nuke-raider/issues/441):

1. **Self-defeating assert.** The check's own assertion string appears in the file being checked,
   so the assert passes on the correct file and fails on nothing. Example:
   `assert 'paths:' not in text` where the file's own comment explaining *why* there is no
   `paths:` filter contains that string. Fix: use a YAML-key regex (`^\s*paths:`) that cannot
   appear in the comment.

2. **Platform-wrong assertion.** The assertion hardcodes a platform-specific value (file
   extension, path separator, casing) that differs on the other platform the CI matrix covers.
   Example: asserting `find_make(...) == 'make.exe'` on a CI leg that runs `windows-latest` where
   `PATHEXT` returns `make.EXE`. Fix: normalize both sides with `os.path.normcase` before
   comparing.

3. **Environment-dependent test.** The check passes when run directly but fails under the hook or
   agent it was written for, because the hook/agent exports environment variables that override
   `cwd` or other assumptions. Example: `git config --local` reads the wrong repo under `GIT_DIR`
   exported by git into every hook's environment. Fix: scrub `GIT_DIR` (and friends) before
   running any git command, or use `install_hooks.clean_env()`.
