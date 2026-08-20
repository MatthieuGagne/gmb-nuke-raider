---
summary: png_to_tiles.py silently mis-decodes RGB PNGs (defilter assumes 1 byte/pixel) — always emit indexed-colour mode "P" PNGs from Pillow generators; luminance error message is misleading
tags: [assets, png, tiles, pillow, png-to-tiles, sprites, tooling, bug]
---

# png_to_tiles.py mis-decodes RGB PNGs

`tools/png_to_tiles.py` advertises RGB PNG support but silently mis-decodes it; emit
indexed-colour PNGs instead. Related: [[loader-registry-and-tooling-checks]] for what
happens after conversion.

`tools/png_to_tiles.py` documents three accepted PNG formats, including "Color type 2
(RGB), bit depth 8" — but RGB input decodes to garbage. Its `_defilter_rows` uses
`row[i-1]` / `prev[i-1]` as the left neighbour for the Sub, Average and Paeth filters,
which is only correct at **1 byte per pixel**. RGB is 3 bytes per pixel and needs
`row[i-3]`.

The failure is misleading: Pillow picks adaptive per-row filters, the decode corrupts
most rows, and the tool then rejects the file with
`PNG has N distinct luminance values (max 4)` — pointing at the palette when the real
fault is the filter arithmetic. Indexed PNGs (colour type 3, bit depth 2 or 8) are
1 byte per pixel and decode correctly whatever filter is chosen.

**Why:** found while generating `assets/sprites/beam.png` in #430. A generator written
to the docstring (`Image.new("RGB", ...)`) fails on its first run and looks like an art
problem, not a tool bug.

**How to apply:** when adding a new tile/sprite asset generated with Pillow, emit mode
`"P"` (indexed, 4-entry palette), never mode `"RGB"` or `"L"` — mode `L` is colour
type 0 and is rejected outright. Verify the emitted C array by decoding the 2bpp bytes
by hand before trusting the art. The converter bug itself is unfixed and was out of
scope of #430; see PR #579 for the full diagnosis. Same class of raw-text/format
assumption biting a tool as the deny-gate quoted-command issue (memory store:
`project_deny_gate_matches_quoted_commands`).
