"""Extended metric tests (FIX-5): bootstrap CI correctness, edge cases, runner integration."""
import os
import sys
import tempfile

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/cunyuliu/ToeholdDesignBench/src")
from metrics.metrics import success_at_k, ndcg_at_k, normalized_regret, pareto_front_size, mean_with_ci  # noqa: E402


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
        # files written
        assert os.path.exists(out + "_per_target.csv")
        assert os.path.exists(out + "_scores.csv")


if __name__ == "__main__":
    test_mean_with_ci_basic()
    test_mean_with_ci_single()
    test_mean_with_ci_empty()
    test_success_at_k_edge()
    test_ndcg_zero_ideal()
    test_regret_constant()
    test_pareto_empty()
    test_runner_integration()
    print("all extended metric + runner tests passed")