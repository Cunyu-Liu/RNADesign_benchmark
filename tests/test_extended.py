"""Extended metric tests (FIX-5): bootstrap CI correctness, edge cases, runner integration."""
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from metrics.metrics import success_at_k, ndcg_at_k, normalized_regret, pareto_front_size, mean_with_ci  # noqa: E402
from beacon_target_benchmark import attach_source_manifest, published_split_audit  # noqa: E402


def test_mean_with_ci_basic():
    rng = np.random.default_rng(1)
    m, lo, hi = mean_with_ci([1.0, 2.0, 3.0], rng=rng)
    assert abs(m - 2.0) < 1e-9
    assert lo <= m <= hi


def test_mean_with_ci_single():
    m, lo, hi = mean_with_ci([5.0], rng=np.random.default_rng(0))
    assert abs(m - 5.0) < 1e-9


def test_mean_with_ci_empty():
    m, lo, hi = mean_with_ci([])
    assert np.isnan(m)


def test_success_at_k_edge():
    assert success_at_k([], {}, 1) == 0
    assert success_at_k(["a", "b"], {"b": True}, 1) == 0
    assert success_at_k(["a", "b"], {"b": True}, 2) == 1


def test_ndcg_zero_ideal():
    assert ndcg_at_k(["a", "b"], {"a": 0.0, "b": 0.0}, 5) == 0.0


def test_regret_constant():
    assert normalized_regret(["a", "b"], {"a": 3.0, "b": 3.0}, 1) == 0.0


def test_pareto_empty():
    assert pareto_front_size([], {}, {}) == 0


def test_runner_integration():
    """End-to-end: build a tiny canonical-like df, run runner.evaluate, check output schema."""
    import runner
    rng = np.random.default_rng(0)
    targets = [f"t{i}" for i in range(6)]
    rows = []
    for t in targets:
        n = 10
        for j in range(n):
            rows.append({
                "target_id": t, "record_id": f"{t}_r{j}",
                "split": "train" if t in targets[:4] else "test",
                "ON": float(rng.random()), "OFF": float(rng.random()),
                "ON_OFF": float(rng.random() - 0.5),
            })
    df = pd.DataFrame(rows)
    test = df[df["split"] == "test"]
    scores = rng.random(len(test))
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "res")
        agg = runner.evaluate(df, scores, out_prefix=out)
        assert "success_at_1" in agg and "mean" in agg["success_at_1"]
        assert "ndcg_at_10" in agg
        assert "normalized_regret_at_10" in agg
        assert "pareto_front_coverage_at_10" in agg
        assert agg["target_accounting"]["n_targets"] == 2
        assert (
            agg["target_accounting"]["n_targets_with_feasible_candidate"]
            + agg["target_accounting"]["n_targets_without_feasible_candidate"]
            == 2
        )
        # files written
        assert os.path.exists(out + "_per_target.csv")
        assert os.path.exists(out + "_scores.csv")


def test_beacon_manifest_keeps_published_and_target_splits_distinct():
    data = pd.DataFrame({
        "source_sequence": ["target_a", "target_a", "target_b", "target_b"],
        "category": ["TF", "TF", "virus", "virus"],
        "sequence": ["ACGT", "CGTA", "TGCA", "GCAT"],
        "split": ["train", "test", "train", "test"],
    })
    manifest = pd.DataFrame({
        "target_id": ["beacon_target_0000", "beacon_target_0001"],
        "source_sequence": ["target_a", "target_b"],
        "category": ["TF", "virus"],
        "split": ["test", "train"],
    })
    merged = attach_source_manifest(data, manifest)
    assert merged["published_row_split"].tolist() == ["train", "test", "train", "test"]
    assert merged["split"].tolist() == ["test", "test", "train", "train"]
    assert merged["target_id"].tolist() == [
        "beacon_target_0000", "beacon_target_0000",
        "beacon_target_0001", "beacon_target_0001",
    ]
    assert not any(column.endswith(("_x", "_y")) for column in merged.columns)
    audit = published_split_audit(merged)
    assert audit["TF"]["test_target_overlap_fraction"] == 1.0
    assert audit["virus"]["test_target_overlap_fraction"] == 1.0


if __name__ == "__main__":
    test_mean_with_ci_basic()
    test_mean_with_ci_single()
    test_mean_with_ci_empty()
    test_success_at_k_edge()
    test_ndcg_zero_ideal()
    test_regret_constant()
    test_pareto_empty()
    test_runner_integration()
    test_beacon_manifest_keeps_published_and_target_splits_distinct()
    print("all extended metric + runner tests passed")
