"""Target-level evaluator with analytic random expectations and analytic tie policy.

Contract §4 (endpoints), §2.4 (random & ties):

- relevance gain: ``ON - OFF`` minus the within-target minimum, linear nonnegative;
- primary metric: mean per-target NDCG@10 over targets with >=2 candidates and
  ideal DCG > 0 (targets equally weighted);
- ties at cutoffs: analytic expectation over equiprobable permutations of
  equal-score candidates (never ``record_id`` or input order);
- random baselines: analytic per-target expectation of a uniformly random
  ranking (never a single seed-0 draw).

The tie-aware quantities implemented here:

- ``expected_ndcg``: E[DCG@k] = sum over score-groups of
  (sum of position weights covered by the group inside the top-k block)
  x mean(gain of group members) — exact because each group member is equally
  likely at each position of the group's block.
- ``expected_success``: P(at least one success candidate in top-k) with the
  straddling group handled by hypergeometric probabilities.
- ``expected_regret``: E[max gain within top-k] via the exact order-statistic
  identity P(max <= v) = C(#{<=v}, j) / C(m, j) for the random j-subset of the
  straddling group.
"""
from math import comb, log2

import numpy as np


def position_weights(k):
    """DCG position weights 1/log2(i+1), i = 1..k (0-indexed i-1 -> log2(i+1))."""
    return [1.0 / log2(i + 1) for i in range(1, k + 1)]


def gains_from_labels(on_off):
    """Within-target min-subtracted linear nonnegative gains."""
    g = np.asarray(on_off, dtype=float)
    if len(g) == 0:
        return g
    return g - g.min()


def _group_by_score(scores):
    """Candidate indices sorted by score desc; groups of equal scores.

    Returns list of groups (lists of candidate positions into the sorted order),
    where positions are 0-based ranks. Ties are grouped; group order is by
    descending score.
    """
    order = np.argsort(-np.asarray(scores, dtype=float), kind="stable")
    s = np.asarray(scores, dtype=float)[order]
    groups = []
    start = 0
    for i in range(1, len(s) + 1):
        if i == len(s) or s[i] != s[start]:
            groups.append((start, i))  # half-open rank interval
            start = i
    return order, groups


def expected_dcg(scores, gains, k):
    """E[DCG@k] under the analytic tie policy (higher score = better)."""
    n = len(scores)
    if n == 0:
        return 0.0
    k = min(k, n)
    order, groups = _group_by_score(scores)
    g = np.asarray(gains, dtype=float)[order]
    w = position_weights(k)
    dcg = 0.0
    for (a, b) in groups:
        lo, hi = max(a, 0), min(b, k)  # ranks inside top-k are 0..k-1
        if hi <= lo:
            continue
        block_w = sum(w[lo:hi])
        mean_gain = float(g[a:b].mean())
        dcg += block_w * mean_gain
    return dcg


def ideal_dcg(gains, k):
    n = len(gains)
    if n == 0:
        return 0.0
    k = min(k, n)
    w = position_weights(k)
    s = np.sort(np.asarray(gains, dtype=float))[::-1]
    return float(sum(wi * gi for wi, gi in zip(w, s[:k])))


def expected_ndcg(scores, on_off, k=10):
    """Tie-aware expected NDCG@k; returns 0.0 when ideal DCG <= 0."""
    g = gains_from_labels(on_off)
    if len(g) == 0:
        return 0.0
    idcg = ideal_dcg(g, k)
    if idcg <= 0:
        return 0.0
    return expected_dcg(scores, g, k) / idcg


def random_ndcg(on_off, k=10):
    """Analytic E[NDCG@k] of a uniformly random ranking (all scores tied)."""
    g = gains_from_labels(on_off)
    n = len(g)
    if n == 0:
        return 0.0
    idcg = ideal_dcg(g, k)
    if idcg <= 0:
        return 0.0
    kk = min(k, n)
    e_dcg = sum(position_weights(kk)) * float(np.mean(g))
    return e_dcg / idcg


def expected_success(scores, is_success, k):
    """Tie-aware P(at least one success candidate in top-k), in [0, 1]."""
    n = len(scores)
    if n == 0:
        return 0.0
    k = min(k, n)
    order, groups = _group_by_score(scores)
    succ = np.asarray([1 if x else 0 for x in is_success], dtype=int)[order]
    p_fail = 1.0
    for (a, b) in groups:
        lo, hi = max(a, 0), min(b, k)
        if hi <= lo:
            continue
        m = b - a                     # group size
        s = int(succ[a:b].sum())      # successes in the whole group
        if s == 0:
            continue                  # full group contributes no success
        if hi >= b:
            # group fully inside top-k
            return 1.0 if s > 0 else p_fail
        j = hi - lo                   # members of this group entering top-k
        if m - s < j:
            continue                  # cannot avoid a success
        p_fail *= comb(m - s, j) / comb(m, j)
    return 1.0 - p_fail


def random_success(is_success, k):
    n = len(is_success)
    if n == 0:
        return 0.0
    k = min(k, n)
    s = int(sum(1 for x in is_success if x))
    if s == 0:
        return 0.0
    if n - s < k:
        return 1.0
    return 1.0 - comb(n - s, k) / comb(n, k)


