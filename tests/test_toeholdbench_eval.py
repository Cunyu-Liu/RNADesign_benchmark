"""Tests for the toeholdbench single evaluator kernel (contract §9 Batch 2).

Acceptance: hand-enumerated tiny candidate sets verify the analytic random
baselines, tie-at-cutoff handling, NDCG, success, and regret; cluster bootstrap
and sign-flip show no systematic offset on zero-effect synthetic data; the CLI
reproduces the direct evaluator call and fails loudly on incomplete scores.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from toeholdbench.evaluator import (  # noqa: E402
    expected_ndcg, random_ndcg, expected_success, random_success,
    expected_regret, random_regret, evaluate_target, ideal_dcg,
    expected_dcg, expected_max_gain,
)
from toeholdbench.stats import cluster_bootstrap, signflip_pvalue, holm  # noqa: E402

W1 = 1.0
W2 = 1.0 / np.log2(3)
W3 = 1.0 / np.log2(4)


# ---------------------------------------------------------------------------
# hand-enumerated NDCG
# ---------------------------------------------------------------------------
def test_ndcg_no_ties_perfect():
    # scores rank gains perfectly: NDCG = 1
    assert expected_ndcg([3.0, 2.0, 1.0], [3.0, 1.0, 0.0], 10) == pytest.approx(1.0)


def test_ndcg_no_ties_imperfect():
    # scores [3,2,1] order gains [1, 3, 0] (candidate2 best but ranked 2nd)
    # DCG = 1*W1 + 3*W2 + 0*W3;  IDCG = 3*W1 + 1*W2 + 0*W3
    val = expected_ndcg([3.0, 2.0, 1.0], [1.0, 3.0, 0.0], 10)
    assert val == pytest.approx((1 * W1 + 3 * W2) / (3 * W1 + 1 * W2))


def test_ndcg_tied_pair():
    # scores [1,1,0], gains [3,1,0]: tied group occupies ranks 1-2
    # E[DCG] = (W1+W2) * mean(3,1) = 2*(W1+W2)
    # IDCG    = 3*W1 + 1*W2 + 0*W3
    val = expected_ndcg([1.0, 1.0, 0.5], [3.0, 1.0, 0.0], 10)
    assert val == pytest.approx((2 * (W1 + W2)) / (3 * W1 + 1 * W2))


def test_ndcg_tie_straddling_cutoff():
    # scores [1,1,1,0], gains [4,3,2,0], k=2: group of 3 straddles k=2
    # E[DCG@2] = (W1+W2) * mean(4,3,2) = 3*(W1+W2)
    # IDCG@2   = 4*W1 + 3*W2
    val = expected_ndcg([1.0, 1.0, 1.0, 0.0], [4.0, 3.0, 2.0, 0.0], 2)
    assert val == pytest.approx((3 * (W1 + W2)) / (4 * W1 + 3 * W2))


def test_ndcg_matches_enumeration_with_ties():
    # full enumeration over permutations of the tied group
    # (gains are min-subtracted first, per the contract's nonnegative gains)
    on_off = [4.0, 3.0, 2.0]
    base = min(on_off)
    gains = [v - base for v in on_off]
    scores = [1.0, 1.0, 1.0]
    from itertools import permutations
    vals = []
    idcg = (2 * W1 + 1 * W2 + 0 * W3)
    for perm in permutations(range(3)):
        g = [gains[i] for i in perm]
        vals.append((g[0] * W1 + g[1] * W2 + g[2] * W3) / idcg)
    assert expected_ndcg(scores, on_off, 10) == pytest.approx(np.mean(vals))


def test_ideal_dcg_and_flat_target():
    assert ideal_dcg([0.0, 0.0], 10) == 0.0  # flat -> ineligible
    assert ideal_dcg([2.0, 1.0], 1) == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# analytic random baselines
# ---------------------------------------------------------------------------
def test_random_ndcg_matches_enumeration():
    gains = [3.0, 1.0, 0.0]
    from itertools import permutations
    vals = []
    for perm in permutations(gains):
        vals.append(perm[0] * W1 + perm[1] * W2 + perm[2] * W3)
    expect = np.mean(vals) / (3 * W1 + 1 * W2 + 0 * W3)
    assert random_ndcg(gains, 10) == pytest.approx(expect)


def test_random_ndcg_ties_are_irrelevant():
    # analytic random baseline is seed-free and permutation-free
    a = random_ndcg([3.0, 1.0, 0.0], 10)
    b = random_ndcg([1.0, 3.0, 0.0], 10)
    expect = (W1 + W2 + W3) * (4.0 / 3.0) / (3 * W1 + 1 * W2)
    assert a == b == pytest.approx(expect)


def test_random_success_hypergeometric():
    # 1 success among 3, k=1 -> 1/3
    assert random_success([True, False, False], 1) == pytest.approx(1 / 3)
    # k=2 -> 1 - C(2,2)/C(3,2) = 1 - 1/3 = 2/3
    assert random_success([True, False, False], 2) == pytest.approx(2 / 3)
    # no success at all
    assert random_success([False, False], 2) == 0.0


def test_random_regret_matches_enumeration():
    gains = [3.0, 0.0]
    # random top-1: E[max] = 1.5 -> regret = (3-1.5)/3 = 0.5
    assert random_regret(gains, 1) == pytest.approx(0.5)
    gains = [3.0, 1.0, 0.0]
    from itertools import permutations
    vals = []
    for perm in permutations(gains):
        vals.append((3 - perm[0]) / 3.0)
    assert random_regret(gains, 1) == pytest.approx(np.mean(vals))


# ---------------------------------------------------------------------------
# tie-aware success / regret
# ---------------------------------------------------------------------------
def test_success_tie_at_cutoff():
    # top-1 from tied group of 3 with 1 success -> 1/3
    val = expected_success([1.0, 1.0, 1.0, 0.0], [True, False, False, False], 1)
    assert val == pytest.approx(1 / 3)


def test_success_tie_partial_cutoff():
    # k=2 from tied group of 3 with 1 success -> P(success in 2 random of 3) = 2/3
    val = expected_success([1.0, 1.0, 1.0, 0.0], [True, False, False, False], 2)
    assert val == pytest.approx(2 / 3)


def test_success_group_fully_inside():
    val = expected_success([1.0, 1.0, 0.0], [False, True, False], 2)
    assert val == 1.0


def test_regret_tied_top1():
    # tied pair gains [3,0], k=1: E[max] = 1.5 -> regret 0.5
    val = expected_regret([1.0, 1.0], [3.0, 0.0], 1)
    assert val == pytest.approx(0.5)


def test_regret_deterministic_order():
    assert expected_regret([1.0, 0.5], [3.0, 0.0], 1) == pytest.approx(0.0)
    assert expected_regret([0.5, 1.0], [3.0, 0.0], 1) == pytest.approx(1.0)


def test_expected_max_gain_enumeration():
    gains = [4.0, 3.0, 2.0]
    from itertools import combinations
    for j in (1, 2, 3):
        subsets = list(combinations(gains, j))
        expect = np.mean([max(s) for s in subsets])
        got = expected_max_gain([1.0, 1.0, 1.0], gains, j)
        assert got == pytest.approx(expect), f"j={j}"


# ---------------------------------------------------------------------------
# evaluate_target bundle
# ---------------------------------------------------------------------------
def test_evaluate_target_ineligible():
    assert evaluate_target([1.0], [1.0]) is None            # singleton
    assert evaluate_target([1.0, 2.0], [0.0, 0.0]) is None  # flat label
    assert evaluate_target([1.0, np.nan], [1.0, 0.0]) is None  # non-finite score


def test_evaluate_target_bundle_fields():
    res = evaluate_target([3.0, 2.0, 1.0], [3.0, 1.0, 0.0],
                          [3.0, 1.0, 0.0], [0.0, 0.0, 0.0],
                          thresholds=[(0.5, 0.5)])
    assert res["ndcg@10"] == pytest.approx(1.0)
    assert res["random_ndcg@10"] < 1.0
    assert "success@1_0.5_0.5" in res and "random_success@1_0.5_0.5" in res
    assert res["success@1_0.5_0.5"] == pytest.approx(1.0)


def test_spearman_with_ties():
    res = evaluate_target([1.0, 1.0, 0.0], [3.0, 1.0, 0.0])
    # ranks (higher value = higher rank): score [2.5,2.5,1], label [3,2,1]
    # -> rho = +sqrt(3)/2
    assert res["spearman"] == pytest.approx(np.sqrt(3) / 2)


# ---------------------------------------------------------------------------
# statistics: cluster bootstrap & sign-flip
# ---------------------------------------------------------------------------
def _synth(n_clusters=20, per_cluster=5, effect=0.0, seed=0):
    rng = np.random.default_rng(seed)
    a = rng.normal(size=n_clusters * per_cluster)
    b = a - effect + rng.normal(scale=0.5, size=n_clusters * per_cluster)
    cl = np.repeat(np.arange(n_clusters), per_cluster)
    return a, b, cl


def test_bootstrap_zero_effect_contains_zero():
    a, b, cl = _synth(effect=0.0, seed=1)
    res = cluster_bootstrap(a, b, cl, n_rep=2000, seed=20260821)
    assert res["ci_low"] <= 0.0 <= res["ci_high"]
    assert abs(res["mean_diff"]) < 0.2


def test_bootstrap_positive_effect_excludes_zero():
    a, b, cl = _synth(effect=1.0, seed=2)
    res = cluster_bootstrap(a, b, cl, n_rep=2000, seed=20260821)
    assert res["mean_diff"] > 0.5
    assert res["ci_low"] > 0


def test_bootstrap_clusters_resampled_whole():
    # identical per-cluster values -> every resample has identical mean
    a = np.arange(10, dtype=float)
    b = a + 1.0
    cl = np.repeat([0, 1], 5)
    res = cluster_bootstrap(a, b, cl, n_rep=100, seed=3)
    assert res["mean_diff"] == pytest.approx(-1.0)
    assert res["ci_low"] == pytest.approx(-1.0)
    assert res["ci_high"] == pytest.approx(-1.0)


def test_signflip_zero_effect_p_not_conservatively_small():
    # under H0 the p-value is ~Uniform(0,1); over many draws the fraction of
    # small p-values must not be systematically inflated
    rng = np.random.default_rng(42)
    ps = []
    for s in range(200):
        n = 12
        a = rng.normal(size=n)
        b = rng.normal(size=n)
        cl = np.arange(n)
        ps.append(signflip_pvalue(a, b, cl, n_rep=1000, seed=s)["p_value"])
    ps = np.array(ps)
    assert ps.mean() > 0.35
    assert (ps < 0.05).mean() < 0.15  # nominal 0.05; generous tolerance


def test_signflip_known_positive_effect():
    a, b, cl = _synth(effect=1.5, seed=5)
    res = signflip_pvalue(a, b, cl, n_rep=5000, seed=20260821)
    assert res["p_value"] < 0.001


def test_holm_two_contrasts():
    assert holm([0.01, 0.04]) == pytest.approx([0.02, 0.04])
    assert holm([0.04, 0.01]) == pytest.approx([0.04, 0.02])
    assert holm([0.03, 0.03]) == pytest.approx([0.06, 0.06])


# ---------------------------------------------------------------------------
# CLI: single evaluation entry point
# ---------------------------------------------------------------------------
def _tiny_track(tmp_path):
    rows = []
    labels = {
        "t1": ([5.0, 3.0, 1.0], [0.0, 0.0, 0.0]),
        "t2": ([4.0, 2.0, 0.5], [1.0, 0.0, 0.0]),
    }
    for tid, (ons, offs) in labels.items():
        for i, (on, off) in enumerate(zip(ons, offs)):
            rows.append({
                "record_id": f"{tid}_c{i}", "study_id": "angenent_mari_2020",
                "assay_id": "x", "label_view": "canonical", "target_id": tid,
                "target_cluster_id": f"cl_{tid}", "candidate_id": f"{tid}_c{i}",
                "outer_fold": 0, "information_regime": "construct",
                "source_accession_version": None,
                "trigger_sequence": "A" * 30, "switch_or_construct_sequence": None,
                "candidate_start": None, "candidate_end": None, "strand": None,
                "context_512": None, "context_mask": None,
                "mapping_status": "unique", "label_on": on, "label_off": off,
                "label_semantics": "normalized_fluorescence_ON_OFF",
                "eligibility_status": "eligible_ranking",
            })
    df = pd.DataFrame(rows)
    p = tmp_path / "track.parquet"
    df.to_parquet(p)
    return p, df


def _tiny_predictions(tmp_path, track):
    rng = np.random.default_rng(7)
    rows = []
    for seed in (1, 2):
        for tid in ("t1", "t2"):
            for i in range(3):
                rows.append({
                    "run_id": "r", "track_id": "canonical", "fold": 0,
                    "target_id": tid, "target_cluster_id": f"cl_{tid}",
                    "record_id": f"{tid}_c{i}", "method_id": "M1", "seed": seed,
                    "score": float(rng.normal()),
                })
    p = tmp_path / "preds.parquet"
    pd.DataFrame(rows).to_parquet(p)
    return p


def test_cli_evaluate(tmp_path):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    from toeholdbench.__main__ import main
    track, tdf = _tiny_track(tmp_path)
    preds = _tiny_predictions(tmp_path, track)
    # self-contrast must be rejected
    with pytest.raises(ValueError, match="self-contrast"):
        main(["evaluate", "--track", str(track), "--predictions", str(preds),
              "--output", str(tmp_path / "run1"),
              "--primary-contrast", "M1:M1"])
    out2 = tmp_path / "run2"
    rc = main(["evaluate", "--track", str(track), "--predictions", str(preds),
               "--output", str(out2)])
    assert rc == 0
    tm = pd.read_csv(out2 / "target_metrics.csv")
    assert len(tm) == 2  # one row per target for M1
    assert "ndcg@10" in tm.columns and "random_ndcg@10" in tm.columns
    ms = pd.read_csv(out2 / "method_summary.csv")
    assert len(ms) == 1
    # determinism: same inputs -> identical summary
    out3 = tmp_path / "run3"
    main(["evaluate", "--track", str(track), "--predictions", str(preds),
          "--output", str(out3)])
    ms3 = pd.read_csv(out3 / "method_summary.csv")
    pd.testing.assert_frame_equal(ms, ms3)


def test_cli_fails_on_missing_coverage(tmp_path):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    from toeholdbench.__main__ import main
    from toeholdbench.adapters import check_coverage, load_predictions
    track, _ = _tiny_track(tmp_path)
    preds = _tiny_predictions(tmp_path, track)
    df = load_predictions(preds)
    df = df[df["record_id"] != "t1_c0"]  # drop every seed of one record
    p2 = tmp_path / "incomplete.parquet"
    df.to_parquet(p2)
    with pytest.raises(ValueError, match="coverage"):
        check_coverage(load_predictions(p2), pd.read_parquet(track))


def test_adapter_rejects_nonfinite_and_duplicates(tmp_path):
    from toeholdbench.adapters import load_predictions
    preds = _tiny_predictions(tmp_path, None)
    df = pd.read_parquet(preds)
    df.loc[0, "score"] = np.inf
    bad = tmp_path / "nonfinite.parquet"
    df.to_parquet(bad)
    with pytest.raises(ValueError, match="non-finite"):
        load_predictions(bad)
    df2 = pd.read_parquet(preds)
    df2 = pd.concat([df2, df2.iloc[[0]]])
    dup = tmp_path / "dup.parquet"
    df2.to_parquet(dup)
    with pytest.raises(ValueError, match="duplicate"):
        load_predictions(dup)


def test_expected_dcg_all_tied_equals_random():
    gains = [4.0, 3.0, 2.0, 0.0]
    scores = [1.0] * 4
    assert expected_dcg(scores, gains, 3) == pytest.approx(
        (W1 + W2 + W3) * np.mean(gains))
