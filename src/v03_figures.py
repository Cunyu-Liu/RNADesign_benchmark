"""Generate the three v0.3.0 paper figures + source-data CSVs (contract §9
Batch 4: manuscript with figures; every panel traces to run artifacts).

Fig 1  objective comparison across backbones (two-backbone TBLR negative
       result) -- grouped bars + analytic random baseline.
Fig 2  architecture-shift transfer -- (A) VISTA mCherry NDCG@10 with
       site-bootstrap CIs; (B) crowdsourced Spearman with cluster-bootstrap
       CIs.
Fig 3  contamination & input masking -- (A) controlled leakage arms;
       (B) BEACON fixed-capacity masking variants.

Outputs: /mnt/.../runs/v0.3.0/paper_figs/ (PNG 300dpi + source_data CSVs)
plus a copy list for outputs/ assembly.
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

BASE = "/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0"
OUT = f"{BASE}/paper_figs"
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({"font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False})

OBJ_ORDER = ["rowwise_mse", "tb_mse", "tb_dual", "tb_lambdarank",
             "full_tblr"]
OBJ_LABEL = {"rowwise_mse": "rowwise\n(legacy)", "tb_mse": "pointwise\n(tb_mse)",
             "tb_dual": "dual\nON/OFF", "tb_lambdarank": "LambdaRank\nonly",
             "full_tblr": "full TBLR"}


def fig1_objectives():
    fig, ax = plt.subplots(figsize=(6.2, 3.4))
    xs = np.arange(len(OBJ_ORDER))
    families = sorted(
        d.replace("eval_", "").replace("_family", "")
        for d in os.listdir(BASE)
        if d.startswith("eval_") and d.endswith("_family")
        and os.path.exists(f"{BASE}/{d}/method_summary.csv"))
    tags = {"cnn60": "CNN", "sandstorm": "SANDSTORM",
            "rnaelectra": "RNAElectra"}
    colors = {"cnn60": "#4878A8", "sandstorm": "#D9822B",
              "rnaelectra": "#5B9E5B"}
    w = 0.8 / len(families)
    src = []
    for i, bb in enumerate(families):
        tag, color = tags.get(bb, bb), colors.get(bb, "#888888")
        ms = pd.read_csv(f"{BASE}/eval_{bb}_family/method_summary.csv")
        ms = ms.set_index("method_id")
        vals = [ms.loc[f"{bb}/{o}", "ndcg@10"] for o in OBJ_ORDER]
        rnd = ms.loc[f"{bb}/rowwise_mse", "random_ndcg@10"]
        off = (i - (len(families) - 1) / 2) * w
        ax.bar(xs + off, vals, w, label=f"{tag} backbone",
               color=color, edgecolor="black", linewidth=0.4)
        for x, v in zip(xs + off, vals):
            ax.text(x, v + 0.004, f"{v:.3f}", ha="center",
                    fontsize=7 if len(families) < 3 else 6)
        src.append(pd.DataFrame(
            {"backbone": bb, "objective": OBJ_ORDER,
             "ndcg@10": vals, "random_ndcg@10": rnd}))
    ax.axhline(rnd, ls="--", c="gray", lw=1,
               label=f"analytic random ({rnd:.3f})")
    ax.set_xticks(xs)
    ax.set_xticklabels([OBJ_LABEL[o] for o in OBJ_ORDER])
    ax.set_ylabel("NDCG@10 (mean over 917 targets)")
    ax.set_ylim(0.60, 0.87)
    ax.legend(frameon=False, loc="lower left", fontsize=8)
    ax.set_title("Objective comparison: TBLR underperforms matched pointwise "
                 f"on all {len(families)} completed backbones", fontsize=9)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig1_objectives.png", dpi=300)
    plt.close(fig)
    pd.concat(src).to_csv(f"{OUT}/fig1_source_data.csv", index=False)


def fig2_transfer():
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.6))
    # panel A: mCherry
    import glob as _g
    vdir = sorted(d for d in os.listdir(BASE)
                  if d.startswith("vista_external_"))[-1]
    vr = json.load(open(f"{BASE}/{vdir}/vista_external_results.json"))
    rows = sorted(vr["onoff_full"], key=lambda r: -r["ndcg@10"])
    names = [r["method"] for r in rows]
    vals = [r["ndcg@10"] for r in rows]
    los = [r["ci_low"] for r in rows]
    his = [r["ci_high"] for r in rows]
    rnd = rows[0]["random_ndcg@10"]
    y = np.arange(len(rows))
    colors = ["#2B7A3D" if "plsda" in n else
              ("#A84040" if "transfer" in n else "#7A7A7A")
              for n in names]
    axes[0].barh(y, vals, xerr=[np.array(vals) - np.array(los),
                                np.array(his) - np.array(vals)],
                 color=colors, edgecolor="black", linewidth=0.4,
                 error_kw=dict(lw=0.8, capsize=2))
    axes[0].axvline(rnd, ls="--", c="gray", lw=1)
    axes[0].text(rnd + 0.01, len(rows) - 0.4, f"random {rnd:.3f}",
                 fontsize=7, color="gray")
    axes[0].set_yticks(y)
    axes[0].set_yticklabels([n.replace("/full_tblr", "")
                             for n in names], fontsize=7)
    axes[0].set_xlabel("NDCG@10 (ON/OFF Full)")
    axes[0].set_title("(A) VISTA mCherry: single target,\n"
                      "site-level bootstrap CIs", fontsize=8)
    axes[0].invert_yaxis()
    pd.DataFrame({"method": names, "ndcg@10": vals, "ci_low": los,
                  "ci_high": his,
                  "random_ndcg@10": rnd}).to_csv(
        f"{OUT}/fig2a_source_data.csv", index=False)
    # panel B: crowdsourced
    cdir = sorted(d for d in os.listdir(BASE)
                  if d.startswith("crowd_external_"))[-1]
    cs = pd.read_csv(f"{BASE}/{cdir}/spearman_summary.csv")
    cs = cs.sort_values("spearman")
    labels = [f"{r['method_id'].replace('transfer-', '')} "
              f"{r['prediction']} vs {r['outcome']}"
              for _, r in cs.iterrows()]
    y = np.arange(len(cs))
    err = np.array([cs["spearman"] - cs["cluster_boot_lo"],
                    cs["cluster_boot_hi"] - cs["spearman"]])
    colors = ["#2B7A3D" if "sandstorm" in l else "#A84040" for l in labels]
    axes[1].barh(y, cs["spearman"], xerr=err, color=colors,
                 edgecolor="black", linewidth=0.4,
                 error_kw=dict(lw=0.8, capsize=2))
    axes[1].axvline(0, c="black", lw=0.8)
    axes[1].set_yticks(y)
    axes[1].set_yticklabels(labels, fontsize=7)
    axes[1].set_xlabel("Spearman rho (native outcomes)")
    axes[1].set_title("(B) Crowdsourced 100 regulators:\n"
                      "architecture-cluster bootstrap CIs", fontsize=8)
    cs.to_csv(f"{OUT}/fig2b_source_data.csv", index=False)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig2_transfer.png", dpi=300)
    plt.close(fig)


def fig3_contamination():
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 3.2))
    # panel A: leakage
    lman = None
    import glob as _g
    for d in reversed(sorted(_g.glob(f"{BASE}/leakage_*"))):
        for f in os.listdir(d):
            if f.endswith(".json") and "manifest" not in f:
                lman = json.load(open(f"{d}/{f}"))
                break
        if lman:
            break
    s = lman["summary"]
    axes[0].bar([0, 1], [s["mean_ndcg_clean"], s["mean_ndcg_leaky"]],
                color=["#4878A8", "#A84040"], edgecolor="black",
                linewidth=0.4, width=0.55)
    axes[0].set_xticks([0, 1])
    axes[0].set_xticklabels(["clean\n(cluster-disjoint)",
                             "leaky\n(same-target)"])
    axes[0].set_ylim(0.80, 0.91)
    for x, v in enumerate([s["mean_ndcg_clean"], s["mean_ndcg_leaky"]]):
        axes[0].text(x, v + 0.0015, f"{v:.4f}", ha="center", fontsize=8)
    axes[0].annotate(f"paired diff\n+{s['mean_paired_diff']:.4f}",
                     xy=(0.5, 0.885), ha="center", fontsize=8,
                     arrowprops=dict(arrowstyle="->", lw=0.8))
    axes[0].set_ylabel("NDCG@10 (156 targets, 5 seeds)")
    axes[0].set_title("(A) Controlled same-target\ncontamination experiment",
                      fontsize=8)
    pd.DataFrame([{"arm": k, "value": v} for k, v in s.items() if
                  k.startswith("mean")]).to_csv(
        f"{OUT}/fig3a_source_data.csv", index=False)
    # panel B: BEACON masking
    ms = pd.read_csv(f"{BASE}/eval_beacon_masks_f0/method_summary.csv")
    ms = ms.set_index(ms.columns[0])
    variants = ["full_construct", "trigger_only", "trigger_and_rc",
                "segment_shuffle", "template_var", "rc_copy_only",
                "scaffold_only"]
    labels = ["full\nconstruct", "trigger\nonly", "trigger\n+RC",
              "segment\nshuffle", "template\nvar", "RC-copy\nonly",
              "scaffold\nonly"]
    vals, rns = [], []
    for v in variants:
        key = f"beacon-mask/{v}"
        if key in ms.index:
            vals.append(float(ms.loc[key].iloc[2]))
            rns.append(float(ms.loc[key].iloc[3]))
        else:
            vals.append(np.nan)
            rns.append(np.nan)
    xs = np.arange(len(variants))
    axes[1].bar(xs, vals, color="#6A5A9E", edgecolor="black",
                linewidth=0.4)
    axes[1].axhline(rns[0], ls="--", c="gray", lw=1,
                    label=f"random ({rns[0]:.3f})")
    axes[1].set_xticks(xs)
    axes[1].set_xticklabels(labels, fontsize=7)
    axes[1].set_ylim(0.60, 0.80)
    axes[1].set_ylabel("NDCG@10 (fold 0)")
    axes[1].legend(frameon=False, fontsize=8)
    axes[1].set_title("(B) BEACON fixed-capacity\ninput masking",
                      fontsize=8)
    pd.DataFrame({"variant": variants, "ndcg@10": vals,
                  "random_ndcg@10": rns}).to_csv(
        f"{OUT}/fig3b_source_data.csv", index=False)
    fig.tight_layout()
    fig.savefig(f"{OUT}/fig3_contamination.png", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    fig1_objectives()
    print("fig1 done")
    fig2_transfer()
    print("fig2 done")
    fig3_contamination()
    print("fig3 done")
    print("outputs:", OUT)
