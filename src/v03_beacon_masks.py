"""BEACON fixed-capacity 148-nt segment-masking ablations (contract §3).

One fixed-capacity 148-position model; seven input-regime variants identical
in architecture, parameters, folds, candidate sets, and training budget:

  trigger_only    positions [3:33]  (the frozen correct trigger slice)
  rc_copy_only    positions [53:83] (reverse-complement trigger copy)
  trigger_and_rc  [3:33] + [53:83]
  scaffold_only   everything except [3:33] and [53:83]
  template_var    positions that vary across the authoritative 91,534
                  constructs (the template's variable positions)
  full_construct  all 148 positions
  segment_shuffle full construct with the five natural segments
                  ([0:3],[3:33],[33:53],[53:83],[83:148]) permuted by a
                  fixed seed-frozen permutation, identical at train and eval

Training: cnn148 backbone (fixed capacity), target-balanced MSE on ON-OFF
(score head; ON/OFF heads present with zero loss weight for parameter
parity), inner-fold-0 early stopping on validation NDCG@10, seed-frozen.

Track: BEACON label view (mapping_status=unique, eligible targets), our
cluster folds. Emits predictions in contract §10 schema per variant.
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

PROJ = "/home/cunyuliu/ToeholdDesignBench"
MNT = "/mnt/cunyuliu/ToeholdDesignBench"
REG = f"{MNT}/runs/v0.3.0/registry_v3"
sys.path.insert(0, f"{PROJ}/src")
import v03_tblr as vr  # noqa: E402
from toeholdbench.evaluator import expected_ndcg  # noqa: E402

LEN = 148
SEGMENTS = [(0, 3), (3, 33), (33, 53), (53, 83), (83, 148)]
SEED = 20260821
SEEDS = [20260821, 20260822, 20260823, 20260824, 20260825]
MAX_EPOCHS = 60
PATIENCE = 8


def variant_masks(constructs):
    """Return dict variant -> boolean mask (length 148) of VISIBLE positions."""
    arr = np.stack([[c for c in str(s).upper()] for s in constructs])
    variable = (arr != arr[0]).any(axis=0)  # positions varying across rows
    m = {v: np.zeros(LEN, dtype=bool) for v in
         ("trigger_only", "rc_copy_only", "trigger_and_rc", "scaffold_only",
          "template_var", "full_construct")}
    m["trigger_only"][3:33] = True
    m["rc_copy_only"][53:83] = True
    m["trigger_and_rc"][3:33] = True
    m["trigger_and_rc"][53:83] = True
    m["scaffold_only"][:] = True
    m["scaffold_only"][3:33] = False
    m["scaffold_only"][53:83] = False
    m["template_var"] = variable
    m["full_construct"][:] = True
    return m, variable


class CNN148(nn.Module):
    """Fixed-capacity 148-position CNN with 3 heads (parameter parity)."""

    def __init__(self, dropout=0.0):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(5, 64, kernel_size=8, padding=3), nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(64, 64, kernel_size=8, padding=3), nn.ReLU(),
            nn.AdaptiveMaxPool1d(1))
        self.dropout = nn.Dropout(dropout)
        self.trunk = nn.Sequential(nn.Linear(64, 32), nn.ReLU())
        self.heads = nn.ModuleDict({
            "score": nn.Linear(32, 1), "on": nn.Linear(32, 1),
            "off": nn.Linear(32, 1)})

    def forward(self, x, msk):  # x: (B,4,148), msk: (B,1,148)
        z = torch.cat([x * msk, msk], dim=1)  # (B,5,148)
        h = self.net(z).squeeze(-1)
        h = self.trunk(self.dropout(h))
        return {k: hd(h).squeeze(-1) for k, hd in self.heads.items()}


def encode_constructs(constructs, mask, shuffle=False):
    X = np.zeros((len(constructs), LEN, 4), dtype=np.float32)
    M = np.zeros((len(constructs), LEN), dtype=np.float32)
    code = {"A": 0, "C": 1, "G": 2, "T": 3}
    for i, s in enumerate(constructs):
        s = str(s).upper()
        for j, ch in enumerate(s[:LEN]):
            k = code.get(ch)
            if k is not None:
                X[i, j, k] = 1.0
            M[i, j] = 1.0
    if shuffle:
        rng = np.random.default_rng(SEED)
        perm = rng.permutation(len(SEGMENTS))
        X2 = np.zeros_like(X)
        M2 = np.zeros_like(M)
        pos = 0
        for p in perm:
            a, b = SEGMENTS[p]
            L = b - a
            X2[:, pos:pos + L] = X[:, a:b]
            M2[:, pos:pos + L] = M[:, a:b]
            pos += L
        X, M = X2, M2
    M = M * mask[None, :]
    return X.transpose(0, 2, 1), M[:, None, :]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--outer-fold", type=int, default=0)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()

    out_dir = f"{MNT}/runs/v0.3.0/{args.run_id}"
    if os.path.exists(out_dir):
        sys.exit(2)
    os.makedirs(out_dir)
    device = torch.device(args.device)
    if not torch.cuda.is_available():
        print("FATAL: CUDA unavailable")
        sys.exit(3)

    df = pd.read_parquet(f"{REG}/beacon_manifest.parquet")
    df = df[(df["mapping_status"] == "unique")
            & (df["eligibility_status"] == "eligible_ranking")].copy()
    with open(f"{REG}/split_manifest.json") as fh:
        sm = json.load(fh)
    df["inner_fold"] = df["target_id"].map(sm["inner_fold_of_target"])
    print(f"BEACON eligible unique rows: {len(df)}, "
          f"targets: {df['target_id'].nunique()}")

    masks, variable = variant_masks(df["switch_or_construct_sequence"])
    print(f"template variable positions: {int(variable.sum())}/148")

    # per-target arrays (encode once for this variant)
    cands = {}
    for tid, sub in df.groupby("target_id"):
        sub = sub.sort_values("record_id")
        X, M = encode_constructs(sub["switch_or_construct_sequence"],
                                 masks[args.variant],
                                 shuffle=args.variant == "segment_shuffle")
        cands[tid] = {"x": X, "m": M,
                      "on": sub["label_on"].astype(float).values,
                      "off": sub["label_off"].astype(float).values,
                      "onoff": (sub["label_on"] - sub["label_off"]
                                ).astype(float).values,
                      "records": sub["record_id"].values,
                      "fold": sub["outer_fold"].iloc[0],
                      "inner": sub["inner_fold"].iloc[0],
                      "cluster": sub["target_cluster_id"].iloc[0]}
    targets = sorted(cands)
    train_pool = [t for t in targets if cands[t]["fold"] != args.outer_fold]
    val_targets = [t for t in train_pool if cands[t]["inner"] == 0]
    train_targets = [t for t in train_pool if cands[t]["inner"] != 0]
    test_targets = [t for t in targets if cands[t]["fold"] == args.outer_fold]

    torch.manual_seed(args.seed)
    model = CNN148().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.01)
    rng = np.random.default_rng(args.seed)
    best_val, best_state, bad = -1.0, None, 0
    t0 = time.time()
    for epoch in range(MAX_EPOCHS):
        model.train()
        rng.shuffle(train_targets)
        for s in range(0, len(train_targets), vr.BATCH_TARGETS):
            batch_t = train_targets[s:s + vr.BATCH_TARGETS]
            picks = [(t, vr.quantile_subsample(cands[t]["onoff"], rng))
                     for t in batch_t]
            x = torch.from_numpy(np.concatenate(
                [cands[t]["x"][i] for t, i in picks])).to(device)
            m = torch.from_numpy(np.concatenate(
                [cands[t]["m"][i] for t, i in picks])).to(device)
            y = torch.from_numpy(np.concatenate(
                [cands[t]["onoff"][i].astype(np.float32)
                 for t, i in picks])).to(device)
            h = model(x, m)
            # equal per-target weight: mean of per-target means
            losses = []
            off0 = 0
            for t, i in picks:
                n = len(i)
                losses.append(torch.nn.functional.mse_loss(
                    h["score"][off0:off0 + n], y[off0:off0 + n]))
                off0 += n
            loss = torch.stack(losses).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
        # validation NDCG@10
        model.eval()
        vals = []
        with torch.no_grad():
            for t in val_targets:
                c = cands[t]
                sc = model(torch.from_numpy(c["x"]).to(device),
                           torch.from_numpy(c["m"]).to(device))["score"]
                vals.append(expected_ndcg(sc.cpu().numpy(), c["onoff"], 10))
        val = float(np.mean(vals))
        if val > best_val + 1e-4:
            best_val, bad = val, 0
            best_state = {k: v.detach().clone()
                          for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= PATIENCE:
                break
    if best_state:
        model.load_state_dict(best_state)

    # emit test predictions
    model.eval()
    rows = []
    with torch.no_grad():
        for t in test_targets:
            c = cands[t]
            sc = model(torch.from_numpy(c["x"]).to(device),
                       torch.from_numpy(c["m"]).to(device))["score"].cpu().numpy()
            for i, rec in enumerate(c["records"]):
                rows.append({
                    "run_id": args.run_id, "track_id": "beacon_v03",
                    "fold": args.outer_fold, "target_id": t,
                    "target_cluster_id": c["cluster"], "record_id": rec,
                    "method_id": f"beacon-mask/{args.variant}",
                    "seed": args.seed, "score": float(sc[i])})
    pd.DataFrame(rows).to_parquet(f"{out_dir}/predictions.parquet", index=False)
    info = {"variant": args.variant, "outer_fold": args.outer_fold,
            "seed": args.seed, "best_val_ndcg10": best_val,
            "epochs_run": epoch + 1, "seconds": time.time() - t0,
            "n_params": sum(p.numel() for p in model.parameters()),
            "visible_positions": int(masks[args.variant].sum()),
            "n_test_predictions": len(rows)}
    with open(f"{out_dir}/run_manifest.json", "w") as fh:
        json.dump(info, fh, indent=2)
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
