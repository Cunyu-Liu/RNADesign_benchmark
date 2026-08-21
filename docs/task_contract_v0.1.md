# ToeholdDesignBench Task Contract v0.1 (archived)

> Historical document only. The controlling contract is
> [`task_contract_v0.2.md`](task_contract_v0.2.md). Results and claims below have
> not been updated to the corrected v0.2 protocol.

Gate 0 deliverable. Freezes the R1/R2/P1 task definitions, inputs, outputs, boundaries and metrics
derived from the project execution contract (Target-aware Toehold Sensor Design Benchmark, v0.1, 2026-08-19).

## 1. Central scientific question

Given an unseen full target RNA, a fixed toehold device architecture, and a candidate/submission budget K,
can different design systems prioritize or design candidates with high ON, low OFF, valid device grammar,
that generalise to real trans/full-length-target conditions — without accessing test labels?

## 2. Task protocol

### R1 — Fused-context intrinsic site ranking (v1 primary)
- **Input:** full source RNA name + measured 30-nt tiles + first-gen device metadata (fused context).
- **Output:** full candidate ranking / top-K candidate IDs per source.
- **Label source:** Angenent-Mari 2020 (97,436 rows; 931 target groups; 23 virus + 908 human TF).
- **Interpretation:** intrinsic switch/window suitability. NOT real full-target sensing.

### R2 — Trans/full-target external ranking (v1 external)
- **Input:** full target RNA + candidate sites + architecture/reporter/context.
- **Output:** per-target candidate ranking.
- **Label source:** Green/Valeri (free-trigger), Toehold-VISTA (truncated/full-length mCherry, ~190 sites).
- **Interpretation:** target accessibility + context transfer. Per-study evaluation; no raw-scale merging.

### P1 — Prospective constrained redesign (optional upgrade)
- **Input:** new target + fixed architecture + mutable-site/hard-constraint spec + budget K.
- **Output:** K never-measured switch sequences.
- **Label source:** new wet-lab experiment.
- **Interpretation:** the only task supporting true de-novo design claims.

## 3. Unified TaskSpec (field schema)

```
target_id            unique full-target ID
target_sequence      full target RNA (required for R2/P1)
candidate_site       start/end coords + trigger sequence
architecture_id      first-gen-30nt | series-A-36nt | frozen
reporter_id, host_id, assay_id
trigger_context      fused | free-truncated | full-length
hard_constraints     RBS, AUG, scaffold, complementarity, length, stop codons
submission_budget_K  1 / 3 / 5 / 10 (pre-registered per task)
output               candidate_id or new sequence, ranking score, confidence, run log
```

## 4. Splits (hard gates)
- S0 exact dedup: split-pair exact overlap = 0.
- S1 target-source disjoint: source_id never crosses train/val/test.
- S2 overlap-component closure (QC).
- S3 target-sequence cluster OOD.
- S4 domain OOD (human TF vs virus).
- S5 context/study OOD (fused -> free/truncated/full).
- S6 hidden external.

## 5. Primary & secondary metrics
- Primary: success@K (per-target top-K contains a pre-registered high-ON/low-OFF hit).
- Secondary: NDCG@K, normalized regret, ON/OFF Pareto front size, hard-valid rate, context transfer gap, cost-per-hit.
- Auxiliary only (never primary): R^2 / Spearman / MAE (prediction metrics).
- Statistics: target/source is the bootstrap unit; report 95% CI + paired bootstrap deltas; correct for multiple testing.

## 6. Information-regime fairness
Same leaderboard => same TaskSpec fields. Regimes: sequence-only | trigger-aware | full-target-aware.
Generators must use a public fixed sample-and-rank adapter; all samples count toward budget.

## 7. Allowed claims (by evidence)
- R1 only: "source-isolated fused-context candidate-site ranking benchmark".
- R1+R2: "cross fused/trans/full-target target-aware candidate prioritization benchmark".
- R1+R2+P1: "prospective hit-rate comparison of design systems under frozen architecture & conditions".
- Forbidden: "first AI toehold design", "first target-aware method", "OFF low => specific", circular validation, single aggregate winner.

## 8. Exclusions (v1)
aptamers, ribozymes, RBS, 5'UTR, Cas13 guides, eukaryotic toeholds, multi-input logic; cross-RNA-func leaderboard;
merging raw ON/OFF across assays; training new RNA foundation models; claiming de-novo validity without P1.
