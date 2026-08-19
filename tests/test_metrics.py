import sys
sys.path.insert(0, "/home/cunyuliu/ToeholdDesignBench/src")
from metrics.metrics import success_at_k, ndcg_at_k, normalized_regret, pareto_front_size


def test_success_at_k():
    succ = {"a": False, "b": True, "c": False}
    assert success_at_k(["b", "a", "c"], succ, 1) == 1
    assert success_at_k(["a", "c", "b"], succ, 2) == 0
    assert success_at_k(["a", "b", "c"], succ, 2) == 1


def test_ndcg_at_k():
    rel = {"a": 3.0, "b": 2.0, "c": 1.0}
    assert ndcg_at_k(["a", "b", "c"], rel, 3) == 1.0  # perfect order
    assert ndcg_at_k(["c", "b", "a"], rel, 3) < 1.0


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


if __name__ == "__main__":
    test_success_at_k()
    test_ndcg_at_k()
    test_normalized_regret()
    test_pareto_front_size()
    print("all metric tests passed")