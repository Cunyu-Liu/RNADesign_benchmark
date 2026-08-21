# ToeholdDesignBench Task Contract v0.2.1

Status: controlling statistical addendum from 2026-08-21. This document inherits
all datasets, splits, endpoints, thresholds, evidence tracks, method identities,
and claim prohibitions from `task_contract_v0.2.md`. It changes only the four
items declared below. Result filenames retain `_v02` because their schema is
unchanged.

## Why this addendum exists

The first real v0.2 run exposed two analysis-boundary problems that synthetic
tests could not settle. A single seeded random ranking changed canonical
success@1 materially, and the BEACON authoritative mapping already contained a
published row-level `split` column that collided with the new target-level
split. The addendum records the corrections before the paper-facing rerun and
preserves the superseded outputs under the server iteration archive.

## A1 — Exact random-ranking expectation

- Paper-facing random-baseline metrics are the exact per-target expectation under
  a uniformly random permutation of all candidates for that target.
- Success@K uses the exact probability of drawing at least one qualified
  candidate without replacement.
- Expected NDCG uses rank exchangeability; expected regret uses the finite-sample
  maximum order statistic; expected Pareto-front coverage uses each front item's
  K/N inclusion probability.
- The row-level score file may retain a seed-0 random draw for audit, but that
  column is not used for paper-facing random metrics or paired comparisons.
- The expected pooled Spearman correlation of the random ranking is reported as
  zero. No random seed is treated as an experimental replicate.

## A2 — Finite-bootstrap reporting

- Target remains the independent unit for canonical and BEACON intervals and
  paired comparisons; VISTA remains a within-target site bootstrap.
- A finite bootstrap must never report `P = 0`. Tail probabilities use an
  add-one Monte Carlo correction and therefore expose their finite resolution.
- Effect differences and 95% confidence intervals carry the interpretation.
  Bootstrap P values are secondary and exploratory; the manuscript must not
  imply multiplicity-controlled confirmatory inference unless a correction is
  explicitly added and reported.

## A3 — BEACON split audit

- BEACON's published row/QC split is preserved as `published_row_split`.
- The source-disjoint benchmark split is the sole column named `split`.
- The result package must report train/test target counts, overlap counts, and
  test-target overlap fractions for the published row split, separately for TF
  and virus sources.
- Published row-split performance may be described as a sequence-level result,
  but not as evidence of unseen-target generalization when target overlap is
  nonzero.

## A4 — Outcome-neutral interpretation

- The paper must report whether pooled prediction and target-ranking utility
  align or diverge; their distinction is a task definition, not a guaranteed
  empirical disagreement.
- VISTA is a paired assessment of context agreement and scorer sensitivity for
  one mCherry target. A context effect may be claimed only when the reported
  estimate and uncertainty support it.
- Failure to beat the random expectation on primary success@1 is a reportable
  result and must not be hidden by leading with a secondary endpoint.

## Updated paper gate

Submission readiness requires all v0.2 conditions plus the following:

1. The exact random expectation is used consistently in the main table,
   pairwise comparisons, group summaries, text, and figures.
2. The BEACON published-split leakage audit is present in machine-readable
   results and the manuscript.
3. No reported bootstrap probability equals zero.
4. The manuscript states the observed direction of objective alignment and the
   primary success@1 result without preserving a superseded hypothesis.
5. A final three-reviewer audit has no blocking technical or claim-scope finding.

