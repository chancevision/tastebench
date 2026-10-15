# tastebench — code

Reference code for **How to Build a Benchmark That Actually Measures Taste**
([arXiv:2610.14707](https://arxiv.org/abs/2610.14707)). MIT licensed — see [`LICENSE`](LICENSE).

| Script | What it does |
|---|---|
| [`tastebench_eval.py`](tastebench_eval.py) | reference eval harness: predictions CSV → metrics JSON. Enforces the frozen contract — gold is `bench_gold` only (weak labels never enter the test set), hard filter `n_raters ≥ 3` **and** percent agreement `≥ 0.60` (inclusive), `difficulty=ambiguous` / `exclude_primary` dropped. Reports pairwise accuracy overall and by domain, plus ECE and cue/group breakdowns when those columns exist. |
| [`randomize_pair_sides.py`](randomize_pair_sides.py) | side-randomization tool: re-emits a pair table with the preferred item in slot A ~50% of the time and records `preferred_side` / `swapped`. This is the tool that takes the position artifact from `0.916` to `0.495/0.505`. It only permutes existing rows — it never invents data. |
| [`build_cue_assignment.py`](build_cue_assignment.py) | builds the era/circle cue-conditioned eval assignment and renders the prompt banner that must be injected into the brief. Creates no labels. |
| [`paper2_diagnostics.py`](paper2_diagnostics.py) | the two derived diagnostics: `side_balance_audit.csv` (position imbalance) and `cross_domain_spread.csv` (per-card max−min domain spread). |
| [`make_paper2_figures.py`](make_paper2_figures.py) | regenerates the five figures from the aggregate artifacts. |
| [`prompts/prompt_v2.txt`](prompts/prompt_v2.txt) | the `prompt_v2` judge template (two-line `PREFERRED` / `CONFIDENCE` output). |
| [`prompts/prompt_cue_v1.txt`](prompts/prompt_cue_v1.txt) | the cue-conditioned variant, which injects `{cue_banner}` for era/circle priors. |

```bash
# score a run
python tastebench_eval.py \
    --preds preds.csv \
    --gold bench_gold_primary_human.csv \
    --out metrics.json

# re-balance a pair table before scoring it
python randomize_pair_sides.py \
    --pairs bench_pairs.csv \
    --gold bench_gold_primary_human.csv \
    --seed 20261010 \
    --out bench_pairs_siderandomized.csv
```

`--assignment pair_id,item_a,item_b[,split]` resolves predictions given as `pred_side` (A/B) instead of
`pred_preferred_id` — that is how the paper's randomized assignment (`eval_assignment_seed7`) is scored.

## Inputs

Only the harness and the randomization tool run on stdlib alone. `paper2_diagnostics.py` and
`make_paper2_figures.py` read the release aggregate artifacts, whose directory is configurable:

```bash
export TASTEBENCH_RESULTS=/path/to/results   # default: ./results
export TASTEBENCH_FIGURES=/path/to/figures   # default: ./figures
python -m pip install -r requirements.txt    # matplotlib, numpy (figure script only)
```

Expected layout under `TASTEBENCH_RESULTS`: `vlm/vlm_main_table.csv`, `vlm/cross_domain_spread.csv`,
`tastebench_baselines_summary.csv`, `primary_gold_summary.json`, `hard_subset/craft_hard_subset.csv`,
`hard_subset/vlm_acc_on_hard_subset.json`. `tastebench_eval.py` runs on any pair table with the
columns in the header above.

## Notes

`tastebench_eval.py` implements the eval contract described in §5.3 of the paper. It is a reference
implementation of the protocol rather than the exact script used for the Round-1 run.