def expected_max_gain(scores, gains, k):
    """E[max gain within top-k] under the analytic tie policy."""
    n = len(scores)
    if n == 0:
        return 0.0
    k = min(k, n)
    order, groups = _group_by_score(scores)
    g = np.asarray(gains, dtype=float)[order]
    best = 0.0
    for (a, b) in groups:
        lo, hi = max(a, 0), min(b, k)
        if hi <= lo:
            continue
        if hi >= b:
            # fully included: deterministic max
            best = max(best, float(g[a:b].max()))
        else:
            j = hi - lo
            m = b - a
            sub = np.sort(g[a:b])[::-1]
            # E[max of a uniformly random j-subset] via exact survival:
            # with distinct descending values u_1 > u_2 > ..., P(max = u_i)
            # = S(u_i) - S(u_{i-1}) where S(u) = P(max >= u), S(u_0) = 0
            uniq = np.unique(sub)[::-1]
            e_max = 0.0
            prev_surv = 0.0  # P(max >= the next larger value) = 0 at start
            for u in uniq:
                n_ge = int((sub >= u).sum())
                if m - n_ge >= j:
                    p_lt = comb(m - n_ge, j) / comb(m, j)  # P(max < u)
                else:
                    p_lt = 0.0
                surv = 1.0 - p_lt  # P(max >= u)
                e_max += u * (surv - prev_surv)
                prev_surv = surv
            best = max(best, e_max)
    return best


def expected_regret(scores, on_off, k):
    """Tie-aware normalized regret@k in [0, 1] (0 = best possible top-k)."""
    g = gains_from_labels(on_off)
    if len(g) == 0:
        return 0.0
    gmax = float(np.max(g))
    gmin = float(np.min(g))
    if gmax == gmin:
        return 0.0
    em = expected_max_gain(scores, g, k)
    return (gmax - em) / (gmax - gmin)


def random_regret(on_off, k):
    """Analytic E[normalized regret@k] of a uniformly random ranking."""
    g = gains_from_labels(on_off)
    n = len(g)
    if n == 0:
        return 0.0
    gmax, gmin = float(np.max(g)), float(np.min(g))
    if gmax == gmin:
        return 0.0
    kk = min(k, n)
    # random ranking: top-k is a uniformly random kk-subset
    uniq = np.unique(g)[::-1]
    prev_surv = 0.0
    e_max = 0.0
    for u in uniq:
        n_ge = int((g >= u).sum())
        if n - n_ge >= kk:
            p_lt = comb(n - n_ge, kk) / comb(n, kk)
        else:
            p_lt = 0.0
        surv = 1.0 - p_lt
        e_max += u * (surv - prev_surv)
        prev_surv = surv
    return (gmax - e_max) / (gmax - gmin)


# ---------------------------------------------------------------------------
# per-target evaluation bundle
# ---------------------------------------------------------------------------
SUCCESS_KS = (1, 3, 5, 10)
PRIMARY_K = 10


def evaluate_target(scores, on_off, on_labels=None, off_labels=None,
                    thresholds=None, ks=SUCCESS_KS, primary_k=PRIMARY_K):
    """Evaluate one target. Returns None if the target is ineligible for ranking
    (fewer than 2 candidates or ideal DCG <= 0); coverage-only targets are the
    caller's responsibility.

    thresholds: iterable of (on_thr, off_thr) pairs; a candidate is a success
    when ON >= on_thr and OFF <= off_thr. When on/off labels are unavailable,
    success metrics are returned as NaN.
    """
    scores = np.asarray(scores, dtype=float)
    on_off = np.asarray(on_off, dtype=float)
    n = len(scores)
    if n < 2 or not np.all(np.isfinite(scores)):
        return None
    g = gains_from_labels(on_off)
    idcg = ideal_dcg(g, primary_k)
    if idcg <= 0:
        return None
    out = {
        "n_candidates": n,
        "ndcg@10": expected_ndcg(scores, on_off, 10),
        "random_ndcg@10": random_ndcg(on_off, 10),
        "spearman": _spearman(scores, on_off),
    }
    for k in ks:
        out[f"regret@{k}"] = expected_regret(scores, on_off, k)
        out[f"random_regret@{k}"] = random_regret(on_off, k)
    if on_labels is not None and off_labels is not None and thresholds:
        on_l = np.asarray(on_labels, dtype=float)
        off_l = np.asarray(off_labels, dtype=float)
        for (ta, tb) in thresholds:
            is_succ = (on_l >= ta) & (off_l <= tb)
            key = f"success@{{}}_{ta}_{tb}"
            for k in ks:
                out[key.format(k)] = expected_success(scores, is_succ, k)
                out[f"random_{key.format(k)}"] = random_success(is_succ, k)
    return out


def _spearman(a, b):
    ra = _ranks(a)
    rb = _ranks(b)
    ra = np.asarray(ra, dtype=float)
    rb = np.asarray(rb, dtype=float)
    if len(ra) < 2:
        return float("nan")
    sa, sb = ra.std(), rb.std()
    if sa == 0 or sb == 0:
        return float("nan")
    return float(np.mean((ra - ra.mean()) * (rb - rb.mean())) / (sa * sb))


def _ranks(x):
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="stable")
    ranks = np.empty(len(x), dtype=float)
    i = 0
    while i < len(x):
        j = i
        while j + 1 < len(x) and x[order[j + 1]] == x[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for t in range(i, j + 1):
            ranks[order[t]] = avg
        i = j + 1
    return ranks
