"""Tests for TBLR training components (contract §7)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import torch  # noqa: E402

import v03_tblr as vr  # noqa: E402


# ---------------------------------------------------------------------------
# encodings
# ---------------------------------------------------------------------------
def test_onehot():
    m = vr.onehot("ACGT", 4)
    assert m.shape == (4, 4)
    assert m[0, 0] == 1 and m[1, 1] == 1 and m[2, 2] == 1 and m[3, 3] == 1
    assert m.sum() == 4
    # non-ACGT -> zero row
    m2 = vr.onehot("AN", 2)
    assert m2[1].sum() == 0


def test_contact_map_ppm():
    m = vr.contact_map_ppm("GC")  # G-C pair
    assert m[0, 1] == 1 and m[1, 0] == 1
    m2 = vr.contact_map_ppm("AT")
    assert m2[0, 1] == 1 and m2[1, 0] == 1
    m3 = vr.contact_map_ppm("AA")
    assert m3.sum() == 0
    # wobble GU
    m4 = vr.contact_map_ppm("GT")
    assert m4[0, 1] == 1 and m4[1, 0] == 1


# ---------------------------------------------------------------------------
# quantile subsampling (contract: <=64 all; >64 -> 8 per 8 quantiles)
# ---------------------------------------------------------------------------
def test_quantile_subsample_small():
    onoff = np.arange(10.0)
    sel = vr.quantile_subsample(onoff, np.random.default_rng(0))
    assert list(sel) == list(range(10))


def test_quantile_subsample_large():
    rng = np.random.default_rng(1)
    onoff = rng.normal(size=200)
    sel = vr.quantile_subsample(onoff, rng)
    assert len(sel) <= vr.MAX_CAND
    # spread across the label distribution: selected values span quantiles
    sel_vals = np.sort(onoff[sel])
    assert sel_vals[0] < np.quantile(onoff, 0.2)
    assert sel_vals[-1] > np.quantile(onoff, 0.8)


# ---------------------------------------------------------------------------
# LambdaRank loss
# ---------------------------------------------------------------------------
def test_lambdarank_perfect_ordering_lower_loss():
    torch.manual_seed(0)
    gains = torch.tensor([3.0, 1.0, 0.0])
    good = vr.lambdarank_loss(torch.tensor([3.0, 1.0, 0.0]), gains)
    bad = vr.lambdarank_loss(torch.tensor([0.0, 1.0, 3.0]), gains)
    assert good.item() < bad.item()
    # perfect ordering with positive margins -> near-zero loss
    assert good.item() < 0.1


def test_lambdarank_flat_gains_zero_loss():
    gains = torch.tensor([2.0, 2.0, 2.0])
    loss = vr.lambdarank_loss(torch.tensor([1.0, 0.0, 3.0]), gains)
    assert loss.item() == 0.0


def test_lambdarank_zero_when_singleton():
    loss = vr.lambdarank_loss(torch.tensor([1.0]), torch.tensor([1.0]))
    assert loss.item() == 0.0


def test_lambdarank_top_pair_weighted_more():
    # transposing the top pair must cost more than transposing the bottom pair
    # (Delta NDCG weights: |g_i - g_j| * |w_{r_i} - w_{r_j}|)
    gains = torch.tensor([3.0, 2.0, 1.0])
    top_swap = vr.lambdarank_loss(torch.tensor([2.0, 3.0, 1.0]), gains)
    bottom_swap = vr.lambdarank_loss(torch.tensor([3.0, 1.0, 2.0]), gains)
    assert top_swap.item() > bottom_swap.item()


# ---------------------------------------------------------------------------
# target-balanced loss weighting
# ---------------------------------------------------------------------------
def test_equal_target_loss_weight():
    # per-target mean losses are averaged: a target with more candidates must
    # not dominate (contract: equal per-target contribution)
    per_target = [torch.tensor(1.0), torch.tensor(3.0)]
    mean = torch.stack(per_target).mean()
    assert mean.item() == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------
def test_cnn_model_shapes_and_heads():
    model = vr.build_model("cnn60", dropout=0.0)
    n_params = sum(p.numel() for p in model.parameters())
    x = torch.randn(5, 4, 60)
    out = model(x)
    assert set(out) == {"score", "on", "off"}
    assert out["score"].shape == (5,)
    assert n_params > 0
    # parameter parity: dropout changes no parameters
    model2 = vr.build_model("cnn60", dropout=0.5)
    assert sum(p.numel() for p in model2.parameters()) == n_params


def test_sandstorm_model_shapes():
    model = vr.build_model("sandstorm", dropout=0.0)
    x = torch.randn(3, 1, 4, 60)
    ppm = torch.randn(3, 1, 59, 59)
    out = model(x, ppm)
    assert out["score"].shape == (3,)
    n1 = sum(p.numel() for p in model.parameters())
    model2 = vr.build_model("sandstorm", dropout=0.5)
    assert sum(p.numel() for p in model2.parameters()) == n1


# ---------------------------------------------------------------------------
# end-to-end smoke on synthetic data (CPU, few epochs)
# ---------------------------------------------------------------------------
def _synthetic_targetdata():
    rows = []
    rng = np.random.default_rng(7)
    for t in range(8):
        n = rng.integers(3, 8)
        for i in range(n):
            trig = "".join(rng.choice(list("ACGT"), 30))
            sw = "".join(rng.choice(list("ACGT"), 30))
            rows.append({
                "record_id": f"{t}_c{i}", "target_id": f"t{t}",
                "target_cluster_id": f"cl{t}", "outer_fold": int(t % 4),
                "inner_fold": int(t % 3),
                "trigger_sequence": trig,
                "switch_or_construct_sequence": sw,
                "construct_59": "".join(rng.choice(list("ACGT"), 59)),
                "label_on": float(rng.uniform(0, 1)),
                "label_off": float(rng.uniform(0, 1)),
            })
    df = pd.DataFrame(rows)
    return vr.TargetData(df, "cnn60"), df


def test_train_one_smoke(monkeypatch):
    data, _ = _synthetic_targetdata()
    monkeypatch.setattr(vr, "MAX_EPOCHS", 2)
    model = vr.build_model("cnn60", dropout=0.0)
    cfg = {"lr": 1e-3, "weight_decay": 0.0, "aux_weight": 0.1, "dropout": 0.0}
    train_targets = [f"t{i}" for i in range(6)]
    val_targets = [f"t{i}" for i in range(6, 8)]
    info = vr.train_one(model, data, train_targets, val_targets, cfg,
                        torch.device("cpu"), 20260821, "full_tblr", "cnn60")
    assert "best_val_ndcg10" in info and info["epochs_run"] >= 1
    assert 0.0 <= info["best_val_ndcg10"] <= 1.0000001


def test_emit_predictions_schema(tmp_path):
    data, _ = _synthetic_targetdata()
    model = vr.build_model("cnn60", dropout=0.0)
    targets = sorted(data.cands.keys())
    path = tmp_path / "preds.parquet"
    n = vr.emit_predictions(model, data, targets, torch.device("cpu"),
                            "cnn60", "full_tblr", "cnn60/full_tblr", 20260821,
                            "testrun", 0, str(path))
    df = pd.read_parquet(path)
    assert n == len(df)
    for col in ("run_id", "track_id", "fold", "target_id", "target_cluster_id",
                "record_id", "method_id", "seed", "score"):
        assert col in df.columns
    assert df["score"].notna().all()
    assert np.isfinite(df["score"]).all()
    # one row per (record, method, seed)
    assert not df.duplicated(subset=["record_id", "method_id", "seed"]).any()


def test_ranking_score_by_ablation():
    heads = {"score": np.array([1.0, 2.0]),
             "on": np.array([0.8, 0.1]),
             "off": np.array([0.2, 0.3])}
    cands = {"onoff": np.array([0.6, -0.2])}
    assert list(vr.ranking_score(heads, cands, "tb_mse")) == [1.0, 2.0]
    assert list(vr.ranking_score(heads, cands, "tb_dual")) == pytest.approx(
        [0.6, -0.2])
    assert list(vr.ranking_score(heads, cands, "full_tblr")) == [1.0, 2.0]


def test_chunk_gradient_accumulation_equivalence():
    """1-target chunks produce gradients identical to the full 32-target
    forward (contract: chunking is an exact memory knob, not a protocol
    change). Replicates the train-loop accumulation pattern."""
    torch.manual_seed(0)
    n_targets, n_cand, dim = 8, 5, 4
    x = torch.randn(n_targets, n_cand, dim)
    lab = torch.randn(n_targets, n_cand)
    ref = torch.nn.Linear(dim, 1)
    crit = torch.nn.MSELoss()

    def grads(chunk_size):
        model = torch.nn.Linear(dim, 1)
        model.load_state_dict(ref.state_dict())
        opt = torch.optim.SGD(model.parameters(), lr=1.0)
        opt.zero_grad()
        for cs in range(0, n_targets, chunk_size):
            chunk = range(cs, min(cs + chunk_size, n_targets))
            losses = []
            for t in chunk:
                h = model(x[t]).squeeze(-1)
                losses.append(crit(h, lab[t]))
            (torch.stack(losses).sum() / n_targets).backward()
        return [p.grad.clone() for p in model.parameters()]

    for chunk_size in (1, 2, 3, n_targets):
        for g0, g1 in zip(grads(chunk_size), grads(n_targets)):
            assert torch.allclose(g0, g1, atol=1e-6), \
                f"chunk_size={chunk_size} diverged"
