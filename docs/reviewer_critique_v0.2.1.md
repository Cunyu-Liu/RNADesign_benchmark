# Reviewer Critique of ToeholdDesignBench v0.2.1 — Formal Reports and Editor Synthesis

Date: 2026-08-21
Scope: full audit of the v0.2.1 delivery state (commit chain up to `69a17f3`, tag `reviewer-baseline-v0.2.1-20260821`) against the v0.1 hard gates, the v0.2.1 consolidated contract, and the manuscript claims.

Three independent reviewer roles (technical validity; novelty and literature; significance and narrative) plus an editor synthesis. Each reviewer had access to: the v0.1/v0.2/v0.2.1 contracts, the workspace Git state, the raw and processed data, the analysis scripts, the manuscript draft, and the internal prior review record.

Recorded prior-state facts that all reviewers were shown before writing reports:

1. The prior internal "three-reviewer no-blocker" verdict only assessed fit for a specialized journal and explicitly did not constitute a Nature-level evaluation.
2. v0.1 required exact dedup, overlap-component, sequence-cluster OOD, study/context OOD, and hidden external gates; v0.2.1 deleted or weakened these hard gates.
3. canonical train/test contain 46 identical 30-nt triggers involving 4/140 test targets. This does not demonstrably explain the MLP gain, but it invalidates any "strictly sequence-disjoint" statement.
4. The 0.5/0.5 success threshold was written into the v0.2 contract after results had been viewed; the old 140-target test must be demoted to development/exploratory and must not be called a pre-registered confirmation set.
5. Method ordering depends on the threshold: at 0.3/0.3 the thermodynamic proxy's relative gain exceeds the MLP's; at 0.5/0.5 the ordering reverses.
6. The BEACON "30-nt input" erroneously used `[0:30]`; the true trigger is 0-based `[3:33]`.
7. The 148-nt construct additionally contains a reverse-complement copy of the trigger around `[53:83]`; the current 148-model has ~3.54× the parameters of the 30-model, so current results cannot be attributed to "extra target context".
8. Of 91,534 BEACON rows, the audit found 396 rows with multiple possible sources and 568 rows with multiple possible sequence IDs; the main analysis must not silently resolve these via `setdefault` or input order.
9. canonical and BEACON share 928/928 non-random target names; they must both be labeled `Angenent–Mari 2020`, one `study_id`, two `label_view`s.
10. All current learned models are row-weighted, full-batch, fixed 15/20-step MSE regressions; the 138 validation targets were never used for model selection or early stopping.
11. One smallpox target contributes 33.15% of canonical training rows but every target is weighted equally at evaluation: the training objective is badly mismatched to the evaluation estimand.
12. `B5_structrank` is still an MSE MLP trained 5 steps longer than B4; it is not a ranker.
13. `salis_onoff` is missing in ~54.42% of rows; non-missing values span ~0.017–157,169; it is currently zero-filled, unstandardized, and mixed with negative-scale MFE in the thermodynamic proxy. Current results show "naive feature concat fails", not "biophysical information is useless".
14. The current leakage-effect comparison used different test candidate sets; it is not a controlled causal comparison.
15. The core execution script runs 18 tests while the manuscript claims 20.
16. The remote workspace at audit time had 28 modified and 22 untracked paths; the core v0.2.1 contract, manuscript, scripts, and tests were uncommitted; all three PID files were stale pointers.
17. Retained correct foundations: signed ON−OFF; target as independent decision unit; no-feasible-candidate targets kept in denominators; per-target analytic random expectation; label-view separation; target-level bootstrap.

---

## Reviewer Report 1 — Technical Validity

**Recommendation: Reject and Resubmit.**

### Major concerns

**T1. Evaluation set contamination.** 46 exactly identical 30-nt triggers cross the canonical train/test boundary, involving 4/140 test targets (fact 3). Whatever the causal contribution, the split cannot be described as sequence-disjoint, and per-target random baselines do not repair a broken split. A benchmark paper whose central claim is evaluation hygiene cannot ship with a contaminated confirmation split.

**T2. Threshold-dependent conclusions with post-hoc threshold selection.** The headline success metric depends materially on the (ON, OFF) threshold pair (fact 5), and the 0.5/0.5 cell was fixed only after results were seen (fact 4). Without a pre-declared full threshold surface and a legacy-only status for 0.5/0.5, the reported comparisons are selection-biased by construction.

**T3. BEACON input slicing is wrong.** The "30-nt trigger" input is `[0:30]` of the 148-nt construct rather than the true trigger `[3:33]` (fact 6). Every downstream BEACON number in the current manuscript inherits this error. Additionally, the construct contains a reverse-complement trigger copy at `[53:83]` (fact 7), so any "context benefit" claim made with a 3.54×-parameter model is confounded three ways: wrong slice, unmodeled RC copy, unequal capacity.

**T4. Mapping ambiguity silently resolved.** 396 rows with multiple possible sources and 568 rows with multiple possible sequence IDs (fact 8) were resolved implicitly by insertion order. A benchmark that claims rigorous data identity must make every mapping status explicit (`unique`/`ambiguous`/`unresolved`) and exclude ambiguous rows from the main analysis.

**T5. Dataset identity.** canonical and BEACON are two label views of the same 2020 experiment (fact 9). Presenting them as independent datasets inflates the external evidence base.

