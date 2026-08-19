# Data reconciliation & ≥70k paired records — disclosure and reconstruction path (FIX-3)

Date: 2026-08-20 · Project: ToeholdDesignBench · Scope: P0/P1 gate "≥70k paired records"

## 1. Headline disclosure (must-read)
The benchmark's **sequence-mapped canonical paired dataset is 52,861 records**, which is **below the
contract's ≥70k paired-records gate**. This is NOT caused by fail-closed exclusion — it is the upper limit
of *publicly available, sequence-mapped, fully-labeled paired* records in the primary file. All records that
carry a complete dual-state label are retained (no record with labels was excluded). This document discloses
the exact situation and the reconstruction path to reach 70k+.

## 2. What the data actually contains (primary file: Toehold_Dataset_Final_2019-10-23.csv, 97,436 rows)
Classification of the 92,731 virus+TF rows:

| state | count | meaning |
|---|---|---|
| both_counts_lab | **52,861** | has final ON & OFF (normalized) labels AND complete dual-state flow-seq counts |
| on_only_nolab | 5,314 | only ON-side counts > 0; no final OFF label |
| off_only_nolab | 22,125 | only OFF-side counts > 0; no final ON label |
| no_counts_nolab | 12,431 | no usable gate counts; no label |

Key facts (verified):
- **Every row with complete dual-state counts (both > 0) has a final label** (both_counts_nolab = 0).
- Rows without labels lack a complete dual-state measurement; their ON/OFF cannot be reconstructed from counts
  (there are no counts to reconstruct from), and Cbn (the intermediate the paper uses: ON = Σ Cbn_i·[0,⅓,⅔,1])
  is absent for them.
- Random-sequences (4,705) are excluded from the primary ranking per contract §7.3.

## 3. The official 91,534 QC2 labels exist — and are preserved
The paper's 91,534 paired ON/OFF (QC2) labels ARE publicly available as a GitHub training asset
`models/mlp_1d/MLP_1D-ON-OFF-ON_OFF-QC2/input/scaling_data.npz` → `arr_0` = (91,534, 3) = [ON, OFF, ON_OFF].
- Downloaded and preserved at `raw/npz/scaling_data.npz` (sha256 recorded in hash_manifest).
- 42,189 of the CSV's 52,861 label triples match npz exactly (round to 1e-4) — confirming the CSV labels are
  a subset of the official QC2 labels with identical values.
- Figure S9 of the paper's Source Data (91,534 experimental values) also matches.
- **But the npz has no sequences/IDs**, so the 91,534 official labels cannot be mapped onto the CSV's rows
  (row-order alignment fails at row 3; only triple-value matching is possible). Hence the 91,534 cannot be
  directly turned into a sequence-mapped ranking set.

## 4. Reconstruction path to ≥70k sequence-mapped paired records (required external action)
To reach ≥70k with sequence mapping, one of the following is required:
1. **Obtain the sequence-mapped complete QC2 dataset from the authors** (91,534 rows with trigger/target/
   source). This is the definitive fix; the authors' GitHub only ships labels (npz) without sequences.
2. **Recover the full counts→Cbn→ON pipeline** from the paper's unpublished methods. Verified: ON = Σ Cbn_i·f_i
   (f=[0,⅓,⅔,1]); a GBDT trained on counts reconstructs ON/OFF with CV R²=0.9998 on labeled rows — BUT the
   unlabeled rows have no dual-state counts to feed it, so reconstruction is only possible for rows that
   already carry labels. Applying the GBDT to rows without dual-state counts is not valid.
3. **Re-request the 2019-03-30 database** referenced in the repo README (`..._toehold_dataset_proc_with_params.csv`),
   which is not in the public repo; it may contain the full 91,534 with sequences.

## 5. What we did NOT do (data-integrity safeguards)
- Did not fabricate labels for the 39,870 unlabeled rows.
- Did not claim 92,730 (= "dual-state gate strings present") as labeled paired — the 92,730 includes rows with
  empty/zero single-state counts that carry no final label.
- Did not claim npz's 91,534 as the benchmark's sequence-mapped set (no sequence mapping possible).
- Did not fail-closed-drop any labeled record: the benchmark's canonical set retains all 52,861 labeled pairs;
  coordinate-unresolved labeled rows are retained with `coordinate_status=no_coord` (NOT excluded).

## 6. Impact on acceptance & claims
- P0/P1 "≥70k paired records": **HOLD** — publicly available sequence-mapped paired labels = 52,861; official
  91,534 preserved but not sequence-mappable. Full closure requires the reconstruction-path action above.
- This does NOT change the benchmark's validity for what it measures (source-isolated fused-context candidate
  ranking on all retained labeled pairs, 931 targets ≥ 500), but it caps the scale claim: we report
  "52,861 sequence-mapped paired records (of the paper's 91,534 official paired labels)".
- Re-verification checklist: once a sequence-mapped 91,534 set is obtained, rebuild canonical_records →
  re-run split/baselines/experiments → update hash_manifest → re-open the ≥70k gate as PASS.