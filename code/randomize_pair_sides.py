#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chance AI
"""Randomize the A/B side at construction and record the resulting gold mapping.

Accompanies "How to Build a Benchmark That Actually Measures Taste"
(arXiv:2610.14707).

The Round-1 pair files put the preferred ("good") item in slot A far too often
(`always_item_a` floor = 0.956), which lets a position-only policy masquerade as
a strong model. This tool re-emits pairs with the preferred item placed in slot A
~50% of the time and records the mapping, so downstream eval cannot be gamed by
position.

It does NOT invent data: it only permutes item_a/item_b of an existing pair table.

Inputs
  --pairs  CSV with at least: pair_id, item_a, item_b
  --gold   CSV with pair_id, preferred_id  (optional: if omitted, read
           precreated `preferred_id` directly from --pairs)

Usage
  python randomize_pair_sides.py \
      --pairs bench_pairs.csv \
      --gold  bench_gold_primary_human.csv \
      --seed 20261010 \
      --out   bench_pairs_siderandomized.csv
"""
from __future__ import annotations

import argparse
import csv
import random
import sys


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--gold", default=None)
    ap.add_argument("--seed", type=int, default=20261010)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pairs = read_csv(args.pairs)
    gold = {r["pair_id"]: r["preferred_id"] for r in read_csv(args.gold)} if args.gold else {}

    rnd = random.Random(args.seed)
    before = {"A": 0, "B": 0, "?": 0}
    after = {"A": 0, "B": 0, "?": 0}
    out_rows = []
    for p in pairs:
        pid = p["pair_id"]
        a, b = str(p.get("item_a", "")), str(p.get("item_b", ""))
        pref = gold.get(pid, p.get("preferred_id", ""))

        # original side
        if pref == a:
            before["A"] += 1
        elif pref == b:
            before["B"] += 1
        else:
            before["?"] += 1

        swapped = False
        if pref in (a, b):
            want_pref_in_a = rnd.random() < 0.5
            if (pref == a) != want_pref_in_a:
                a, b = b, a
                swapped = True

        pref_side = "A" if pref == a else ("B" if pref == b else "?")
        after[pref_side] += 1
        row = dict(p)
        row["item_a"], row["item_b"] = a, b
        row["preferred_id"] = pref
        row["preferred_side"] = pref_side
        row["swapped"] = str(swapped)
        out_rows.append(row)

    fields = list(pairs[0].keys()) + ["preferred_side", "swapped"]
    fields = list(dict.fromkeys(fields + ["item_a", "item_b", "preferred_id"]))
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    n = sum(before.values())
    print(f"pairs={n}")
    print(f"before  P(pref in A)={before['A']/n:.4f}  P(pref in B)={before['B']/n:.4f}")
    print(f"after   P(pref in A)={after['A']/n:.4f}  P(pref in B)={after['B']/n:.4f}")
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