**T6. Training objective vs. evaluation estimand mismatch.** All learned models are row-weighted full-batch MSE regressions with fixed 15/20 optimization steps; one target supplies 33.15% of training rows while evaluation is target-equal-weighted (facts 10, 11). The validation targets are never used (fact 10). The "model comparison" is therefore a comparison of underfit, objective-mismatched estimators, and no conclusion about modern architectures can be drawn from it.

**T7. Statistical protocol.** P values are derived from bootstrap zero-crossing proportions; ties are not handled analytically; random baselines are single seed-0 draws rather than per-target analytic expectations. `B5_structrank` is described as a ranker but is an MSE MLP (fact 12).

**T8. Biophysical feature preprocessing.** `salis_onoff`: 54.42% missing, ~7 orders of magnitude dynamic range, zero-filled, unstandardized, mixed with negative-scale MFE (fact 13). The "biophysics hurts" claim is unsupported by the current pipeline.

**T9. Leakage comparison is not controlled.** Different test candidate sets on the two arms (fact 14). No causal statement is possible.

**T10. Reproducibility gaps.** 18 executed tests vs. 20 claimed (fact 15); at audit time the core contract, manuscript, scripts, and tests were uncommitted and PID files were stale (fact 16).

### What survives

The signed ON−OFF label, target-as-unit evaluation, no-feasible-candidate denominators, analytic per-target random expectation, label-view separation, and target-level bootstrap (fact 17) are sound and should be preserved in the next version.

### Required for resubmission

Exact-dedup and homology-aware clustering with cross-fold closure verification; [3:33] trigger slicing with tests; explicit mapping-status ledger; a single evaluator with analytic tie handling; target-balanced training; pre-declared threshold surface; train-only preprocessing; controlled leakage design with identical test candidates; committed, single-entry reproduction.

---

## Reviewer Report 2 — Novelty and Literature

**Recommendation: Reject.**

### Major concerns

**N1. No modern official-model reproduction.** The benchmark's model panel is dated: it does not reproduce, under official implementations, any of the 2024–2026 models that define the current frontier (BEACON ResNet/LSTM/BEACON-B512/SpliceBERT-MS1024/RNA-FM/UTR-LM-MRL; SANDSTORM/GARDN 2025; RNAElectra 2026 preprint; Valeri STORM/NuSpeak CNN cores; Angenent–Mari MLP-O and CNN/VIS4Map). Without official reproduction under identity tolerance, the leaderboard cannot support claims about modern RNA models.

**N2. No original method aligned with the evaluation.** The benchmark's own conclusion is that training objectives mismatch target-equal-weight ranking, yet no target-grouped ranking objective is proposed and ablated. This is the obvious scientific opportunity and it is absent.

**N3. Two label views presented as two datasets.** canonical and BEACON are the same 2020 experiment (facts 8, 9). The paper's external-evidence framing depends on this conflation.

**N4. Holdout presented as new.** The Angenent–Mari paper already performed per-virus-genome holdout. Source/virus holdout cannot be claimed as a methodological contribution; only genuinely new split machinery (exact/RC trigger closure, overlap components, context homology closure) can.

**N5. Literature coverage.** The manuscript does not engage the 2024–2026 design-predictor and pretrained-RNA-model literature in either related work or experiments.

### Required for resubmission

Official-commit adapters with identity reproduction on original splits before any new evaluation; a proposed target-grouped ranking method with matched-capacity ablations across ≥2 backbones; correct data identity; literature cutoff declared and covered.

---

## Reviewer Report 3 — Significance and Narrative

**Recommendation: Reject and Resubmit.**

### Major concerns

**S1. The paper is still an audit.** The main result remains "the prior benchmark's protocol was flawed". Protocol audits are serviceable as blog posts or supplementary analyses, not as the central contribution of a computational-biology article at a selective venue.

**S2. No demonstrated consequence.** The manuscript does not show that the corrected protocol changes any model-selection or external-experiment conclusion. If nothing changes under the corrected protocol, the audit is bookkeeping; if something changes, that change is the result — and it is missing.

**S3. Thin independent external evidence.** The only independent full-target track is a single mCherry target (VISTA). One target cannot carry an external-validity claim regardless of its internal site count.

**S4. Overclaiming risk.** Phrases like "state of the art" and "generalizable" appear without simultaneous-comparison support; prospective or generation-capability implications are implied but not tested.

### Required for resubmission

A frozen central question with pre-declared endpoints; at least two independent external studies evaluated on their native tasks; explicit two-tier outlet criteria with honest negative-result paths; claims bounded to the evidence.

---

## Editor Synthesis

**Decision: not suitable for a high-impact venue in its current form; viable as a professional benchmark prototype under major revision.**

The three reviews converge: the technical foundation contains correct elements (Reviewer 1's "what survives"), but the confirmation split is contaminated, the model panel is stale, the training protocol cannot support architecture-level conclusions, the data identity is misrepresented, and the paper's contribution is an audit rather than a result. The path forward is not more experiments of the same kind but a version-controlled closure: freeze a corrected protocol, reproduce official modern baselines under identity tolerance, propose and strictly ablate a task-aligned ranking objective, evaluate on ≥2 independent external studies natively, and pre-declare two-tier outlet criteria. If the methodological gains or external replications fail, the honest outcome is a benchmark/resource paper at a specialized venue — which is a publishable and useful result, not a failure to hide.
