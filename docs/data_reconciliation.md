# Data reconciliation v0.2

Date: 2026-08-21

This note replaces the contradictory v0.1 “≥70k gate” narrative. The project has
two useful sequence-mapped datasets, but their labels and preprocessing are not
interchangeable. They are therefore separate evidence tracks.

## 1. Canonical track

The primary Angenent-Mari CSV contains 97,436 rows. After excluding the 4,705
random-sequence controls from target ranking, 92,731 virus+TF rows remain across
931 target groups (23 virus and 908 human-derived sources).

| admission state | rows | use |
|---|---:|---|
| `admitted_paired` | 52,861 | Canonical R1 ranking and prediction labels across 926 targets. |
| `admitted_single_label` | 27,439 | Retained for accounting; not assigned a paired outcome. |
| `retained_no_label` | 12,431 | Retained for accounting; not assigned an outcome. |

Every R1 paper table must call the main labeled sample “52,861 paired records,”
not 91,534. Canonical `ON_OFF` is the signed difference `ON - OFF`; 7,428 paired
records have a negative value and must not be silently clamped.

Absolute coordinates were reconstructed for 87,989 of the 92,731 canonical
virus+TF rows; 4,742 remain `no_coord`. Coordinate status does not create a
label, and unresolved rows remain visible in the accounting ledger.

## 2. Official QC2 label array

The original authors' model asset contains 91,534 rows of `[ON, OFF, ON_OFF]`
labels but no sequences or source identifiers. It is preserved as provenance,
not used as a target-ranking table. Its row count cannot be combined with the
canonical source mapping to claim a 91,534-row canonical leaderboard.

## 3. BEACON sequence-mapped track

BEACON provides 91,534 148-nt sequence rows. Mapping through the GSE149225
`source_sequence` and oligo identifiers attributes all rows to:

- 40,824 virus rows from 23 targets;
- 47,005 TF rows from 905 targets;
- 3,705 random rows forming one pooled source group.

The BEACON `ON_OFF` values use a separately reprocessed normalization. They do
not equal canonical signed `ON - OFF` and therefore form R2 rather than extending
R1. The random pooled group is excluded from target-ranking metrics.

The distributed BEACON train/validation/test files are row splits. All 23 virus
targets occur across those splits, so that split cannot establish unseen-virus
generalization. v0.2 creates a fresh source-disjoint mixed track and a TF-to-virus
domain-OOD track in `src/beacon_target_benchmark.py`.

## 4. VISTA external context track

The VISTA workbook contains 189 sites for one mCherry target with paired
truncated and full-target measurements. It is analyzed as a within-target paired
context stress test. It does not close a multi-target external-validation gate.

## 5. Reporting consequence

The old “≥70k gate passed/failed” binary has been retired because it mixed scale,
sequence mapping, source mapping, and label semantics. The paper must instead
state the exact row and target counts for each evidence track and must not merge
their raw outcomes. This preserves both datasets without overstating either one.
