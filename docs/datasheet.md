# ToeholdDesignBench — Datasheet

## Motivation
Benchmark per-target top-K candidate-ranking utility of toehold RNA sensors while
keeping assay and normalization contexts separate.

## Composition
- Canonical records: 97,436 raw → 92,731 virus+TF retained records (23 viral
  genomes + 908 human-TF-derived sources; 4,705 random excluded from R1).
- Canonical main ranking labels: 52,861 `admitted_paired` records. The remaining
  39,870 virus+TF records are retained for accounting but are not given inferred labels.
- Targets: 931 (23 virus + 908 human); median 53 candidates/target.
- Label-bearing R1 targets: 926 (fixed split: 648 train, 138 validation, 140 test).
- Canonical labels: `ON`, `OFF`, and signed `ON_OFF = ON - OFF`; flow-seq
  quality/count fields; local computational proxies `SalisLab*` and `mfe_seq_*`.
- Split: source-disjoint 70/15/15 (target never crosses train/test).
- Separate BEACON track: 91,534 sequence-mapped rows, 23 virus + 905 TF
  sources plus one random pooled group; its normalized `ON_OFF` is not merged
  with canonical labels.
- Separate VISTA track: 189 sites from one mCherry target with paired truncated
  and full-context values.

## Collection
- Source study: Angenent-Mari NM et al., Nat Commun 11:5057 (2020). DOI 10.1038/s41467-020-18677-1.
- Assay: flow-seq on BL21 E. coli; ON = fused trigger, OFF = no-cognate-trigger leak (NOT specificity).
- Architecture: first-gen 30-nt toehold switch (Green et al. 2014).

## Schema (canonical_records.parquet, key fields)
record_id, study_id, target_id, source_category (virus|human_TF), tile_index, architecture_id,
reporter_id (GFP), host_id (ecoli_BL21), assay_id (flow-seq), trigger_context (fused), trigger,
switch, ON, OFF, ON_OFF, QC_ON, QC_OFF, QC_ON_OFF, salis_onoff, mfe_switch_off/on, mfe_trigger,
gc_trigger, paired_characterized, admission_status, source_accession, window_start, window_end,
strand (forward|revcomp), coordinate_status.

## Data processing
- QC filter: paper's Supplementary Table S1 states "QC2 was ultimately chosen as the final condition";
  exact thresholds recovered via table-image (residual item). paired_characterized (flow-seq both states) = 92,730.
- Coordinates: triggers mapped to NCBI RefSeq genomes/transcripts via exact match; fail-closed exclusion ledger.

## Uses / limitations
- R1 = intrinsic fused-context ranking; does NOT measure real trans/full-target sensing or specificity.
- Random 30-nt triggers excluded from primary ranking (auxiliary/negative control).
- BEACON, canonical, and VISTA raw labels must not be merged across scales.
- VISTA uncertainty is within one target and cannot support cross-target generalization.
- B3/B4/B5 are representative repository proxies, not complete reproductions of
  named published systems.

## Distribution
- Angenent-Mari dataset: CC BY 4.0. RefSeq sequences: public domain (NCBI). VISTA: verify before redistribution.

## Maintenance
Static versioned release with runner, frozen manifests, result schema, license
matrix, exclusion ledger, and run log. No live leaderboard is promised.
