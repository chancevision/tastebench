#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chance AI
"""Build a cue-conditioned eval assignment and the prompt banners.

Accompanies "How to Build a Benchmark That Actually Measures Taste"
(arXiv:2610.14707).

The schema materializes 10 `null`+`correct`+`misleading` families (20 conditioned
rows), but they are split=dev, unlabeled, and never rendered into a prompt banner.
This tool:

  * selects rows with a non-null `cue_type`
  * emits an eval assignment CSV (pair_id, item_a, item_b, cue_type, condition_*)
  * renders the era/circle banner text that must be injected into the brief

It does NOT create labels. Scoring conditioned rows still requires expert gold for
the conditioned rows; cue-conditioned scoring is not reported in the current
release (see the paper's limitations).

Usage
  python build_cue_assignment.py \
      --pairs bench_pairs.csv \
      --out   cue_eval_assignment.csv
"""
from __future__ import annotations

import argparse
import csv
import sys


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def cue_banner(condition_era: str, condition_circle: str) -> str:
    """Render the conditioning instruction injected ahead of the brief."""
    parts = []
    if condition_era:
        parts.append(f"era = {condition_era}")
    if condition_circle:
        parts.append(f"circle = {condition_circle}")
    if not parts:
        return ""
    return (
        "Judge fit for the stated prior: " + "; ".join(parts) + ".\n"
        "The prior modifies what counts as appropriate; craft is still required.\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = read_csv(args.pairs)
    out = []
    for r in rows:
        cue = (r.get("cue_type") or "").strip()
        if cue in ("", "null"):
            continue
        era = (r.get("condition_era") or "").strip()
        circle = (r.get("condition_circle") or "").strip()
        out.append({
            "pair_id": r.get("pair_id", ""),
            "pair_group_id": r.get("pair_group_id", ""),
            "domain": r.get("domain", ""),
            "item_a": r.get("item_a", ""),
            "item_b": r.get("item_b", ""),
            "cue_type": cue,
            "condition_era": era,
            "condition_circle": circle,
            "split": r.get("split", ""),
            "cue_banner": cue_banner(era, circle).replace("\n", " ").strip(),
        })

    if not out:
        print("no conditioned rows found (nothing to write)")
        return 0

    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"wrote {len(out)} conditioned rows -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
