---
name: build
description: Use this skill to build the GBC ROM. Triggers when verifying a build, checking for compiler errors, or confirming the ROM was produced after making changes.
---

Run `GBDK_HOME=/home/mathdaman/gbdk make`.

On success: report ROM size with `ls -lh build/nuke-raider.gb`.

On failure: extract lines containing "error:" from the output, show each as
`file:line: message`. Distinguish compiler errors (fixable in source) from
linker errors. Identify which file to look at first. Do not attempt to fix
errors automatically unless the user asks.
