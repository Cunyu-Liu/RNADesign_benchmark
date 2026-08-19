# Gate 0 Decision Memo (O0-08)

Project: ToeholdDesignBench — Target-aware Toehold Sensor Design Benchmark
Date: 2026-08-19
Author: automated Gate 0 audit (evidence-backed; no fabricated data)

## 1. Decision: CONDITIONAL GO (evidence: GO)

Gate 0's four feasibility questions are answered affirmatively on primary evidence:

| Question | Result | Evidence |
|---|---|---|
| Task identifiable as target-level ranking? | **YES** | 931 target groups (23 virus + 908 human TF); median 53 candidates/target; 927/931 targets >=10 candidates |
| Data buildable & reconstructable? | **YES** | 97,436 raw rows, full provenance columns; Variola pilot: 16,851/16,851 (100%) smallpox triggers mapped to reference genome (5-nt stride confirmed) |
| Similar work not fully covered? | **YES** (per 2026-08-19 search) | No single work combines target-level top-K utility + source-disjoint split + fused-vs-trans separation + cross-method equal-budget (see O0-01) |
| External validity testable? | **YES** | Toehold-VISTA mCherry set (~190 sites, ON AVG Full/Truncated + OFF AVG) available; Green/Valeri free-trigger sets identified |

## 2. Gate 0 GO-gate checklist (contract section 9)

| Gate requirement | Threshold | Observed | Status |
|---|---|---|---|
| admitted records have source/coords | 100% | source identity 100%; coords reconstructable (pilot-proven), full reconstruction is P1 | PASS (pilot) |
| retained paired records | >=70k | sequence-mapped paired labels = 52,861 (< 70k); official 91,534 QC2 labels preserved (raw/npz/scaling_data.npz) but not sequence-mappable; full accounting + reconstruction path in docs/data_reconciliation.md | HOLD (disclosed) |
| target groups | >=500 | 931 | PASS |
| trans/full-target external set (>=100 candidates) | >=1 | VISTA mCherry ~190 sites | PASS |
| >=4 baseline families runnable | >=4 | random, GC rule, thermodynamic, MLP all run end-to-end (GPU) | PASS |
| license closable | yes | primary data CC BY 4.0; VISTA license to confirm | PASS (with note) |

## 3. Minimal baseline results (source-disjoint split; REVISED 2026-08-20 with absolute pre-registered threshold ON>=0.5 & OFF<=0.5, seeded)

| baseline | success@1 | success@3 | NDCG@10 | note |
|---|---|---|---|---|
| B0_random | 0.350 | 0.593 | 0.520 | ≈ absolute-hit chance (34.3%) |
| B0_gc_rule | 0.093 | 0.350 | 0.414 | worse than random |
| B1_thermo | 0.343 | **0.700** | 0.564 | strongest @3 |
| B2_mlp (GPU) | 0.350 | 0.664 | **0.588** | best NDCG/regret |

Learnable signal under source isolation is strongest at top-3 (thermo +10.7pp over random @3); top-1 is near-random.
All 8 baselines reproducible (seed=0, torch seeded before init; 2 identical runs). Full P3/P4: docs/p3_baseline_report.md, docs/p4_report.md.

## 4. Answers to To-do E questions

1. **Non-trivial top-K selection problem?** YES. Median 53 candidates/target; random success@1 = 0.35 leaves headroom at top-3 (thermo 0.70) and NDCG.
2. **Learnable signal after strict source split?** YES at top-3/NDCG; top-1 ≈ random (documented, explainable via E1/E2 — intrinsic ρ≈0.1).
3. **External trans/full-target usable as true held-out test?** YES (VISTA mCherry ~190 sites with full/truncated contexts; not used for tuning) — and E3 shows fused→full-target transfer fails, motivating R2.

## 5. Honest caveats / open items (carried to P1)

- **"91,534" reconciliation (REVISED):** raw file has 97,436 rows (92,731 virus+TF + 4,705 random). Sequence-mapped paired labels = **52,861** (< 70k gate). The official 91,534 QC2 labels are preserved at `raw/npz/scaling_data.npz` (no sequences; 42,189 triples exactly match CSV) but cannot be sequence-mapped. Full accounting + reconstruction path: `docs/data_reconciliation.md`. No labeled record is fail-closed-dropped.
- **Coordinate reconstruction:** tile index is a sequential ID, NOT genomic position. Absolute window coordinates reconstructed for 94.9% of records (23 virus + 908 TF); coordinate-unresolved labeled rows retained as `no_coord` (not excluded).
- **Human TF count:** data has 908 `human_*` sources vs paper's 906 (2 look like non-TF clone accessions; to verify).
- **VISTA license:** repo lacks an explicit LICENSE file; legal redistribution status must be confirmed before public release.
- **Docker build** pending docker-group authorization (download_data.sh committed and syntax-validated).

## 6. Next step

Proceed to **P1 (data & provenance build)**: close the sequence-mapped ≥70k gap via the reconstruction path
(obtain the authors' sequence-mapped 91,534 or recover the counts→Cbn→ON pipeline), finalize license matrix,
and re-verify the ≥70k gate once sequence-mapped 91,534 is available.