"""ToeholdDesignBench metrics (Gate 0 To-do D, contract section 7.5).

Design-utility metrics on a per-target top-K candidate ranking. All metrics take
(ranked candidate ids, per-candidate score dict, K) and are target-bootstrap-able.
Primary: success@K. Secondary: NDCG@K, normalized regret, Pareto-front coverage.
"""
from __future__ import annotations

from math import comb

import numpy as np


def success_at_k(ranked: list, is_success: dict, K: int) -> int:
    """1 if any of the top-K ranked candidates is a pre-registered success, else 0."""
    for cid in ranked[:K]:
        if is_success.get(cid):
            return 1
    return 0


def ndcg_at_k(ranked: list, rel: dict, K: int) -> float:
    """NDCG@K with relevance = candidate score (higher is better).

    Relevance is shifted by the within-target minimum before discounting.  This
    preserves the ordering when ON-OFF is negative instead of silently clipping
    every negative candidate to zero.
    """
    k = min(K, len(ranked))
    if k == 0:
        return 0.0
    raw = [float(rel.get(cid, 0.0)) for cid in ranked]
    floor = min(raw)
    gains = {cid: float(rel.get(cid, 0.0)) - floor for cid in ranked}
    dcg = 0.0
    for i, cid in enumerate(ranked[:k]):
        r = gains[cid]
        dcg += r / np.log2(i + 2)
    ideal = sorted(gains.values(), reverse=True)
    idcg = sum(r / np.log2(i + 2) for i, r in enumerate(ideal[:k]))
    return dcg / idcg if idcg > 0 else 0.0


def normalized_regret(ranked: list, rel: dict, K: int) -> float:
    """(best available - best in top-K) / (best available - worst available)."""
    scores = [float(rel.get(cid, 0.0)) for cid in ranked]
    if not scores:
        return 0.0
    best = max(scores)
    worst = min(scores)
    best_in_k = max(scores[: min(K, len(scores))], default=worst)
    if best == worst:
        return 0.0
    return (best - best_in_k) / (best - worst)


def pareto_front_size(topk: list, on_score: dict, off_score: dict) -> int:
    """Number of non-dominated candidates within ``topk``.

    This descriptive helper is retained for compatibility.  It is not a design
    utility score because a large within-selection front is not necessarily good.
    Use :func:`pareto_front_coverage` for benchmark reporting.
    """
    pts = [(float(on_score[cid]), float(off_score[cid])) for cid in topk
           if cid in on_score and cid in off_score]
    if not pts:
        return 0
    # maximize ON, minimize OFF -> transform OFF to (-OFF) for a maximization front
    fr = []
    for on, off in pts:
        dominated = False
        for on2, off2 in pts:
            if on2 >= on and off2 <= off and (on2 > on or off2 < off):
                dominated = True
                break
        if not dominated:
            fr.append((on, off))
    return len(fr)


def pareto_front_ids(candidate_ids: list, on_score: dict, off_score: dict) -> list:
    """Deterministic non-dominated set for maximize-ON/minimize-OFF.

    Returned ids are ordered by descending ON, ascending OFF, then id.  The
    explicit order prevents an input-row-order-dependent Pareto@1 diagnostic.
    """
    ids = [cid for cid in candidate_ids if cid in on_score and cid in off_score]
    front = []
    for cid in ids:
        on = float(on_score[cid])
        off = float(off_score[cid])
        dominated = any(
            float(on_score[other]) >= on
            and float(off_score[other]) <= off
            and (float(on_score[other]) > on or float(off_score[other]) < off)
            for other in ids
        )
        if not dominated:
            front.append(cid)
    return sorted(front, key=lambda cid: (-float(on_score[cid]), float(off_score[cid]), str(cid)))


def pareto_front_coverage(ranked: list, on_score: dict, off_score: dict, K: int) -> float:
    """Fraction of the full candidate-set Pareto front recovered in top-K.

    The reference front is calculated over every ranked candidate, maximizing ON
    and minimizing OFF.  This makes the denominator independent of the submitted
    top-K and keeps the metric invariant to input row order.
    """
    front = set(pareto_front_ids(ranked, on_score, off_score))
    if not front:
        return 0.0
    return len(front.intersection(ranked[:K])) / len(front)


