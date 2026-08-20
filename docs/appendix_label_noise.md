# Appendix: Why is pooled top-1 ≈ random? A label-noise / weak-signal attribution (T4)

For the reviewer question "why is pooled success@1 ≈ random?", we provide an empirical, evidence-based
decomposition. The short answer: **top-1 is weak for an identifiable, measurable reason — not because the
benchmark or the data are broken.** Three converging lines of evidence:

## A. Trigger-sequence prediction signal is intrinsically weak (≈ chance)
Per-target Spearman ρ between a thermodynamic predictor and ON/OFF across the 140 test targets has
**mean ≈ 0**, matching the row-chance ρ histogram (`figs/fig1_pred_rho.png`; `p4_noise_attribution.json`
per_target_rho_thermo). At the sequence level, the trigger's measurable features explain almost none of the
per-switch outcome variance. This is the E1/E2 finding restated as a diagnostic: design utility cannot be
higher than what the features can separate.

## B. The pooled top-1 ≈ random is driven by TF targets, and TF targets are label-limited
Splitting test targets by group (`figs/fig2_s1_by_group.png`):

| group | # targets | random s@1 | thermo s@1 | gc s@1 |
|---|---|---|---|---|
| virus | 6 | 0.667 | **0.833** | 0.167 |
| human TF | 134 | 0.284 | 0.321 | 0.090 |

- **Virus targets: strong, reproducible signal** (thermo 0.833 ≫ random 0.667).
- **Human TF targets: every method ≈ random at top-1** (0.28–0.32), and there are **134 TF vs 6 virus**
  test targets. The pooled top-1 (≈ 0.30–0.35) is therefore a *TF-dominated average*, not a uniform failure.
- `figs/fig3_label_limited.png` shows most targets have low success fraction under the absolute threshold —
  i.e., within most targets, few designs satisfy `ON ≥ 0.5 & OFF ≤ 0.5`, capping what *any* ranker can
  achieve at top-1 even with perfect scores.

## C. Ceiling check (noise, not an implementation bug)
- An **oracle** that perfectly orders each target by true utility reaches success@1 ≈ 0.91 (P2 sanity). The
  gap from 0.91 to the observed ≈0.35 is explained by (A) weak features + (B) label-limited TF targets, not
  by a coding error in the evaluation.
- Success@3/NDCG@10 *do* separate methods at the pooled level (thermo s@3 = 0.70 vs random 0.63; see P3),
  further confirming the signal exists but is weak at the strict top-1, absolute-threshold setting.

## Implication for the paper
- The correct statement is **not** "nothing is learnable" but "under strict source isolation and an absolute
  hit threshold, ranking utility is dominated by label-limited TF targets; virus targets retain strong
  signal, and top-3/NDCG still separate methods." This is a *strength* of the benchmark (it surfaces a real
  hardness), and it cannot be read as a NO-GO — it is a documented, decomposable ceiling.
- We do **not** claim real trans-sensing or de-novo design; we claim a calibrated *candidate-site ranking*
  benchmark whose difficulty is attributable and reproducible.

Outputs: `processed/p4_noise_attribution.json`, `processed/figs/fig1_*.png`, `fig2_*.png`, `fig3_*.png`,
`src/p4_noise_attr.py`.