import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from metrics.metrics import (
    success_at_k, ndcg_at_k, normalized_regret, pareto_front_size,
    pareto_front_ids, pareto_front_coverage, paired_mean_difference_ci,
    expected_random_ranking_metrics,
)
from model_utils import onehot_channels, onehot_flat


def test_success_at_k():
    succ = {"a": False, "b": True, "c": False}
    assert success_at_k(["b", "a", "c"], succ, 1) == 1
    assert success_at_k(["a", "c", "b"], succ, 2) == 0
    assert success_at_k(["a", "b", "c"], succ, 2) == 1


def test_ndcg_at_k():
    rel = {"a": 3.0, "b": 2.0, "c": 1.0}
    assert ndcg_at_k(["a", "b", "c"], rel, 3) == 1.0  # perfect order
    assert ndcg_at_k(["c", "b", "a"], rel, 3) < 1.0
    negative = {"a": -1.0, "b": -2.0, "c": -3.0}
    assert ndcg_at_k(["a", "b", "c"], negative, 3) == 1.0


def test_normalized_regret():
    rel = {"a": 1.0, "b": 0.0}
    assert normalized_regret(["a", "b"], rel, 1) == 0.0  # best in top-1
    assert normalized_regret(["b", "a"], rel, 1) == 1.0  # miss best


def test_pareto_front_size():
    on = {"a": 1.0, "b": 0.8, "c": 0.5}
    off = {"a": 0.1, "b": 0.1, "c": 0.9}
    # a dominates b (same OFF, higher ON) and c (higher ON, lower OFF); only a non-dominated
    assert pareto_front_size(["a", "b", "c"], on, off) == 1
    on2 = {"a": 1.0, "b": 0.5}
    off2 = {"a": 0.9, "b": 0.1}
    # a: high ON + high OFF; b: low OFF + low ON -> both non-dominated
    assert pareto_front_size(["a", "b"], on2, off2) == 2


def test_pareto_front_order_is_deterministic():
    on = {"a": 0.8, "b": 0.9, "c": 0.4}
    off = {"a": 0.1, "b": 0.2, "c": 0.8}
    assert pareto_front_ids(["a", "b", "c"], on, off) == ["b", "a"]
    assert pareto_front_ids(["c", "a", "b"], on, off) == ["b", "a"]


def test_pareto_front_coverage_uses_global_front():
    on = {"a": 0.9, "b": 1.0, "c": 0.5}
    off = {"a": 0.1, "b": 0.2, "c": 0.8}
    # a and b form the global front. Top-1 recovers one of the two.
    assert pareto_front_coverage(["a", "b", "c"], on, off, 1) == 0.5
    assert pareto_front_coverage(["c", "b", "a"], on, off, 2) == 0.5
    assert pareto_front_coverage(["b", "a", "c"], on, off, 2) == 1.0


def test_conv_channel_layout():
    flat = onehot_flat(["AACG"], length=4)
    channels = onehot_channels(["AACG"], length=4)
    assert channels.shape == (1, 4, 4)
    expected = np.array([
        [1, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1],
        [0, 0, 0, 0],
    ], dtype=np.float32)
    assert np.array_equal(channels[0], expected)
    # Direct reshape is the historical bug and must not equal channel-first data.
    assert not np.array_equal(flat.reshape(1, 4, 4), channels)


def test_paired_bootstrap_difference():
    d, lo, hi, p = paired_mean_difference_ci(
        [1, 1, 1, 1], [0, 0, 0, 0], rng=np.random.default_rng(2), n_bootstrap=200
    )
    assert d == 1.0 and lo == 1.0 and hi == 1.0
    assert np.isclose(p, 2 / 201)


def test_expected_random_ranking_metrics_are_exact():
    ids = ["a", "b", "c"]
    success = {"a": False, "b": True, "c": False}
    rel = {"a": 2.0, "b": 1.0, "c": 0.0}
    on = {"a": 1.0, "b": 0.8, "c": 0.2}
    off = {"a": 0.5, "b": 0.1, "c": 0.9}
    result = expected_random_ranking_metrics(ids, success, rel, on, off)
    assert np.isclose(result["success_at_1"], 1 / 3)
    assert result["success_at_3"] == 1.0
    expected_ndcg = np.mean([
        ndcg_at_k(list(order), rel, 10)
        for order in (
            ("a", "b", "c"), ("a", "c", "b"), ("b", "a", "c"),
            ("b", "c", "a"), ("c", "a", "b"), ("c", "b", "a"),
        )
    ])
    assert np.isclose(result["ndcg_at_10"], expected_ndcg)
    assert result["normalized_regret_at_10"] == 0.0
    assert result["pareto_front_coverage_at_10"] == 1.0


if __name__ == "__main__":
    test_success_at_k()
    test_ndcg_at_k()
    test_normalized_regret()
    test_pareto_front_size()
    test_pareto_front_order_is_deterministic()
    test_pareto_front_coverage_uses_global_front()
    test_conv_channel_layout()
    test_paired_bootstrap_difference()
    test_expected_random_ranking_metrics_are_exact()
    print("all metric tests passed")
