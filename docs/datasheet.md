# ToeholdDesignBench — Datasheet

## Motivation
Benchmark per-target top-K design utility of toehold RNA sensors. Reframes Angenent-Mari 2020
91,534 paired ON/OFF switches from single-sequence regression to target-level candidate selection.

## Composition
- Records: 97,436 raw → 92,731 virus+TF canonical (23 viral genomes + 908 human-TF-derived sources; 4,705 random excluded).
- Targets: 931 (23 virus + 908 human); median 53 candidates/target.
- Labels: `ON`, `OFF`, `ON_OFF` (normalized); `QC_ON/OFF/ON_OFF` (replicate counts); flow-seq gate counts; computational proxies `SalisLab*` (RBS calculator) and `mfe_seq_*` (ViennaRNA).
- Split: source-disjoint 70/15/15 (target never crosses train/test).

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
- Cross-study raw ON/OFF must not be merged; VISTA data is a separate external set.

## Distribution
- Angenent-Mari dataset: CC BY 4.0. RefSeq sequences: public domain (NCBI). VISTA: verify before redistribution.

## Maintenance
Static versioned release; runner + manifests + hash for reproducibility. No live leaderboard promised.