---
name: bank-post-build
description: Hard gate — invoke after a successful build, before smoketest. Runs make bank-post-build and reports the output.
---

# Bank Post-Build Gate

Run after `GBDK_HOME=/home/mathdaman/gbdk make` succeeds. Block proceeding to smoketest if exit code is 1.

```sh
make bank-post-build
```
Report the full output to the user. If exit code is 1, **BLOCK** and tell the user to fix the reported issue before proceeding to smoketest.

If exit code is 0, proceed — the script already printed the pass/warn status.

After `make bank-post-build` exits 0, run `make memory-check` (the `gb-memory-validator` skill) for WRAM/VRAM/OAM budget checks.
