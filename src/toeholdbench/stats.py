"""Cluster-level statistics: paired target-cluster bootstrap and paired sign-flip.

Contract §5 (statistical contract):

- 95% CI: 5,000-replicate paired target-cluster bootstrap; clusters resampled
  whole (targets never split from their cluster);
- formal P: 50,000-replicate cluster-level paired sign-flip/randomization with
  add-one correction;
- Holm correction over exactly the two pre-declared secondary contrasts.
"""
import numpy as np


def cluster_bootstrap(per_target_a, per_target_b, clusters, n_rep=5000, seed=20260821):
    """Paired target-cluster bootstrap of mean per-target differences.

    per_target_a/b: arrays aligned to targets; clusters: cluster id per target.
    Returns dict with mean difference and percentile CI. Clusters are resampled
    with replacement; the metric is the mean over the resampled target multiset.
    """
    per_target_a = np.asarray(per_target_a, dtype=float)
    per_target_b = np.asarray(per_target_b, dtype=float)
    clusters = np.asarray(clusters)
    uniq = np.unique(clusters)
    idx_by_cluster = {c: np.flatnonzero(clusters == c) for c in uniq}
    rng = np.random.default_rng(seed)
    diffs = per_target_a - per_target_b
    stats = np.empty(n_rep)
    for r in range(n_rep):
        pick = rng.integers(0, len(uniq), size=len(uniq))
        rows = np.concatenate([idx_by_cluster[uniq[c]] for c in pick])
        stats[r] = diffs[rows].mean()
    obs = float(diffs.mean())
    return {
        "mean_diff": obs,
        "ci_low": float(np.percentile(stats, 2.5)),
        "ci_high": float(np.percentile(stats, 97.5)),
        "n_rep": n_rep,
        "n_clusters": int(len(uniq)),
    }


def signflip_pvalue(per_target_a, per_target_b, clusters, n_rep=50000,
                    seed=20260821):
    """Cluster-level paired sign-flip/randomization test with add-one correction.

    Permutation statistic: mean over clusters of the cluster-mean paired
    difference, with randomly flipped cluster signs. H0: per-cluster paired
    differences are symmetric about 0.
    """
    per_target_a = np.asarray(per_target_a, dtype=float)
    per_target_b = np.asarray(per_target_b, dtype=float)
    clusters = np.asarray(clusters)
    diffs = per_target_a - per_target_b
    uniq = np.unique(clusters)
    cl_means = np.array([diffs[clusters == c].mean() for c in uniq])
    obs = float(np.abs(cl_means.mean()))
    rng = np.random.default_rng(seed)
    n_ge = 0
    for _ in range(n_rep):
        signs = rng.choice([-1.0, 1.0], size=len(cl_means))
        t = abs((cl_means * signs).mean())
        if t >= obs:
            n_ge += 1
    return {
        "statistic": obs,
        "p_value": (n_ge + 1) / (n_rep + 1),
        "n_rep": n_rep,
        "n_clusters": int(len(uniq)),
    }


def holm(pvalues):
    """Holm step-down adjustment. Returns adjusted p-values in input order."""
    p = np.asarray(pvalues, dtype=float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * p[idx]
        running = max(running, val)
        adj[idx] = min(1.0, running)
    return adj.tolist()
