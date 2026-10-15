#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chance AI
"""Reference eval harness for TasteBench.

Accompanies "How to Build a Benchmark That Actually Measures Taste"
(arXiv:2610.14707).

Reconstructed from the frozen contract:
  - the benchmark schema (rev2)
  - the paper's eval contract (Sec. 5.3)

Implements:
  - gold merge against `bench_gold` ONLY (never `bench_weak`)
  - hard filter: n_raters >= 3 AND percent agreement >= 0.60 (inclusive)
  - drop difficulty=ambiguous / exclude_primary
  - pairwise accuracy overall + by domain
  - ECE over correctness when a `confidence` column is present
  - accuracy by cue_type / pair_group_id when those columns are present

Usage:
  python tastebench_eval.py \
      --preds preds.csv \
      --gold bench_gold_primary_human.csv \
      --out metrics.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import defaultdict


def _f(row: dict, *keys: str) -> str | None:
    for k in keys:
        if k in row and row[k] not in ("", None):
            return row[k]
    return None


def load_rows(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def is_truthy(v: str | None) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y", "t"}


def gold_eligible(row: dict, require_split: str | None) -> bool:
    """Frozen hard filter. Returns True if the gold row enters the primary test set."""
    # drop ambiguous / excluded even if tags are wrong
    if "exclude_primary" in row and is_truthy(row.get("exclude_primary")):
        return False
    diff = _f(row, "difficulty")
    if diff is not None and diff.strip().lower() == "ambiguous":
        return False
    # expert panel size
    try:
        if int(float(_f(row, "n_raters") or 0)) < 3:
            return False
    except (TypeError, ValueError):
        return False
    # primary agreement gate (percent agreement, inclusive)
    try:
        if float(_f(row, "agreement") or 0.0) < 0.60:
            return False
    except (TypeError, ValueError):
        return False
    if require_split is not None:
        split = _f(row, "split")
        if split is not None and split.strip().lower() != require_split:
            return False
    return True


def resolve_prediction(row: dict, assignment: dict[str, dict] | None) -> str | None:
    """preds may carry `pred_preferred_id` directly, or `pred_side` (A/B) resolvable
    via an assignment table that maps pair_id -> {item_a, item_b}."""
    direct = _f(row, "pred_preferred_id")
    if direct:
        return direct
    side = _f(row, "pred_side", "prediction", "side")
    if side is None:
        return None
    if assignment is None:
        raise SystemExit(
            f"preds row for pair {row.get('pair_id')} has pred_side but no --assignment given"
        )
    pair = str(row.get("pair_id"))
    a = assignment.get(pair)
    if not a:
        return None
    side = side.strip().upper()
    if side == "A":
        return a.get("item_a")
    if side == "B":
        return a.get("item_b")
    return None


def ece(pairs: list[tuple[float, int]], bins: int = 10) -> float | None:
    """Expected calibration error over (confidence, correct) pairs."""
    if not pairs:
        return None
    total = len(pairs)
    acc = sum(correct for _, correct in pairs) / total
    err = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        bucket = [
            (c, y) for c, y in pairs
            if (lo <= c < hi) or (b == bins - 1 and c == 1.0)
        ]
        if not bucket:
            continue
        conf = sum(c for c, _ in bucket) / len(bucket)
        acc_b = sum(y for _, y in bucket) / len(bucket)
        err += (len(bucket) / total) * abs(acc_b - conf)
    return err


def accuracy(rows: list[dict]) -> float | None:
    if not rows:
        return None
    return sum(1 for r in rows if r["_correct"]) / len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="TasteBench reference eval")
    ap.add_argument("--preds", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--assignment", default=None,
                    help="optional pair_id,item_a,item_b[,split] table to resolve pred_side")
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", default="test",
                    help="split to require when a split column exists (default: test)")
    ap.add_argument("--bins", type=int, default=10)
    args = ap.parse_args()

    gold = load_rows(args.gold)
    preds = {str(r.get("pair_id")): r for r in load_rows(args.preds)}

    assignment = None
    if args.assignment:
        assignment = {str(r.get("pair_id")): r for r in load_rows(args.assignment)}

    merged: list[dict] = []
    n_gold = n_eligible = n_matched = n_unresolved = 0
    for g in gold:
        n_gold += 1
        if not gold_eligible(g, args.split):
            continue
        n_eligible += 1
        pair = str(g.get("pair_id"))
        p = preds.get(pair)
        if p is None:
            continue
        gold_id = str(_f(g, "preferred_id") or "")
        pred_id = resolve_prediction(p, assignment)
        if pred_id is None:
            n_unresolved += 1
            continue
        n_matched += 1
        rec = dict(g)
        rec["_pred_id"] = pred_id
        rec["_correct"] = int(str(pred_id) == gold_id)
        conf = _f(p, "confidence")
        if conf is not None:
            try:
                c = float(conf)
                if 0.0 <= c <= 1.0:
                    rec["_conf"] = c
            except ValueError:
                pass
        merged.append(rec)

    by_domain: dict[str, list[dict]] = defaultdict(list)
    by_cue: dict[str, list[dict]] = defaultdict(list)
    by_group: dict[str, list[dict]] = defaultdict(list)
    conf_pairs: list[tuple[float, int]] = []
    for r in merged:
        by_domain[str(r.get("domain", "unknown"))].append(r)
        if _f(r, "cue_type") is not None:
            by_cue[str(r.get("cue_type"))].append(r)
        if _f(r, "pair_group_id") is not None:
            by_group[str(r.get("pair_group_id"))].append(r)
        if "_conf" in r:
            conf_pairs.append((r["_conf"], r["_correct"]))

    metrics = {
        "n_gold_rows": n_gold,
        "n_gold_eligible": n_eligible,
        "n_eval": n_matched,
        "n_unresolved_pred": n_unresolved,
        "pairwise_acc": accuracy(merged),
        "by_domain": {d: {"n": len(rs), "acc": accuracy(rs)} for d, rs in sorted(by_domain.items())},
        "ece": ece(conf_pairs, args.bins) if conf_pairs else None,
        "by_cue_type": {c: {"n": len(rs), "acc": accuracy(rs)} for c, rs in sorted(by_cue.items())} or None,
        "by_pair_group_id": {g: {"n": len(rs), "acc": accuracy(rs)} for g, rs in sorted(by_group.items())} or None,
        "policy": (
            "gold=bench_gold only (weak never in test); hard-filter n_raters>=3 AND "
            "percent agreement>=0.60 inclusive; drop difficulty=ambiguous / exclude_primary; "
            "data_origin disclosed."
        ),
    }

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, sort_keys=False)
        fh.write("\n")

    print(json.dumps({k: metrics[k] for k in ("n_eval", "pairwise_acc", "ece")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
