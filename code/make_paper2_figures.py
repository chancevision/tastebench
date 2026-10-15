#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Chance AI
"""Generate the TasteBench figures from existing artifacts (no new data).

Accompanies "How to Build a Benchmark That Actually Measures Taste"
(arXiv:2610.14707).

Inputs (under $TASTEBENCH_RESULTS, default ./results): vlm/vlm_main_table.csv,
vlm/cross_domain_spread.csv, tastebench_baselines_summary.csv,
primary_gold_summary.json, hard_subset/vlm_acc_on_hard_subset.json.

Output ($TASTEBENCH_FIGURES, default ./figures):
  fig_accuracy_by_domain.pdf  VLM pairwise accuracy by domain (5 cards)
  fig_baselines_floors.pdf    non-VLM floors + chance line
  fig_agreement_by_domain.pdf human mean agreement by domain (panel saturation)
  fig_hard_subset.pdf         craft hard-subset accuracy by domain
  fig_domain_spread.pdf       zero-shot cross-domain spread (max-min) per card

Usage:  python make_paper2_figures.py
"""
from __future__ import annotations

import csv
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.environ.get("TASTEBENCH_RESULTS", os.path.join(ROOT, "results"))
OUT = os.environ.get("TASTEBENCH_FIGURES", os.path.join(ROOT, "figures"))
DOMAINS = ["book", "brand", "tech", "visual"]


def read_csv(p):
    with open(p, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def style():
    plt.rcParams.update({
        "figure.dpi": 150, "font.size": 9, "axes.grid": True,
        "grid.alpha": 0.3, "axes.axisbelow": True, "savefig.bbox": "tight",
    })


def fig_accuracy_by_domain():
    rows = read_csv(os.path.join(RES, "vlm", "vlm_main_table.csv"))
    models = [r["model"] for r in rows]
    x = np.arange(len(DOMAINS))
    w = 0.8 / len(models)
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    for i, r in enumerate(rows):
        vals = [float(r[f"acc_{d}"]) for d in DOMAINS]
        ax.bar(x + i * w - 0.4 + w / 2, vals, w, label=r["model"])
    ax.set_xticks(x, DOMAINS)
    ax.set_ylim(0.6, 1.02)
    ax.set_ylabel("pairwise accuracy")
    ax.axhline(0.5, color="k", lw=0.8, ls="--")
    ax.set_title("Round-1 VLM accuracy by domain (craft = ceiling)")
    ax.legend(ncol=2, fontsize=7, loc="lower right")
    fig.savefig(os.path.join(OUT, "fig_accuracy_by_domain.pdf"))
    plt.close(fig)


def fig_baselines_floors():
    rows = read_csv(os.path.join(RES, "tastebench_baselines_summary.csv"))
    names = [r["baseline"].replace("_", "\\_") for r in rows]
    vals = [float(r["acc"]) for r in rows]
    fig, ax = plt.subplots(figsize=(6.2, 3.0))
    cols = ["#d62728" if n.startswith("always") else ("#ff7f0e" if "leak" in n else "#1f77b4")
            for n in names]
    ax.bar(range(len(rows)), vals, color=cols)
    ax.axhline(0.5, color="k", lw=0.8, ls="--")
    ax.set_xticks(range(len(rows)), [n.replace("\\_", "_") for n in names],
                  rotation=20, ha="right", fontsize=7)
    ax.set_ylim(0, 1.02)
    ax.set_ylabel("accuracy")
    ax.set_title("Non-VLM floors: always_item_a is a construction artifact")
    fig.savefig(os.path.join(OUT, "fig_baselines_floors.pdf"))
    plt.close(fig)


def fig_agreement_by_domain():
    d = json.load(open(os.path.join(RES, "primary_gold_summary.json")))
    by = d["by_domain"]
    doms = [x for x in DOMAINS if x in by]
    vals = [by[x]["mean_agreement_primary"] for x in doms]
    ns = [by[x]["pairs"] for x in doms]
    fig, ax = plt.subplots(figsize=(6.0, 3.0))
    ax.bar(doms, vals, color="#2ca02c")
    for i, (v, n) in enumerate(zip(vals, ns)):
        ax.text(i, v + 0.002, f"{v:.4g}\n(n={n})", ha="center", fontsize=7)
    ax.set_ylim(0.9, 1.01)
    ax.axhline(0.60, color="k", lw=0.8, ls="--")
    ax.set_ylabel("mean percent agreement")
    ax.set_title("Human expert agreement by domain (saturated)")
    fig.savefig(os.path.join(OUT, "fig_agreement_by_domain.pdf"))
    plt.close(fig)


def fig_hard_subset():
    d = json.load(open(os.path.join(RES, "hard_subset", "vlm_acc_on_hard_subset.json")))
    res = d["results"]
    models = [r["model"] for r in res]
    x = np.arange(len(DOMAINS))
    w = 0.8 / len(models)
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    for i, r in enumerate(res):
        vals = [r["by_domain"][dm]["acc"] for dm in DOMAINS]
        ax.bar(x + i * w - 0.4 + w / 2, vals, w, label=r["model"])
    ax.set_xticks(x, DOMAINS)
    ax.set_ylim(0.6, 1.02)
    ax.set_ylabel("accuracy")
    ax.set_title("Post-hoc hard subset: craft still at ceiling")
    ax.legend(ncol=2, fontsize=7, loc="lower right")
    fig.savefig(os.path.join(OUT, "fig_hard_subset.pdf"))
    plt.close(fig)


def fig_domain_spread():
    rows = read_csv(os.path.join(RES, "vlm", "cross_domain_spread.csv"))
    rows = [r for r in rows if not r["model"].startswith("[baseline]")]
    models = [r["model"] for r in rows]
    spread = [float(r["spread_max_minus_min"]) for r in rows]
    order = np.argsort(spread)
    models = [models[i] for i in order]
    spread = [spread[i] for i in order]
    fig, ax = plt.subplots(figsize=(6.2, 3.0))
    ax.barh(models, spread, color="#9467bd")
    ax.set_xlabel("max domain acc - min domain acc")
    ax.set_title("Zero-shot cross-domain spread (smaller = more consistent)")
    fig.savefig(os.path.join(OUT, "fig_domain_spread.pdf"))
    plt.close(fig)


if __name__ == "__main__":
    style()
    os.makedirs(OUT, exist_ok=True)
    fig_accuracy_by_domain()
    fig_baselines_floors()
    fig_agreement_by_domain()
    fig_hard_subset()
    fig_domain_spread()
    print("figures ->", os.path.relpath(OUT, ROOT))
    for f in sorted(os.listdir(OUT)):
        print(" ", f)
