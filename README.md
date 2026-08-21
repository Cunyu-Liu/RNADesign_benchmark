# ToeholdDesignBench

ToeholdDesignBench evaluates toehold-switch candidate prioritization at the
target level. Its central question is whether a method can rank candidates for an
unseen target under a fixed experimental budget—not merely predict pooled assay
values for individual rows.

The controlling protocol is the consolidated
[task contract v0.2.1](docs/task_contract_v0.2.1_consolidated.md). The v0.2
contract and v0.2.1 statistical addendum remain as change-history records.
Older reports and scripts remain available for audit, but their numerical results
must not be used in the revised manuscript.

## Evidence tracks

The release keeps three label systems separate:

- **Canonical main track:** 52,861 paired records from 926 label-bearing targets
  (the retained canonical table has 931 targets), signed `ON - OFF`, fixed
  target/source-disjoint split, success@K plus rank utility.
- **BEACON reconstruction:** 91,534 rows from 23 virus and 905 TF sources,
  BEACON-normalized `ON_OFF`, evaluated with a newly built source-disjoint split
  and TF-to-virus domain OOD. Its published row split is not used to claim
  unseen-target generalization.
- **VISTA context stress test:** 189 paired truncated/full measurements from one
  mCherry target. This is a single-target external context analysis, not evidence
  of general cross-target transfer.

These tracks are not merged into one label scale.

## Methods and metrics

The repository contains random, GC, thermodynamic, MLP, CNN, deeper CNN, and two
local sequence-plus-biophysical baselines. The latter learned models are
representative local baselines, not full reproductions of named published design
systems. Learned canonical baselines use seeds 0–4 and report the mean predicted
score.

The canonical primary metric is success@1 under the frozen threshold ON ≥ 0.5
and OFF ≤ 0.5. Secondary metrics are success@3/5, NDCG@10, normalized regret@10,
and global Pareto-front coverage@10. Targets—not candidate rows—are the
uncertainty and paired-comparison unit. The report always includes targets for
which no threshold-qualified candidate exists.

## Installation and data paths

Python 3.10+ and the packages in `requirements.txt` are required. For example:

```bash
python -m pip install -r requirements.txt
```

By default, scripts read `./data` and `./data/processed`. External locations can
be selected without editing code:

```bash
export TD_BENCH_ROOT=/path/to/ToeholdDesignBench-data
export TD_BENCH_PROCESSED="$TD_BENCH_ROOT/processed"
```

Public raw files can be downloaded with:

```bash
bash scripts/download_data.sh
```

The core v0.2 run also requires the prepared canonical parquet, frozen split
manifest, authoritative BEACON source mapping, and VISTA workbook listed by
`scripts/run_v02.sh`. The data release must place those derived artifacts at the
paths checked by that script. The VISTA workbook's redistribution status is not
assumed; the download instruction is supplied instead.

## One-command core reproduction

From the repository root, after preparing the data directory:

```bash
bash scripts/run_v02.sh
```

This entry runs the focused tests, five-seed canonical baselines, group
robustness summaries, corrected E1/E2/E4/E5/E6 analyses, BEACON source-disjoint
tracks, the paired VISTA stress test, a built-in runner example, and provisional
paper tables/figures with source-data CSVs and alt text. Paper-facing outputs are
written to `TD_BENCH_PROCESSED` with `_v02` in their names.

To evaluate a user-supplied canonical score file:

```bash
python src/runner.py \
  --method my_method \
  --scores my_scores.csv \
  --out "$TD_BENCH_PROCESSED/my_method_v02"
```

The CSV must contain exactly one finite `score` for every test `record_id`.

## Result status

The v0.1 result narratives in `docs/p3_baseline_report.md`, `docs/p4_report.md`,
and `docs/paper_draft.md` are archived. Do not copy their numbers into a
manuscript. The corrected manuscript is
[`docs/manuscript_v0.2.1.md`](docs/manuscript_v0.2.1.md) and uses only the final
v0.2.1 result package.

## Claim boundary

The current evidence can support a source-isolated candidate-ranking benchmark,
a BEACON domain-shift analysis, and a single-target paired context stress test.
It cannot establish universal full-target transfer failure, biochemical
specificity, de novo design validity, or prospective hit rate. Those claims
require broader external targets or new wet-lab evidence.
