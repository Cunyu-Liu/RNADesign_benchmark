"""Create manuscript tables and provisional publication figures from v0.2 outputs.

This module never substitutes historical results or placeholder values.  It fails
when any required v0.2 result is absent or internally inconsistent.  Figures are
general manuscript figures because the target journal and submission phase have
not yet been selected; journal-specific export checks remain a submission task.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path


METHOD_LABELS = {
    "B0_random": "Random",
    "B0_gc": "GC rule",
    "B1_thermo": "Thermodynamic proxy",
    "B2_mlp": "MLP",
    "B2_cnn": "CNN",
    "B3_deep": "Deeper CNN proxy",
    "B4_struct": "Sequence + local biophysics",
    "B5_structrank": "Longer-trained local proxy",
    "random": "Random",
    "gc_full": "Full-sequence GC",
    "mlp30": "MLP (first 30 nt)",
    "cnn30": "CNN (first 30 nt)",
    "mlp148": "MLP (148 nt)",
    "fused_mlp_first30": "Fused MLP (first 30 nt)",
    "fused_mlp_last30": "Fused MLP (last 30 nt)",
    "tsgen2": "tsgen2 rank",
    "gc_first30": "GC (first 30 nt)",
}

COLORS = {
    "rule": "#000000",
    "thermo": "#D55E00",
    "sequence": "#0072B2",
    "local": "#009E73",
    "other": "#CC79A7",
}
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "h"]


def method_style(method: str, index: int) -> tuple[str, str]:
    if method in {"B0_random", "B0_gc", "random", "gc_full", "gc_first30"}:
        color = COLORS["rule"]
    elif method in {"B1_thermo", "tsgen2"}:
        color = COLORS["thermo"]
    elif method in {"B2_mlp", "B2_cnn", "B3_deep", "mlp30", "cnn30", "mlp148",
                    "fused_mlp_first30", "fused_mlp_last30"}:
        color = COLORS["sequence"]
    elif method in {"B4_struct", "B5_structrank"}:
        color = COLORS["local"]
    else:
        color = COLORS["other"]
    return color, MARKERS[index % len(MARKERS)]


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"required v0.2 result is missing: {path}")
    with path.open() as handle:
        value = json.load(handle)
    if value.get("version") != "0.2":
        raise ValueError(f"expected v0.2 result in {path}, got {value.get('version')!r}")
    return value


def load_bundle(processed: Path) -> dict:
    paths = {
        "p3": processed / "p3_baselines_v02.json",
        "canonical": processed / "revision_analysis_v02.json",
        "beacon": processed / "beacon_target_benchmark_v02.json",
        "vista": processed / "vista_paired_context_v02.json",
    }
    bundle = {name: read_json(path) for name, path in paths.items()}

    seeds = bundle["p3"].get("seed_policy", {}).get("learned_models")
    if seeds != [0, 1, 2, 3, 4]:
        raise ValueError(f"canonical learned-model seed policy is not frozen at 0-4: {seeds!r}")
    if "signed canonical ON minus OFF" not in bundle["p3"].get("label_semantics", ""):
        raise ValueError("canonical result does not declare signed ON-minus-OFF semantics")
    for track_name, track in bundle["beacon"].get("tracks", {}).items():
        if track.get("target_overlap") != 0:
            raise ValueError(f"BEACON track {track_name} has nonzero target overlap")
    if bundle["vista"].get("scope") != "single_target_single_study_paired_context_stress_test":
        raise ValueError("VISTA result lacks the frozen single-target scope declaration")
    return {"paths": paths, **bundle}


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict]) -> str:
    headers = list(rows[0])
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(str(row[h]) for h in headers) + " |" for row in rows)
    return "\n".join(lines) + "\n"


def write_markdown(path: Path, title: str, note: str, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {title}\n\n{note}\n\n{markdown_table(rows)}")


def fmt_interval(metric: dict) -> str:
    mean = metric["mean"]
    lo, hi = metric["ci95"]
    return f"{mean:.3f} [{lo:.3f}, {hi:.3f}]"


def canonical_rows(bundle: dict) -> list[dict]:
    methods = bundle["canonical"]["E1_objective_alignment"]["methods"]
    rows = []
    for method, result in methods.items():
        rows.append({
            "Method": METHOD_LABELS.get(method, method),
            "Pooled Spearman": f"{result['pooled_prediction_spearman']:.3f}",
            "Success@1 (95% CI)": fmt_interval(result["success_at_1"]),
            "Success@3 (95% CI)": fmt_interval(result["success_at_3"]),
            "NDCG@10 (95% CI)": fmt_interval(result["ndcg_at_10"]),
            "Regret@10 (95% CI)": fmt_interval(result["normalized_regret_at_10"]),
            "Pareto coverage@10 (95% CI)": fmt_interval(
                result["pareto_front_coverage_at_10"]
            ),
        })
    return rows


def canonical_pairwise_rows(bundle: dict) -> list[dict]:
    paired = bundle["canonical"]["E1_objective_alignment"]["paired_vs_random"]
    rows = []
    for method, metrics in paired.items():
        for metric_name, result in metrics.items():
            rows.append({
                "Method": METHOD_LABELS.get(method, method),
                "Metric": metric_name,
                "Mean difference": f"{result['mean_difference']:.3f}",
                "95% CI": f"[{result['ci95'][0]:.3f}, {result['ci95'][1]:.3f}]",
                "Bootstrap P": f"{result['two_sided_bootstrap_p']:.4f}",
                "Targets": result["n_targets"],
            })
    return rows


def beacon_rows(bundle: dict) -> list[dict]:
    rows = []
    for track_name, track in bundle["beacon"]["tracks"].items():
        for method, result in track["methods"].items():
            rows.append({
                "Track": track_name,
                "Method": METHOD_LABELS.get(method, method),
                "Test targets": track["n_test_targets"],
                "Target overlap": track["target_overlap"],
                "Mean target Spearman (95% CI)": fmt_interval(result["target_spearman"]),
                "NDCG@10 (95% CI)": fmt_interval(result["ndcg_at_10"]),
                "Regret@10 (95% CI)": fmt_interval(result["normalized_regret_at_10"]),
            })
    return rows


def vista_rows(bundle: dict) -> list[dict]:
    rows = []
    for method, result in bundle["vista"]["methods"].items():
        difference = result["paired_context_difference"]
        rows.append({
            "Method": METHOD_LABELS.get(method, method),
            "Spearman: truncated": f"{result['spearman_with_truncated']:.3f}",
            "Spearman: full": f"{result['spearman_with_full']:.3f}",
            "Full − truncated": f"{difference['full_minus_truncated_spearman']:.3f}",
            "Site-bootstrap 95% CI": (
                f"[{difference['site_bootstrap_ci95'][0]:.3f}, "
                f"{difference['site_bootstrap_ci95'][1]:.3f}]"
            ),
            "Top-10 overlap: truncated": f"{result['top10_overlap_with_truncated_oracle']:.3f}",
            "Top-10 overlap: full": f"{result['top10_overlap_with_full_oracle']:.3f}",
        })
    return rows


def configure_matplotlib(cache_dir: Path):
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))
    cache_dir.mkdir(parents=True, exist_ok=True)
    import matplotlib

    matplotlib.use("Agg")
    matplotlib.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 9,
        "legend.fontsize": 7,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "savefig.facecolor": "white",
        "figure.facecolor": "white",
    })
    import matplotlib.pyplot as plt

    return plt


def save_figure(fig, base: Path) -> None:
    base.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(base.with_suffix(".pdf"), facecolor="white")
    png_path = base.with_suffix(".png")
    fig.savefig(png_path, dpi=600, facecolor="white", transparent=False)
    # Matplotlib PNG output may retain an alpha channel even with an opaque
    # figure patch.  Flatten explicitly to RGB so downstream layout software
    # cannot blend the figure against an unintended background.
    from PIL import Image

    with Image.open(png_path) as source:
        if source.mode == "RGBA":
            background = Image.new("RGB", source.size, "white")
            background.paste(source, mask=source.getchannel("A"))
            background.save(png_path, dpi=(600, 600))
        elif source.mode != "RGB":
            source.convert("RGB").save(png_path, dpi=(600, 600))


def figure_objective_alignment(bundle: dict, figure_dir: Path, plt) -> dict:
    methods = bundle["canonical"]["E1_objective_alignment"]["methods"]
    rows = []
    for method, result in methods.items():
        ndcg = result["ndcg_at_10"]
        rows.append({
            "method": method,
            "label": METHOD_LABELS.get(method, method),
            "pooled_spearman": result["pooled_prediction_spearman"],
            "ndcg_at_10_mean": ndcg["mean"],
            "ndcg_at_10_ci_low": ndcg["ci95"][0],
            "ndcg_at_10_ci_high": ndcg["ci95"][1],
            "n_targets": ndcg["n_targets"],
        })
    write_csv(figure_dir / "figure_1_source_data.csv", rows)

    fig, ax = plt.subplots(figsize=(180 / 25.4, 110 / 25.4), layout="constrained")
    for index, row in enumerate(rows):
        color, marker = method_style(row["method"], index)
        yerr = [[row["ndcg_at_10_mean"] - row["ndcg_at_10_ci_low"]],
                [row["ndcg_at_10_ci_high"] - row["ndcg_at_10_mean"]]]
        ax.errorbar(
            row["pooled_spearman"], row["ndcg_at_10_mean"], yerr=yerr,
            fmt=marker, color=color, markerfacecolor="white", markeredgewidth=1.2,
            capsize=2, linewidth=1, markersize=5, label=row["label"],
        )
    ax.axvline(0, color="#777777", linewidth=0.7, linestyle="--")
    ax.set(
        xlim=(-1, 1), ylim=(0, 1),
        xlabel="Pooled prediction Spearman ρ",
        ylabel="Mean target NDCG@10 (95% target-bootstrap CI)",
        title="Prediction and target NDCG align across the evaluated methods",
    )
    ax.grid(axis="y", color="#DDDDDD", linewidth=0.5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, frameon=False)
    save_figure(fig, figure_dir / "figure_1_objective_alignment")
    plt.close(fig)
    alt = (
        "Scatter plot showing that pooled prediction Spearman correlation and mean target NDCG "
        "at 10 order the evaluated canonical methods similarly. Vertical intervals are 95% "
        "target-bootstrap confidence "
        "intervals; marker and color combinations identify methods in the legend. Both axes show "
        "their full bounded ranges."
    )
    (figure_dir / "figure_1_alt_text.txt").write_text(alt + "\n")
    return {"id": "figure_1", "source_data": "figure_1_source_data.csv", "alt_text": alt}


def figure_beacon(bundle: dict, figure_dir: Path, plt) -> dict:
    rows = []
    tracks = bundle["beacon"]["tracks"]
    for track_name, track in tracks.items():
        for method, result in track["methods"].items():
            metric = result["ndcg_at_10"]
            rows.append({
                "track": track_name,
                "method": method,
                "label": METHOD_LABELS.get(method, method),
                "mean": metric["mean"],
                "ci_low": metric["ci95"][0],
                "ci_high": metric["ci95"][1],
                "n_targets": metric["n_targets"],
            })
    write_csv(figure_dir / "figure_2_source_data.csv", rows)

    track_names = list(tracks)
    fig, axes = plt.subplots(
        1, len(track_names), figsize=(180 / 25.4, 92 / 25.4),
        sharex=True, layout="constrained",
    )
    if len(track_names) == 1:
        axes = [axes]
    for ax, track_name in zip(axes, track_names):
        selected = [row for row in rows if row["track"] == track_name]
        for index, row in enumerate(selected):
            color, marker = method_style(row["method"], index)
            xerr = [[row["mean"] - row["ci_low"]], [row["ci_high"] - row["mean"]]]
            ax.errorbar(
                row["mean"], index, xerr=xerr, fmt=marker, color=color,
                markerfacecolor="white", markeredgewidth=1.2, capsize=2,
                linewidth=1, markersize=5,
            )
        ax.set_yticks(range(len(selected)), [row["label"] for row in selected])
        ax.set(xlim=(0, 1), xlabel="Mean target NDCG@10", title=track_name.replace("_", " "))
        ax.grid(axis="x", color="#DDDDDD", linewidth=0.5)
        ax.invert_yaxis()
    fig.suptitle("BEACON ranking under source-disjoint and domain-OOD evaluation", fontsize=9)
    save_figure(fig, figure_dir / "figure_2_beacon_tracks")
    plt.close(fig)
    alt = (
        "Two-panel point-range plot of BEACON mean target NDCG at 10 for the "
        "source-disjoint mixed and TF-to-virus domain-OOD tracks. Horizontal intervals are "
        "95% target-bootstrap confidence intervals and both panels use the same zero-to-one scale."
    )
    (figure_dir / "figure_2_alt_text.txt").write_text(alt + "\n")
    return {"id": "figure_2", "source_data": "figure_2_source_data.csv", "alt_text": alt}


def figure_vista(bundle: dict, figure_dir: Path, plt) -> dict:
    rows = []
    for method, result in bundle["vista"]["methods"].items():
        difference = result["paired_context_difference"]
        rows.append({
            "method": method,
            "label": METHOD_LABELS.get(method, method),
            "truncated_spearman": result["spearman_with_truncated"],
            "full_spearman": result["spearman_with_full"],
            "full_minus_truncated": difference["full_minus_truncated_spearman"],
            "difference_ci_low": difference["site_bootstrap_ci95"][0],
            "difference_ci_high": difference["site_bootstrap_ci95"][1],
            "n_sites": difference["n_sites"],
        })
    write_csv(figure_dir / "figure_3_source_data.csv", rows)

    fig, ax = plt.subplots(figsize=(180 / 25.4, 105 / 25.4), layout="constrained")
    for index, row in enumerate(rows):
        color, _ = method_style(row["method"], index)
        ax.plot(
            [row["truncated_spearman"], row["full_spearman"]], [index, index],
            color=color, linewidth=1,
        )
        ax.plot(
            row["truncated_spearman"], index, marker="o", color=color,
            markerfacecolor="white", markeredgewidth=1.2, markersize=5,
            label="Truncated" if index == 0 else None,
        )
        ax.plot(
            row["full_spearman"], index, marker="s", color=color,
            markerfacecolor="white", markeredgewidth=1.2, markersize=5,
            label="Full target" if index == 0 else None,
        )
    ax.axvline(0, color="#777777", linewidth=0.7, linestyle="--")
    ax.set(
        xlim=(-1, 1), yticks=range(len(rows)),
        yticklabels=[row["label"] for row in rows],
        xlabel="Spearman ρ with VISTA measurement", ylabel="Scorer",
        title="VISTA paired context stress test for one mCherry target",
    )
    ax.invert_yaxis()
    ax.grid(axis="x", color="#DDDDDD", linewidth=0.5)
    ax.legend(loc="lower right", frameon=False)
    save_figure(fig, figure_dir / "figure_3_vista_context")
    plt.close(fig)
    alt = (
        "Paired point plot with one row per scorer, showing Spearman correlation with truncated "
        "measurements as circles and full-target measurements as squares for 189 sites from one "
        "mCherry target. Lines connect the two contexts; this is a within-target stress test rather "
        "than a cross-target generalization estimate."
    )
    (figure_dir / "figure_3_alt_text.txt").write_text(alt + "\n")
    return {"id": "figure_3", "source_data": "figure_3_source_data.csv", "alt_text": alt}


def build_artifacts(processed: Path, output: Path) -> dict:
    processed = Path(processed).resolve()
    output = Path(output).resolve()
    bundle = load_bundle(processed)
    table_dir = output / "tables"
    figure_dir = output / "figures"

    tables = {
        "canonical_main": canonical_rows(bundle),
        "canonical_paired_vs_random": canonical_pairwise_rows(bundle),
        "beacon_tracks": beacon_rows(bundle),
        "vista_context": vista_rows(bundle),
    }
    notes = {
        "canonical_main": (
            "Canonical signed ON−OFF track. Intervals resample targets; pooled Spearman is auxiliary. "
            "The Random row is the exact per-target expectation under uniform ranking, not one sampled permutation."
        ),
        "canonical_paired_vs_random": (
            "Paired target-bootstrap differences versus the exact per-target expectation under "
            "uniform random ranking. Bootstrap P values use the add-one finite-resampling correction."
        ),
        "beacon_tracks": (
            "BEACON-normalized label; canonical absolute success thresholds are not transferred."
        ),
        "vista_context": (
            "One mCherry target and one study. Site-bootstrap intervals are within-target only."
        ),
    }
    for name, rows in tables.items():
        write_csv(table_dir / f"{name}.csv", rows)
        write_markdown(table_dir / f"{name}.md", name.replace("_", " ").title(), notes[name], rows)

    plt = configure_matplotlib(output / ".mplconfig")
    figures = [
        figure_objective_alignment(bundle, figure_dir, plt),
        figure_beacon(bundle, figure_dir, plt),
        figure_vista(bundle, figure_dir, plt),
    ]
    manifest = {
        "version": "0.2",
        "status": "provisional_general_manuscript_export",
        "journal_profile": "not selected; verify live journal requirements before submission",
        "source_results": {name: str(path) for name, path in bundle["paths"].items()},
        "transformations": [
            "no row filtering in artifact builder",
            "format precomputed target-level estimates and confidence intervals",
            "plot bounded rank metrics on zero-to-one axes",
            "plot correlations on minus-one-to-one axes",
        ],
        "uncertainty": (
            "canonical and BEACON intervals resample targets; VISTA difference intervals "
            "resample sites within one mCherry target"
        ),
        "missing_data_policy": "required missing results or fields stop artifact generation",
        "figure_width_mm": 180,
        "formats": ["PDF vector", "PNG 600 dpi"],
        "palette": "Okabe-Ito-on-white subset plus redundant marker/label encodings",
        "figures": figures,
        "tables": sorted(tables),
    }
    output.mkdir(parents=True, exist_ok=True)
    with (output / "artifact_manifest.json").open("w") as handle:
        json.dump(manifest, handle, indent=2, allow_nan=False)
    return manifest


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    data_root = Path(os.environ.get("TD_BENCH_ROOT", project_root / "data"))
    processed = Path(os.environ.get("TD_BENCH_PROCESSED", data_root / "processed"))
    output = Path(os.environ.get("TD_PAPER_ARTIFACTS", processed / "paper_artifacts_v02"))
    manifest = build_artifacts(processed, output)
    print(json.dumps(manifest, indent=2))
    print("wrote", output)


if __name__ == "__main__":
    main()
