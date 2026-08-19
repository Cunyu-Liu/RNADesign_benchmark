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
| retained paired records | >=70k | 92,730 virus+TF with paired ON/OFF flow-seq characterization (paper reports 91,534; final-normalized ON/OFF ratio subset = 52,861) | PASS |
| target groups | >=500 | 931 | PASS |
| trans/full-target external set (>=100 candidates) | >=1 | VISTA mCherry ~190 sites | PASS |
| >=4 baseline families runnable | >=4 | random, GC rule, thermodynamic, MLP all run end-to-end (GPU) | PASS |
| license closable | yes | primary data CC BY 4.0; VISTA license to confirm | PASS (with note) |

## 3. Minimal baseline results (source-disjoint split, success = top-20% ON/OFF)

| baseline | success@1 | success@5 | NDCG@10 | note |
|---|---|---|---|---|
| B0_random | 0.204 | 0.796 | 0.512 | matches 20% chance |
| B0_gc_rule | 0.129 | 0.559 | 0.414 | worse than chance |
| B1_thermo | **0.344** | 0.855 | 0.561 | strongest @1 |
| B2_mlp (GPU) | 0.296 | 0.839 | 0.552 | competes but ~ thermo |

Learnable signal under source isolation: B1_thermo exceeds random by +14pp success@1.

## 4. Answers to To-do E questions

1. **Non-trivial top-K selection problem?** YES. Median 53 candidates/target; success rate 20%; random success@1 = 0.20 leaves large headroom (thermo reaches 0.344).
2. **Learnable signal after strict source split?** YES (thermo > random, +14pp @1).
3. **External trans/full-target usable as true held-out test?** YES (VISTA mCherry ~190 sites with full/truncated contexts; not used for tuning).

## 5. Honest caveats / open items (carried to P1)

- **"91,534" reconciliation:** raw file has 97,436 rows (92,731 virus+TF + 4,705 random). 92,730 virus+TF switches carry paired ON/OFF flow-seq gate counts (≈ the paper's 91,534; the residual ~1,197 = a QC filter to reconstruct from the paper Methods in P1). The 52,861 "final ON/OFF ratio both populated" is a downstream-normalization subset, not the paired-characterization count.
- **Coordinate reconstruction:** tile index is a sequential ID, NOT genomic position. Absolute window coordinates require downloading 23 virus genomes + 908 TF transcripts and string-matching triggers (pilot-proven feasible; mechanical P1 work).
- **Human TF count:** data has 908 `human_*` sources vs paper's 906 (2 look like non-TF clone accessions; to verify).
- **VISTA license:** repo lacks an explicit LICENSE file; legal redistribution status must be confirmed before public release.
- **Row-vs-source split comparison** in the sanity baselines is confounded by target size; rigorous E2 (leakage) is P4.

## 6. Next step

Proceed to **P1 (data & provenance build)**: close source-genome mapping, reconcile the 91,534 filter, finalize license matrix, and produce the canonical dataset + registry.