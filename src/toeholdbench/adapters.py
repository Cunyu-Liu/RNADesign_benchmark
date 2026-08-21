"""Method registry + score adapter (contract §10).

Every method that scores candidates must be registered with its identity,
information regime, score direction, and dataset exposure. The adapter converts
original scores to the benchmark's higher-is-better convention and refuses
silent imputation: missing, duplicate, or non-finite scores fail the track.
"""
import numpy as np
import pandas as pd

REQUIRED_METHOD_FIELDS = [
    "method_id", "family", "official_source", "source_commit", "checkpoint",
    "official_or_adapted", "information_regime", "training_mode", "objective",
    "original_score_direction", "benchmark_score_transform", "parameter_count",
    "tuning_budget", "seeds", "environment", "dataset_exposure",
]

PREDICTION_FIELDS = ["run_id", "track_id", "fold", "target_id",
                     "target_cluster_id", "record_id", "method_id", "seed", "score"]


def validate_method_entry(entry):
    missing = [f for f in REQUIRED_METHOD_FIELDS if f not in entry]
    if missing:
        raise ValueError(f"method entry missing fields: {missing}")
    if entry["original_score_direction"] not in ("higher_better", "lower_better"):
        raise ValueError("original_score_direction must be higher/lower_better")
    return True


def adapt_scores(scores, direction):
    """Convert original scores to benchmark higher-is-better."""
    if direction == "higher_better":
        return np.asarray(scores, dtype=float)
    if direction == "lower_better":
        return -np.asarray(scores, dtype=float)
    raise ValueError(f"unknown direction: {direction}")


def load_predictions(path):
    df = pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path)
    missing = [f for f in PREDICTION_FIELDS if f not in df.columns]
    if missing:
        raise ValueError(f"prediction file missing fields: {missing}")
    if not np.isfinite(df["score"].astype(float)).all():
        raise ValueError("non-finite scores present: method-track FAIL "
                         "(contract forbids imputation)")
    dup = df.duplicated(subset=["track_id", "fold", "record_id", "method_id", "seed"])
    if dup.any():
        raise ValueError(f"{int(dup.sum())} duplicate prediction rows")
    return df


def check_coverage(predictions, eligible_manifest):
    """100% score coverage on the frozen eligible set; loud failure otherwise."""
    eligible = set(
        zip(eligible_manifest["record_id"], eligible_manifest["target_id"]))
    have = set(zip(predictions["record_id"], predictions["target_id"]))
    missing = eligible - have
    if missing:
        raise ValueError(f"score coverage incomplete: {len(missing)} eligible "
                         f"candidates unscored (first: {sorted(missing)[:3]})")
    extra = have - eligible
    if extra:
        raise ValueError(f"predictions contain non-eligible candidates: "
                         f"{len(extra)} (first: {sorted(extra)[:3]})")
    return True
