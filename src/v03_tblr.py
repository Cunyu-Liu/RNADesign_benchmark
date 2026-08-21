"""TBLR — Target-Balanced LambdaRank training + matched objective ablations.

Contract: docs/task_contract_v0.3.0.md §7 (TBLR), §9 Batch 3.

Ablations (per backbone, same parameters/folds/preprocessing/budget):
  rowwise_mse   legacy row-weighted pointwise MSE (score head regresses ON-OFF;
                row minibatches, no target balancing)
  tb_mse        target-balanced pointwise MSE (matched pointwise comparator)
  tb_dual       target-balanced dual ON/OFF regression (score = pred_on - pred_off)
  tb_lambdarank target-balanced LambdaRank-only (aux weight 0)
  full_tblr     LambdaRank@10 + lambda_aux * [Huber(ON)+Huber(OFF)]/2

Sampling (contract §7): one epoch = each training target sampled once in random
order; batch = 32 targets; <=64 candidates per target all in loss, >64 sampled
as 8 per each of 8 label-quantile bins, rotating across epochs (only the
target's training labels are used). Every target contributes equally to the
loss. Evaluation scores all candidates.

Model selection: 3-fold target-cluster inner CV inside each outer fold; <=12
pre-declared configs; <=100 epochs; inner-validation NDCG@10 early stopping
(patience 10, min improvement 1e-4); tuning seed 20260821; final seeds
20260821..20260825. Final runs early-stop on inner fold 0 (documented nested-CV
convention; training uses inner folds 1+2).

Outputs: predictions parquet in contract §10 schema plus a run manifest, under
/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/<run_id>/ (never overwritten).
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

PROJ = "/home/cunyuliu/ToeholdDesignBench"
MNT = "/mnt/cunyuliu/ToeholdDesignBench"
REG = f"{MNT}/runs/v0.3.0/registry_v3"
MANIFEST = f"{REG}/canonical_manifest.parquet"
SPLIT = f"{REG}/split_manifest.json"

STUDY = "canonical_v03"
TUNING_SEED = 20260821
FINAL_SEEDS = [20260821, 20260822, 20260823, 20260824, 20260825]
N_OUTER = 5
BATCH_TARGETS = 32
MAX_CAND = 64
N_QUANT_BINS = 8
PER_QUANT = 8
MAX_EPOCHS = 100
PATIENCE = 10
MIN_IMPROVE = 1e-4
LR = {"cnn60": 3e-4, "sandstorm": 1e-4, "rnaelectra": 2e-5}
WD_DEFAULT = {"cnn60": 0.01, "sandstorm": 0.0, "rnaelectra": 0.01}
RNAELECTRA_PATH = f"{MNT}/external_src/rnaelectra"
AUX_DEFAULTS = [0.1, 0.25, 0.5]  # inner-CV chooses from these for full TBLR

BASES = "ACGT"
CODE = {c: i for i, c in enumerate(BASES)}

_RNAE_TOK = None


def _rnaelectra_tokenizer():
    global _RNAE_TOK
    if _RNAE_TOK is None:
        from transformers import AutoTokenizer
        _RNAE_TOK = AutoTokenizer.from_pretrained(
            RNAELECTRA_PATH, trust_remote_code=True)
    return _RNAE_TOK


def onehot(seq, length):
    """(length, 4) one-hot; non-ACGT -> all zeros."""
    m = np.zeros((length, 4), dtype=np.float32)
    for i, ch in enumerate(str(seq)[:length].upper()):
        j = CODE.get(ch)
        if j is not None:
            m[i, j] = 1.0
    return m


def contact_map_ppm(seq):
    """SANDSTORM prototype PPM (GA_util.contact_map semantics): LxL matrix with
    complementary-pair indicator (GC=1, AU=1, GU=1 in their prototype)."""
    s = str(seq).upper()
    L = len(s)
    comp = {"A": "T", "T": "A", "C": "G", "G": "C"}
    m = np.zeros((L, L), dtype=np.float32)
    idx = {c: np.array([i for i, ch in enumerate(s) if ch == c]) for c in BASES}
    for a, b in (("G", "C"), ("A", "T"), ("G", "T")):
        ia, ib = idx[a], idx[b]
        if len(ia) and len(ib):
            m[np.ix_(ia, ib)] = 1.0
            m[np.ix_(ib, ia)] = 1.0
    return m


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------
class CNNBackbone(nn.Module):
    """Small fixed-capacity CNN over 60-nt (trigger 30 + switch 30) one-hot.

    ~fixed parameter count shared by every ablation (heads always present).
    """

    def __init__(self, dropout=0.0):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(4, 64, kernel_size=8, padding=3), nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(64, 64, kernel_size=8, padding=3), nn.ReLU(),
            nn.AdaptiveMaxPool1d(1),
        )
        self.dropout = nn.Dropout(dropout)
        self.trunk = nn.Sequential(nn.Linear(64, 32), nn.ReLU())

    def forward(self, x):  # x: (B, 4, 60)
        h = self.net(x).squeeze(-1)
        return self.trunk(self.dropout(h))


class SandstormBackbone(nn.Module):
    """PyTorch port of GA_util.create_SANDSTORM (latent_dim=64, seq_len=60,
    ppm_len=59): dual-branch CNN (one-hot + prototype PPM) -> concat -> MLP.
    """

    def __init__(self, dropout=0.0):
        super().__init__()
        # PyTorch port of GA_util.create_SANDSTORM; Keras 'same' padding pads
        # the height axis after the first stride-(4,1) conv collapses it to 1,
        # so later convs pad H symmetrically (documented port detail; the
        # identity reproduction runs the official Keras code itself).
        self.seq_branch = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=(4, 18), stride=(4, 1), padding=(0, 9)),
            nn.BatchNorm2d(16), nn.ReLU(),
            nn.Conv2d(16, 8, kernel_size=(4, 9), stride=(4, 1), padding=(2, 4)),
            nn.ReLU(),
            nn.Conv2d(8, 4, kernel_size=(4, 3), stride=(4, 1), padding=(2, 1)),
            nn.ReLU(),
        )
        self.ppm_branch = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=(9, 9), stride=(59, 1), padding=(0, 4)),
            nn.Dropout2d(0.2), nn.ReLU(),
            nn.Conv2d(16, 8, kernel_size=(5, 5), stride=(59, 1), padding=(2, 2)),
            nn.ReLU(),
            nn.Conv2d(8, 4, kernel_size=(3, 3), stride=(59, 1), padding=(1, 1)),
            nn.ReLU(),
        )
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, ppm):
        # x: (B, 1, 4, 60); ppm: (B, 1, 59, 59)
        y = self.seq_branch(x)              # (B, 4, 1, ~60)
        y = y.flatten(1)
        p = self.ppm_branch(ppm)            # (B, 4, 1, ~59)
        p = p.amax(dim=(2, 3))              # GlobalMaxPooling2D
        z = torch.cat([p, y], dim=1)
        return z

    @property
    def trunk(self):
        return None


class RNAElectraBackbone(nn.Module):
    """Official RNAElectra backbone (ModernBert, HF checkpoint) with mean
    pooling over sequence positions; k=1 nucleotide tokenizer."""

    _tok_cache = None
    _model_cache = None

    def __init__(self, dropout=0.0):
        super().__init__()
        from transformers import AutoModel, AutoTokenizer
        if RNAElectraBackbone._model_cache is None:
            RNAElectraBackbone._tok_cache = AutoTokenizer.from_pretrained(
                RNAELECTRA_PATH, trust_remote_code=True)
            RNAElectraBackbone._model_cache = AutoModel.from_pretrained(
                RNAELECTRA_PATH)
        self.tok = RNAElectraBackbone._tok_cache
        self.encoder = RNAElectraBackbone._model_cache
        self.dropout = nn.Dropout(dropout)

    def forward(self, input_ids, attention_mask):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        h = out.last_hidden_state  # (B, L, H)
        m = attention_mask.unsqueeze(-1).to(h.dtype)
        pooled = (h * m).sum(1) / m.sum(1).clamp(min=1)
        return self.dropout(pooled)


class TBLRModel(nn.Module):
    """Backbone + three heads (ranking score, ON, OFF) — identical parameter
    count across objective ablations; unused heads get loss weight 0."""

    def __init__(self, backbone, feat_in, dropout=0.0, feat_dim=32):
        super().__init__()
        self.backbone = backbone
        self.heads = nn.ModuleDict({
            "score": nn.Linear(feat_dim, 1),
            "on": nn.Linear(feat_dim, 1),
            "off": nn.Linear(feat_dim, 1),
        })
        self.feat = nn.Sequential(nn.Linear(feat_in, feat_dim), nn.ReLU())

    def forward(self, *inputs):
        z = self.backbone(*inputs)
        z = self.feat(z)
        return {k: h(z).squeeze(-1) for k, h in self.heads.items()}


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------
class TargetData:
    """Per-target candidate arrays for one label view."""

    def __init__(self, df, backbone):
        self.targets = sorted(df["target_id"].unique())
        self.fold = dict(zip(df["target_id"], df["outer_fold"]))
        self.cluster = dict(zip(df["target_id"], df["target_cluster_id"]))
        self.inner = {}
        if "inner_fold" in df.columns:
            self.inner = dict(zip(df["target_id"], df["inner_fold"]))
        self.cands = {}
        for tid, sub in df.groupby("target_id"):
            sub = sub.sort_values("record_id")
            if backbone == "rnaelectra":
                cons = [str(c) for c in sub["construct_59"]]
                enc = _rnaelectra_tokenizer()(
                    cons, padding=True, truncation=True, max_length=62,
                    return_tensors="np")
                self.cands[tid] = {
                    "input_ids": enc["input_ids"].astype(np.int64),
                    "attention_mask": enc["attention_mask"].astype(np.int64),
                    "on": sub["label_on"].astype(float).values,
                    "off": sub["label_off"].astype(float).values,
                    "onoff": (sub["label_on"] - sub["label_off"]).astype(float).values,
                    "records": sub["record_id"].values,
                }
            elif backbone == "sandstorm":
                # official SANDSTORM input: 59-nt construct
                # (switch+loop2+stem1+atg+stem2) with a prepended C -> 60 nt,
                # plus the prototype PPM of the 59-nt construct.
                cons = [str(c) for c in sub["construct_59"]]
                seqs = [onehot(c, 59) for c in cons]
                x = np.stack(seqs)  # (n, 59, 4)
                x = np.pad(x, ((0, 0), (1, 0), (0, 0)))  # prepend C -> 60nt
                ppm = np.stack([contact_map_ppm(c) for c in cons])
                self.cands[tid] = {
                    "x": x.transpose(0, 2, 1)[:, None, :, :],  # (n, 1, 4, 60)
                    "ppm": ppm[:, None, :, :],                 # (n, 1, 59, 59)
                    "on": sub["label_on"].astype(float).values,
                    "off": sub["label_off"].astype(float).values,
                    "onoff": (sub["label_on"] - sub["label_off"]).astype(float).values,
                    "records": sub["record_id"].values,
                }
            else:
                seqs = [np.concatenate([onehot(t, 30), onehot(s, 30)], axis=0)
                        for t, s in zip(sub["trigger_sequence"],
                                        sub["switch_or_construct_sequence"])]
                self.cands[tid] = {
                    "x": np.stack(seqs).transpose(0, 2, 1),  # (n, 4, 60)
                    "on": sub["label_on"].astype(float).values,
                    "off": sub["label_off"].astype(float).values,
                    "onoff": (sub["label_on"] - sub["label_off"]).astype(float).values,
                    "records": sub["record_id"].values,
                }


def load_data(backbone):
    df = pd.read_parquet(MANIFEST)
    df = df[df["eligibility_status"] == "eligible_ranking"].copy()
    with open(SPLIT) as fh:
        sm = json.load(fh)
    inner = {t: v for t, v in sm["inner_fold_of_target"].items()}
    df["inner_fold"] = df["target_id"].map(inner)
    return TargetData(df, backbone), df


# ---------------------------------------------------------------------------
# losses
# ---------------------------------------------------------------------------
def lambdarank_loss(scores, gains, k=10):
    """Pairwise LambdaRank with |Delta NDCG@k| pair weights.

    scores, gains: (n,) tensors for ONE target. Pairs with equal gains are
    skipped. DCG weights are zero beyond rank k (NDCG@k truncation).
    """
    n = scores.shape[0]
    if n < 2:
        return scores.sum() * 0.0
    g = gains
    order = torch.argsort(scores, descending=True)
    ranks = torch.empty_like(order)
    ranks[order] = torch.arange(n, device=scores.device)
    pos_w = torch.zeros(n, device=scores.device)
    top = min(k, n)
    pos_w[:top] = 1.0 / torch.log2(torch.arange(
        top, device=scores.device, dtype=torch.float32) + 2.0)
    # IDCG@k
    sorted_g = torch.sort(g, descending=True).values
    idcg = float((sorted_g[:top] * pos_w[:top]).sum())
    if idcg <= 0:
        return scores.sum() * 0.0
    gi, gj = g[:, None], g[None, :]
    wi, wj = pos_w[ranks][:, None], pos_w[ranks][None, :]
    delta = (gi - gj).abs() * (wi - wj).abs() / idcg
    mask = (gi > gj)
    if not mask.any():
        return scores.sum() * 0.0
    si, sj = scores[:, None], scores[None, :]
    logloss = F.softplus(-(si - sj))
    pair_loss = (delta * logloss * mask)
    return pair_loss.sum() / mask.sum().clamp(min=1)


def target_mean_mse(pred, onoff):
    return F.mse_loss(pred, onoff)


def huber_mean(pred, target, delta=1.0):
    return F.smooth_l1_loss(pred, target)


# ---------------------------------------------------------------------------
# training
# ---------------------------------------------------------------------------
def quantile_subsample(onoff, rng, max_cand=MAX_CAND):
    n = len(onoff)
    if n <= max_cand:
        return np.arange(n)
    # 8 quantile bins by training labels, 8 candidates each, rotating per epoch
    order = np.argsort(onoff, kind="stable")
    picks = []
    edges = np.linspace(0, n, N_QUANT_BINS + 1).astype(int)
    for b in range(N_QUANT_BINS):
        lo, hi = edges[b], edges[b + 1]
        bin_idx = order[lo:hi]
        if len(bin_idx) == 0:
            continue
        take = min(PER_QUANT, len(bin_idx))
        picks.append(rng.choice(bin_idx, size=take, replace=False))
    sel = np.concatenate(picks)
    if len(sel) > max_cand:
        sel = rng.choice(sel, size=max_cand, replace=False)
    return np.sort(sel)


def evaluate_val(model, data, val_targets, device, backbone, ablation):
    """Mean per-target tie-aware NDCG@10 on full candidate sets."""
    model.eval()
    sys.path.insert(0, f"{PROJ}/src")
    from toeholdbench.evaluator import expected_ndcg
    scores_by_target = score_targets(model, data, val_targets, device, backbone)
    vals = []
    for tid, sc in scores_by_target.items():
        c = data.cands[tid]
        score_for_ranking = ranking_score(sc, c, ablation)
        vals.append(expected_ndcg(score_for_ranking, c["onoff"], 10))
    model.train()
    return float(np.mean(vals)) if vals else 0.0


def ranking_score(head_out, cands, ablation):
    if ablation == "tb_dual":
        return head_out["on"] - head_out["off"]
    return head_out["score"]


@torch.no_grad()
def score_targets(model, data, targets, device, backbone, chunk=2048):
    """Score full candidate sets, batched ACROSS targets (identical outputs;
    one forward per chunk instead of one per target)."""
    model.eval()
    # build a flat index of (tid, row) pairs
    flat = []
    for tid in targets:
        c = data.cands[tid]
        for i in range(len(c["records"])):
            flat.append((tid, i))
    out = {tid: {k: np.zeros(len(data.cands[tid]["records"]),
                             dtype=np.float32)
                 for k in ("score", "on", "off")} for tid in targets}
    for s in range(0, len(flat), chunk):
        part = flat[s:s + chunk]
        if backbone == "sandstorm":
            x = torch.from_numpy(np.stack(
                [data.cands[t]["x"][i] for t, i in part])).to(device)
            ppm = torch.from_numpy(np.stack(
                [data.cands[t]["ppm"][i] for t, i in part])).to(device)
            h = model(x, ppm)
        elif backbone == "rnaelectra":
            ids = torch.from_numpy(np.stack(
                [data.cands[t]["input_ids"][i] for t, i in part])).to(device)
            mask = torch.from_numpy(np.stack(
                [data.cands[t]["attention_mask"][i] for t, i in part])
            ).to(device)
            h = model(ids, mask)
        else:
            x = torch.from_numpy(np.stack(
                [data.cands[t]["x"][i] for t, i in part])).to(device)
            h = model(x)
        h = {k: v.cpu().numpy() for k, v in h.items()}
        for j, (tid, i) in enumerate(part):
            for k in ("score", "on", "off"):
                out[tid][k][i] = h[k][j]
    return out


def train_one(model, data, train_targets, val_targets, cfg, device, seed,
              ablation, backbone):
    torch.manual_seed(seed)
    np.random.seed(seed % (2**31))
    rng = np.random.default_rng(seed)
    model.to(device).train()
    opt = torch.optim.AdamW(model.parameters(),
                            lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    best_val, best_state, best_epoch, bad = -1.0, None, 0, 0
    t0 = time.time()
    for epoch in range(MAX_EPOCHS):
        rng.shuffle(train_targets)
        if ablation == "rowwise_mse":
            # legacy: row-weighted minibatches over all rows
            rows = [(tid, i) for tid in train_targets
                    for i in range(len(data.cands[tid]["records"]))]
            rng.shuffle(rows)
            for s in range(0, len(rows), 2048):
                batch = rows[s:s + 2048]
                lab = np.array([data.cands[t]["onoff"][i] for t, i in batch])
                if backbone == "sandstorm":
                    x = torch.from_numpy(np.stack(
                        [data.cands[t]["x"][i] for t, i in batch])).to(device)
                    ppm = torch.from_numpy(np.stack(
                        [data.cands[t]["ppm"][i] for t, i in batch])).to(device)
                    h = model(x, ppm)
                elif backbone == "rnaelectra":
                    ids = torch.from_numpy(np.stack(
                        [data.cands[t]["input_ids"][i] for t, i in batch])
                    ).to(device)
                    mask = torch.from_numpy(np.stack(
                        [data.cands[t]["attention_mask"][i] for t, i in batch])
                    ).to(device)
                    h = model(ids, mask)
                else:
                    x = torch.from_numpy(np.stack(
                        [data.cands[t]["x"][i] for t, i in batch])).to(device)
                    h = model(x)
                loss = F.mse_loss(h["score"], torch.from_numpy(
                    lab.astype(np.float32)).to(device))
                opt.zero_grad()
                loss.backward()
                opt.step()
        else:
            for s in range(0, len(train_targets), BATCH_TARGETS):
                batch_t = train_targets[s:s + BATCH_TARGETS]
                # per-target candidate selection (quantile rotation)
                picks = []
                for tid in batch_t:
                    c = data.cands[tid]
                    sel = quantile_subsample(c["onoff"], rng)
                    picks.append((tid, sel))
                # ONE forward for the whole batch of targets (identical
                # semantics; removes per-target call overhead)
                if backbone == "sandstorm":
                    x = torch.from_numpy(np.concatenate(
                        [data.cands[t]["x"][i] for t, i in picks])).to(device)
                    ppm = torch.from_numpy(np.concatenate(
                        [data.cands[t]["ppm"][i] for t, i in picks])).to(device)
                    h_all = model(x, ppm)
                elif backbone == "rnaelectra":
                    ids = torch.from_numpy(np.concatenate(
                        [data.cands[t]["input_ids"][i] for t, i in picks])
                    ).to(device)
                    mask = torch.from_numpy(np.concatenate(
                        [data.cands[t]["attention_mask"][i] for t, i in picks])
                    ).to(device)
                    h_all = model(ids, mask)
                else:
                    x = torch.from_numpy(np.concatenate(
                        [data.cands[t]["x"][i] for t, i in picks])).to(device)
                    h_all = model(x)
                losses = []
                offset = 0
                for tid, sel in picks:
                    n = len(sel)
                    c = data.cands[tid]
                    onoff = torch.from_numpy(c["onoff"][sel].astype(
                        np.float32)).to(device)
                    on = torch.from_numpy(c["on"][sel].astype(
                        np.float32)).to(device)
                    off = torch.from_numpy(c["off"][sel].astype(
                        np.float32)).to(device)
                    h = {k: h_all[k][offset:offset + n] for k in h_all}
                    offset += n
                    if ablation == "tb_mse":
                        losses.append(target_mean_mse(h["score"], onoff))
                    elif ablation == "tb_dual":
                        losses.append((huber_mean(h["on"], on)
                                       + huber_mean(h["off"], off)) / 2)
                    elif ablation == "tb_lambdarank":
                        losses.append(lambdarank_loss(h["score"], onoff))
                    elif ablation == "full_tblr":
                        ll = lambdarank_loss(h["score"], onoff)
                        aux = (huber_mean(h["on"], on)
                               + huber_mean(h["off"], off)) / 2
                        losses.append(ll + cfg["aux_weight"] * aux)
                loss = torch.stack(losses).mean()  # equal per-target weight
                opt.zero_grad()
                loss.backward()
                opt.step()
        val = evaluate_val(model, data, val_targets, device, backbone, ablation)
        if val > best_val + MIN_IMPROVE:
            best_val, best_epoch, bad = val, epoch, 0
            best_state = {k: v.detach().clone()
                          for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= PATIENCE:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    return {"best_val_ndcg10": best_val, "best_epoch": best_epoch,
            "epochs_run": epoch + 1, "seconds": time.time() - t0}


def build_model(backbone, dropout):
    with torch.no_grad():
        if backbone == "sandstorm":
            bb = SandstormBackbone(dropout=dropout)
            z = bb(torch.zeros(1, 1, 4, 60), torch.zeros(1, 1, 59, 59))
        elif backbone == "rnaelectra":
            bb = RNAElectraBackbone(dropout=dropout)
            z = bb(torch.zeros(1, 8, dtype=torch.long),
                   torch.ones(1, 8, dtype=torch.long))
        else:
            bb = CNNBackbone(dropout=dropout)
            z = bb(torch.zeros(1, 4, 60))
    return TBLRModel(bb, feat_in=int(z.shape[1]), dropout=dropout, feat_dim=32)


# ---------------------------------------------------------------------------
# prediction emission
# ---------------------------------------------------------------------------
def emit_predictions(model, data, targets, device, backbone, ablation,
                     method_id, seed, run_id, fold, out_path):
    scores = score_targets(model, data, targets, device, backbone)
    rows = []
    for tid, heads in scores.items():
        c = data.cands[tid]
        sc = ranking_score(heads, c, ablation)
        for i, rec in enumerate(c["records"]):
            rows.append({
                "run_id": run_id,
                "track_id": STUDY,
                "fold": fold,
                "target_id": tid,
                "target_cluster_id": data.cluster[tid],
                "record_id": rec,
                "method_id": method_id,
                "seed": seed,
                "score": float(sc[i]),
                "predicted_on": float(heads["on"][i]),
                "predicted_off": float(heads["off"][i]),
            })
    pd.DataFrame(rows).to_parquet(out_path, index=False)
    return len(rows)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backbone", choices=["cnn60", "sandstorm", "rnaelectra"],
                    required=True)
    ap.add_argument("--ablation", choices=["rowwise_mse", "tb_mse", "tb_dual",
                                           "tb_lambdarank", "full_tblr"],
                    required=True)
    ap.add_argument("--outer-fold", type=int, required=True)
    ap.add_argument("--seed", type=int, default=TUNING_SEED)
    ap.add_argument("--lr-mult", type=float, default=1.0)
    ap.add_argument("--weight-decay", default="default")
    ap.add_argument("--aux-weight", type=float, default=0.25)
    ap.add_argument("--dropout", type=float, default=None)
    ap.add_argument("--mode", choices=["final", "tune-inner"], default="final")
    ap.add_argument("--inner-fold", type=int, default=0)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()

    out_dir = f"{MNT}/runs/v0.3.0/{args.run_id}"
    if os.path.exists(out_dir):
        print(f"REFUSING to overwrite {out_dir}")
        sys.exit(2)
    os.makedirs(out_dir)
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        print("FATAL: CUDA requested but unavailable (contract: no silent CPU "
              "fallback)")
        sys.exit(3)

    data, df = load_data(args.backbone)
    all_targets = sorted(data.cands.keys())

    lr = LR[args.backbone] * args.lr_mult
    wd = WD_DEFAULT[args.backbone] if args.weight_decay == "default" \
        else float(args.weight_decay)
    dropout = args.dropout if args.dropout is not None else 0.0
    cfg = {"lr": lr, "weight_decay": wd, "aux_weight": args.aux_weight,
           "dropout": dropout}

    train_pool = [t for t in all_targets if data.fold[t] != args.outer_fold]
    test_targets = [t for t in all_targets if data.fold[t] == args.outer_fold]

    if args.mode == "tune-inner":
        val_targets = [t for t in train_pool
                       if data.inner.get(t) == args.inner_fold]
        train_targets = [t for t in train_pool
                         if data.inner.get(t) != args.inner_fold]
    else:
        # final: early-stop on inner fold 0, train on inner folds 1+2
        val_targets = [t for t in train_pool if data.inner.get(t) == 0]
        train_targets = [t for t in train_pool if data.inner.get(t) != 0]

    model = build_model(args.backbone, dropout)
    n_params = sum(p.numel() for p in model.parameters())
    info = train_one(model, data, train_targets, val_targets, cfg, device,
                     args.seed, args.ablation, args.backbone)
    info.update({"backbone": args.backbone, "ablation": args.ablation,
                 "outer_fold": args.outer_fold, "mode": args.mode,
                 "inner_fold": args.inner_fold, "seed": args.seed,
                 "config": cfg, "n_params": n_params,
                 "n_train_targets": len(train_targets),
                 "n_val_targets": len(val_targets),
                 "n_test_targets": len(test_targets)})

    method_id = f"{args.backbone}/{args.ablation}"
    if args.mode == "final":
        n = emit_predictions(model, data, test_targets, device, args.backbone,
                             args.ablation, method_id, args.seed, args.run_id,
                             args.outer_fold, f"{out_dir}/predictions.parquet")
        info["n_predictions"] = n
    with open(f"{out_dir}/run_manifest.json", "w") as fh:
        json.dump(info, fh, indent=2)
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
