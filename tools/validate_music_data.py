#!/usr/bin/env python3
"""Validate that hUGESong order_cnt matches the actual order array lengths."""
import re
import sys

PATH = "src/music_data.c"

def count_order_entries(src: str, array_name: str) -> int:
    m = re.search(rf"const unsigned char\* const {array_name}\[\]\s*=\s*\{{([^}}]+)\}}", src)
    if not m:
        raise ValueError(f"Array {array_name} not found")
    entries = [e.strip() for e in m.group(1).split(",") if e.strip()]
    return len(entries)

def get_order_cnt(src: str) -> int:
    m = re.search(r"static const unsigned char order_cnt\s*=\s*(\d+)\s*;", src)
    if not m:
        raise ValueError("order_cnt not found")
    return int(m.group(1))

def main():
    with open(PATH) as f:
        src = f.read()

    order_cnt = get_order_cnt(src)
    errors = []

    for name in ("order1", "order2", "order3", "order4"):
        length = count_order_entries(src, name)
        if length != order_cnt:
            errors.append(f"  {name}: {length} entries, expected {order_cnt}")

    if errors:
        print(f"FAIL: order_cnt={order_cnt} does not match order array lengths:")
        for e in errors:
            print(e)
        sys.exit(1)
    else:
        print(f"PASS: order_cnt={order_cnt} matches all order arrays.")

if __name__ == "__main__":
    main()
