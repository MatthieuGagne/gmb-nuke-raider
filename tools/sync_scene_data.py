#!/usr/bin/env python3
"""Keep docs/memory-explained.html's SCENE_DATA block in sync with src/config.h.

The HTML explainer embeds `const SCENE_DATA = {...}` between marker comments. This
regenerates that block from memory_check.scenes_json(), so the per-scene OAM model
in the explainer never drifts from the build's view of config.h.

Idempotent: writing the same model twice produces identical bytes (no git churn).
Existing line endings (LF or CRLF) are preserved.

Usage:
    python tools/sync_scene_data.py [repo_root]            # write
    python tools/sync_scene_data.py --check [repo_root]    # exit 1 if out of sync
    or imported: sync_scene_data.sync(repo_root, check=False) -> int (0 ok, 1 problem)
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_check

BEGIN = '/* SCENE_DATA:BEGIN */'
END = '/* SCENE_DATA:END */'
HTML_REL = os.path.join('docs', 'memory-explained.html')


def _block(repo_root, nl):
    """Build the replacement block (markers + JS literal) using newline `nl`."""
    model = memory_check.scenes_json(repo_root)
    raw = BEGIN + '\n' + 'const SCENE_DATA = ' + json.dumps(model, indent=2) + ';\n' + END
    return raw.replace('\n', nl)


def sync(repo_root='.', check=False):
    """Regenerate (or, with check=True, validate) the HTML SCENE_DATA block.

    Returns 0 on success / already-in-sync, 1 on missing markers or (check mode) drift.
    """
    path = os.path.join(repo_root, HTML_REL)
    with open(path, 'r', encoding='utf-8', newline='') as f:
        content = f.read()

    if BEGIN not in content or END not in content:
        print(f"sync_scene_data: markers {BEGIN} .. {END} not found in {HTML_REL}", file=sys.stderr)
        return 1

    nl = '\r\n' if '\r\n' in content else '\n'
    pat = re.compile(re.escape(BEGIN) + '.*?' + re.escape(END), re.S)
    new = pat.sub(lambda m: _block(repo_root, nl), content, count=1)

    if new == content:
        return 0
    if check:
        print(f"sync_scene_data: {HTML_REL} OAM scene data is stale — "
              f"run `make` or `python tools/sync_scene_data.py`", file=sys.stderr)
        return 1

    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(new)
    print(f"sync_scene_data: updated {HTML_REL}")
    return 0


def main():
    args = sys.argv[1:]
    check = '--check' in args
    args = [a for a in args if a != '--check']
    repo_root = args[0] if args else '.'
    sys.exit(sync(repo_root, check=check))


if __name__ == '__main__':
    main()
