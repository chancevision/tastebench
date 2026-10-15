#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chance AI
"""Derived diagnostics for the TasteBench paper.

Accompanies "How to Build a Benchmark That Actually Measures Taste"
(arXiv:2610.14707).

Derives two honest, artifact-only tables from EXISTING files (no new data,
no model runs, no fabricated numbers):

  side_balance_audit.csv     -- position/A-B imbalance
      * full-250: from tastebench_baselines_summary.csv (always_item_a ==
        P(preferred is item_a); always_item_b == P(preferred is item_b))
      * 107-pair hard subset: true per-pair counts from craft_hard_subset.csv
        (item_a / item_b / preferred_id present)

  cross_domain_spread.csv    -- zero-shot cross-domain consistency
      * from vlm_main_table.csv: per-card max/min domain accuracy and spread.
        This is a SPREAD, not a transfer matrix: the models are zero-shot, so
        there is no in-domain adaptation to measure transfer against.

Reads and writes under $TASTEBENCH_RESULTS (default ./results).

Usage:  python paper2_diagnostics.py
"""
from __future__ import annotations

import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.environ.get("TASTEBENCH_RESULTS", os.path.join(ROOT, "results"))


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows, header):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    print("wrote", os.path.relpath(path, ROOT))


def side_balance_audit():
    rows = []
    # --- full-250, by domain, from baselines summary (aggregate) ---
    base = read_csv(os.path.join(RES, "tastebench_baselines_summary.csv"))
    by = {r["baseline"]: r for r in base}
    a, b = by.get("always_item_a"), by.get("always_item_b")
    summary = json.load(open(os.path.join(RES, "primary_gold_summary.json")))
    dom_pairs = {d: v["pairs"] for d, v in summary["by_domain"].items()}
    if a and b:
        rows.append(["full_250", "all", a["n"], a["acc"], b["acc"]])
        for dom in ("book", "brand", "tech", "visual"):
            rows.append(["full_250", dom, dom_pairs.get(dom, ""),
                         a[f"acc_{dom}"], b[f"acc_{dom}"]])

    # --- 107-pair hard subset, true per-pair counts ---
    hard = read_csv(os.path.join(RES, "hard_subset", "craft_hard_subset.csv"))
    from collections import defaultdict
    cnt = defaultdict(lambda: [0, 0])  # dom -> [pref_is_a, pref_is_b]
    for r in hard:
        dom = r["domain"]
        pa = int(str(r["preferred_id"]) == str(r["item_a"]))
        pb = int(str(r["preferred_id"]) == str(r["item_b"]))
        cnt[dom][0] += pa
        cnt[dom][1] += pb
    tot = [sum(v[0] for v in cnt.values()), sum(v[1] for v in cnt.values())]
    n = tot[0] + tot[1]
    rows.append(["hard_subset_107", "all", n,
                 round(tot[0] / n, 4), round(tot[1] / n, 4)])
    for dom in sorted(cnt):
        ca, cb = cnt[dom]
        m = ca + cb
        rows.append(["hard_subset_107", dom, m, round(ca / m, 4), round(cb / m, 4)])

    write_csv(
        os.path.join(RES, "vlm", "side_balance_audit.csv"),
        rows,
        ["scope", "domain", "n", "p_preferred_is_item_a", "p_preferred_is_item_b"],
    )


def cross_domain_spread():
    rows = []
    for r in read_csv(os.path.join(RES, "vlm", "vlm_main_table.csv")):
        doms = {d: float(r[f"acc_{d}"]) for d in ("book", "brand", "tech", "visual")}
        hi = max(doms.values())
        lo = min(doms.values())
        rows.append([
            r["model"], r["openrouter_id"],
            f"{doms['book']}", f"{doms['brand']}", f"{doms['tech']}", f"{doms['visual']}",
            f"{hi - lo:.4f}",
        ])
    # baselines as reference floors
    for r in read_csv(os.path.join(RES, "tastebench_baselines_summary.csv")):
        doms = {d: float(r[f"acc_{d}"]) for d in ("book", "brand", "tech", "visual")}
        rows.append([
            f"[baseline] {r['baseline']}", "",
            f"{doms['book']}", f"{doms['brand']}", f"{doms['tech']}", f"{doms['visual']}",
            f"{max(doms.values()) - min(doms.values()):.4f}",
        ])
    write_csv(
        os.path.join(RES, "vlm", "cross_domain_spread.csv"),
        rows,
        ["model", "openrouter_id", "book", "brand", "tech", "visual", "spread_max_minus_min"],
    )


if __name__ == "__main__":
    side_balance_audit()
    cross_domain_spread()
