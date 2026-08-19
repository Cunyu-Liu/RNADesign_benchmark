"""ToeholdDesignBench metrics (Gate 0 To-do D, contract section 7.5).

Design-utility metrics on a per-target top-K candidate ranking. All metrics take
(ranked candidate ids, per-candidate score dict, K) and are target-bootstrap-able.
Primary: success@K. Secondary: NDCG@K, normalized regret, Pareto front size.
"""
from __future__ import annotations

import numpy as np


def success_at_k(ranked: list, is_success: dict, K: int) -> int:
    """1 if any of the top-K ranked candidates is a pre-registered success, else 0."""
    for cid in ranked[:K]:
        if is_success.get(cid):
            return 1
    return 0


def ndcg_at_k(ranked: list, rel: dict, K: int) -> float:
    """NDCG@K with relevance = candidate score (higher is better)."""
    k = min(K, len(ranked))
    if k == 0:
        return 0.0
    dcg = 0.0
    for i, cid in enumerate(ranked[:k]):
        r = max(0.0, float(rel.get(cid, 0.0)))
        dcg += r / np.log2(i + 2)
    ideal = sorted((max(0.0, float(rel.get(cid, 0.0))) for cid in ranked), reverse=True)
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
    """Number of non-dominated candidates in top-K for (maximize ON, minimize OFF)
    plus one reference point at (min_ON, max_OFF)."""
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