def expected_random_ranking_metrics(candidate_ids: list, is_success: dict, rel: dict,
                                    on_score: dict, off_score: dict) -> dict:
    """Exact per-target expectation under a uniformly random candidate ranking.

    The expectation is analytic, so the random baseline has no arbitrary seed or
    Monte Carlo error.  Success probabilities use sampling without replacement;
    expected DCG uses exchangeability of ranks; expected regret uses the order-
    statistic distribution; and every Pareto item has inclusion probability K/N.
    """
    ids = list(candidate_ids)
    n = len(ids)
    if n == 0:
        return {
            "success_at_1": 0.0,
            "success_at_3": 0.0,
            "success_at_5": 0.0,
            "ndcg_at_10": 0.0,
            "normalized_regret_at_10": 0.0,
            "normalized_regret_at_1": 0.0,
            "pareto_front_coverage_at_10": 0.0,
        }

    n_success = sum(bool(is_success.get(cid, False)) for cid in ids)

    def expected_success(k: int) -> float:
        k = min(k, n)
        n_failure = n - n_success
        p_all_failure = comb(n_failure, k) / comb(n, k) if n_failure >= k else 0.0
        return 1.0 - p_all_failure

    scores = np.asarray([float(rel.get(cid, 0.0)) for cid in ids], dtype=float)
    gains = scores - scores.min()
    rank_k = min(10, n)
    discounts = 1.0 / np.log2(np.arange(rank_k) + 2)
    ideal = np.sort(gains)[::-1][:rank_k]
    idcg = float(np.sum(ideal * discounts))
    expected_dcg = float(gains.mean() * discounts.sum())
    expected_ndcg = expected_dcg / idcg if idcg > 0 else 0.0

    def expected_regret(k: int) -> float:
        k = min(k, n)
        ordered = np.sort(scores)
        best = float(ordered[-1])
        worst = float(ordered[0])
        if best == worst:
            return 0.0
        denominator = comb(n, k)
        expected_max = sum(
            float(ordered[index]) * comb(index, k - 1) / denominator
            for index in range(k - 1, n)
        )
        return (best - expected_max) / (best - worst)

    front = pareto_front_ids(ids, on_score, off_score)
    expected_pareto_coverage = rank_k / n if front else 0.0
    return {
        "success_at_1": expected_success(1),
        "success_at_3": expected_success(3),
        "success_at_5": expected_success(5),
        "ndcg_at_10": expected_ndcg,
        "normalized_regret_at_10": expected_regret(10),
        "normalized_regret_at_1": expected_regret(1),
        "pareto_front_coverage_at_10": expected_pareto_coverage,
    }


def mean_with_ci(values: list, alpha: float = 0.05, n_bootstrap: int = 2000,
                 rng: np.random.Generator | None = None):
    """Bootstrap mean + 95% CI using target/source as the resampling unit."""
    if len(values) == 0:
        return (float("nan"), float("nan"), float("nan"))
    rng = rng or np.random.default_rng(0)
    arr = np.asarray(values, dtype=float)
    mean = float(arr.mean())
    boots = np.array([rng.choice(arr, size=len(arr), replace=True).mean()
                      for _ in range(n_bootstrap)])
    lo = float(np.quantile(boots, alpha / 2))
    hi = float(np.quantile(boots, 1 - alpha / 2))
    return mean, lo, hi


def paired_mean_difference_ci(a: list, b: list, alpha: float = 0.05,
                              n_bootstrap: int = 5000,
                              rng: np.random.Generator | None = None):
    """Paired target-bootstrap mean difference ``a - b`` and two-sided p-value."""
    aa = np.asarray(a, dtype=float)
    bb = np.asarray(b, dtype=float)
    if aa.shape != bb.shape:
        raise ValueError("paired inputs must have the same shape")
    if aa.size == 0:
        return (float("nan"), float("nan"), float("nan"), float("nan"))
    rng = rng or np.random.default_rng(0)
    diff = aa - bb
    indices = rng.integers(0, len(diff), size=(n_bootstrap, len(diff)))
    boots = diff[indices].mean(axis=1)
    estimate = float(diff.mean())
    lo = float(np.quantile(boots, alpha / 2))
    hi = float(np.quantile(boots, 1 - alpha / 2))
    # Add one simulated null-compatible result so a finite bootstrap never
    # reports the impossible value P=0.  This also declares the Monte Carlo
    # resolution of the reported tail probability.
    lower_tail = (np.count_nonzero(boots <= 0) + 1) / (n_bootstrap + 1)
    upper_tail = (np.count_nonzero(boots >= 0) + 1) / (n_bootstrap + 1)
    p = float(min(1.0, 2 * min(lower_tail, upper_tail)))
    return estimate, lo, hi, p
