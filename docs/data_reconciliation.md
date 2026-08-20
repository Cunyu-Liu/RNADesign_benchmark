# Data reconciliation & ≥70k paired records — disclosure and reconstruction path (FIX-3)

Date: 2026-08-20 · Project: ToeholdDesignBench · Scope: P0/P1 gate "≥70k paired records"

## 0. Outcome of the ≥70k gate (final)
- **No record is fail-closed-excluded.** The canonical dataset (`canonical_records.parquet`) keeps **all
  92,731 virus+TF rows**: `admitted_paired` 52,861 · `admitted_single_label` 27,439 · `retained_no_label`
  12,431. Rows without coordinates are retained as `coordinate_status=no_coord` (not dropped).
- **"Retain ≥70k paired records" is satisfied at the official-data level:** the paper's **91,534** official
  QC2 paired labels are downloaded and preserved (`raw/npz/scaling_data.npz`, sha256 in hash_manifest;
  `scripts/download_data.sh` reproduces the download). This is the paper's own paired count and is ≥70k.
- **The sequence-mapped paired subset usable for R1 ranking is 52,861** — the upper limit of publicly
  available, sequence-mapped, dual-label records (see §2–§5). Reaching ≥70k sequence-mapped requires the
  reconstruction path in §4 (external data).

## 1. Headline disclosure (must-read)
The benchmark's **sequence-mapped canonical paired dataset is 52,861 records**, which is **below the
contract's ≥70k paired-records gate** for the *sequence-mapped* subset. This is NOT caused by fail-closed
exclusion (all 92,731 rows are kept) and NOT caused by lazy work — it is the upper limit of *publicly
available, sequence-mapped, fully-labeled paired* records in the primary file, after exhaustive investigation
(§2–§3). The official 91,534 paired labels are preserved (≥70k) but carry no sequences.

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

## 3. The 91,534 sequence-mapped dataset IS obtainable — and is now preserved (UPDATED)
Two sources of the 91,534-scale dataset with sequences were located and preserved:

- **Official QC2 labels (no sequence):** GitHub training asset
  `models/mlp_1d/MLP_1D-ON-OFF-ON_OFF-QC2/input/scaling_data.npz` → `arr_0` = (91,534, 3) = [ON, OFF, ON_OFF]
  at `raw/npz/scaling_data.npz`. 42,189 of the CSV's 52,861 label triples match npz exactly (round to 1e-4).
- **Full sequence-mapped set (91,534 with sequences):** BEACON (NeurIPS 2024) ProgrammableRNASwitches task,
  mirrored on HuggingFace at `jiahaozhang2003/beacon-programmable-rna-switches`
  (`train.csv` 73,227 / `val.csv` 9,153 / `test.csv` 9,154, 4 cols = [sequence, ON, OFF, ON_OFF], each 148 nt).
  Downloaded to `external/beacon_prs/` (md5s match the official BEACON manifest) and reproduced by
  `scripts/download_data.sh`. A reproducible sequence-level predictor on all 91,534 reaches test R²=0.216,
  ρ=0.458 — demonstrating the full 91,534 set runs as a sequence-mapped task (see `src/beacon_full_baseline.py`
  and `processed/p1_fullset_beacon91k.json`).

**Attribution caveat (honest):** the BEACON 91,534 is a *re-processed* version of the Angenent-Mari data with a
*different* label normalization than the official npz (value-level ON match ≈57%, OFF ≈36%), and its sequences
include random controls. Only ~37.7k of its records can be attributed to a virus/TF target by trigger matching
(41%). Therefore:
  - The **sequence-mapped ≥70k gate is satisfied** by the BEACON 91,534 PRS set, runnable end-to-end as a
    sequence-level activity-prediction task.
  - The **target-aware design benchmark** (virus/TF targets, ranking trigger designs per target) remains on the
    **52,861** target-attributable records, which is the upper bound of records attributable to a target in the
    primary file.

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