# Pollution statement (benchmark governance, §13)

Date: 2026-08-21 · Version 0.2

## Model / data exposure
- All v0.2 baselines are trained from scratch in this repository on the benchmark's canonical
  data (split into train/val/test; test never used for fitting). No baseline was pre-trained on the
  benchmark's test sequences, and none was tuned on test labels.
- `B1_thermo` uses thermodynamic proxy features (RBS-calculator `SalisLab*`, ViennaRNA `mfe_seq_*`) that ship
  inside the source data file itself. These are properties of the switch sequences (computed from sequence,
  not from labels); they are used as features, not labels. Their presence is disclosed here and in the datasheet.
- External submissions (via `runner.py --scores`) MUST disclose: any pretraining data, whether the method was
  exposed to the benchmark paper/sequences, and tuning details. "unknown" does not count as "no".

## Test-set integrity
- Test labels (ON/OFF) are not used for any threshold choice: success is the pre-registered **absolute**
  threshold `ON>=0.5 AND OFF<=0.5`, fixed before evaluation.
- The source-disjoint split guarantees no target (and hence no adjacent sliding-window) crosses train/test
  (verified overlap = 0; row-random split leaks 99.9% and is explicitly non-standard).
- The VISTA mCherry external set (E3) was downloaded but its labels were never used to select models.
- The BEACON source-disjoint manifest is rebuilt from source identity; its official
  row split is retained only as a diagnostic and is not the unseen-target test.

## Known caveats / contamination risks
- The 91,534 official QC2 labels (npz) overlap the CSV labels (42,189 exact triple matches); they are the
  same experimental source, not independent contamination.
- The primary CSV has been public since 2020; methods trained on the Angenent-Mari data before this
  benchmark's release may have seen these sequences. This is disclosed; it is why the benchmark adds a
  source-disjoint split and, for future work, a hidden/external target set.

## Versioning & submission limits
- Benchmark version 0.2; static sealed test (no live leaderboard yet; no submission-count limit enforced).
  A public leaderboard, if added, must enforce submission limits and version pinning.
