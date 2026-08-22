"""Tests for the crowdsourced architecture-shift track (contract §9 Batch 4)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import v03_crowd as vc  # noqa: E402


def test_clean_seq_and_pad_to():
    assert vc.clean_seq("AUGCN") == "ATGCN"
    assert vc.pad_to("ATGC", 6) == "ATGCNN"
    assert vc.pad_to("ATGCATGC", 4) == "ATGC"
    assert len(vc.pad_to("AT", 30)) == 30


def test_pad_to_gives_zero_onehot_rows():
    import v03_tblr as vr
    m = vr.onehot(vc.pad_to("AT", 4), 4)
    assert m[:2].sum() == 2.0
    assert m[2:].sum() == 0.0  # N padding encodes as all-zero rows


def test_architecture_clusters_deterministic_and_complete_case():
    rng = np.random.default_rng(0)
    regs = pd.DataFrame({
        c: rng.normal(size=60) for c in vc.STRUCT_FEATURES
    })
    regs.loc[0, vc.STRUCT_FEATURES[3]] = np.nan  # one incomplete row
    labels1, n1 = vc.architecture_clusters(regs)
    labels2, n2 = vc.architecture_clusters(regs)
    assert n1 == 59
    assert np.isnan(labels1.loc[0])
    # deterministic: same seed -> identical labels
    assert (labels1.fillna(-1) == labels2.fillna(-1)).all()
    assert set(labels1.dropna().astype(int)) <= set(range(vc.CLUSTER_K))


def test_cluster_bootstrap_spearman_bounds():
    rng = np.random.default_rng(1)
    n = 80
    pred = rng.normal(size=n)
    outcome = pred + rng.normal(scale=0.5, size=n)
    clusters = np.repeat([0, 1, 2, 3], 20).astype(float)
    base, lo, hi = vc.cluster_bootstrap_spearman(
        pred, outcome, clusters, n_rep=200, seed=7)
    assert base == pytest.approx(
        float(spearmanr(pred, outcome).statistic))
    assert lo <= base <= hi


def test_cluster_bootstrap_excludes_nan_clusters():
    rng = np.random.default_rng(2)
    n = 60
    pred = rng.normal(size=n)
    outcome = pred + rng.normal(scale=0.3, size=n)
    clusters = np.repeat([0.0, 1.0, np.nan, 2.0], 15)
    base, lo, hi = vc.cluster_bootstrap_spearman(
        pred, outcome, clusters, n_rep=100, seed=3)
    assert np.isfinite(base) and np.isfinite(lo) and np.isfinite(hi)


def test_cluster_bootstrap_constant_prediction_returns_nan_safe():
    # scipy returns nan for constant input; the wrapper must not crash
    pred = np.ones(40)
    outcome = np.arange(40, dtype=float)
    clusters = np.repeat([0.0, 1.0], 20)
    base, lo, hi = vc.cluster_bootstrap_spearman(
        pred, outcome, clusters, n_rep=20, seed=5)
    assert np.isnan(base)
