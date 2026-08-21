"""Focused tests for the result-to-paper artifact boundary."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from build_paper_artifacts import build_artifacts  # noqa: E402


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value))


def metric(mean: float, lo: float, hi: float, n: int = 10) -> dict:
    return {"mean": mean, "ci95": [lo, hi], "n_targets": n}


def synthetic_results(processed: Path) -> None:
    methods = {}
    canonical_methods = (
        "B0_random", "B0_gc", "B1_thermo", "B2_mlp", "B2_cnn", "B3_deep",
        "B4_struct", "B5_structrank",
    )
    for index, name in enumerate(canonical_methods):
        value = 0.35 + 0.04 * index
        methods[name] = {
            "pooled_prediction_spearman": -0.20 + 0.06 * index,
            "success_at_1": metric(value, value - 0.08, value + 0.08),
            "success_at_3": metric(value + 0.1, value + 0.02, value + 0.18),
            "success_at_5": metric(value + 0.2, value + 0.12, min(1.0, value + 0.28)),
            "ndcg_at_10": metric(value + 0.05, value, value + 0.1),
            "normalized_regret_at_10": metric(0.22 - index * 0.015, 0.08, 0.3),
            "pareto_front_coverage_at_10": metric(value, value - 0.1, value + 0.1),
        }
    paired = {}
    for name in canonical_methods[1:]:
        paired[name] = {}
        for metric_name in (
            "success_at_1", "success_at_3", "ndcg_at_10", "pareto_front_coverage_at_10"
        ):
            paired[name][metric_name] = {
                "mean_difference": 0.05,
                "ci95": [0.01, 0.09],
                "two_sided_bootstrap_p": 0.02,
                "n_targets": 10,
            }
    write_json(processed / "p3_baselines_v02.json", {
        "version": "0.2",
        "label_semantics": "signed canonical ON minus OFF",
        "seed_policy": {"learned_models": [0, 1, 2, 3, 4]},
    })
    write_json(processed / "revision_analysis_v02.json", {
        "version": "0.2",
        "E1_objective_alignment": {"methods": methods, "paired_vs_random": paired},
    })
    tracks = {}
    for track_name in ("source_disjoint_mixed", "TF_to_virus_domain_OOD"):
        tracks[track_name] = {
            "n_test_targets": 10,
            "target_overlap": 0,
            "methods": {
                name: {
                    "target_spearman": metric(0.1, 0.0, 0.2),
                    "ndcg_at_10": metric(0.5 + index * 0.05, 0.4, 0.7),
                    "normalized_regret_at_10": metric(0.2, 0.1, 0.3),
                }
                for index, name in enumerate(("random", "gc_full", "mlp30", "cnn30", "mlp148"))
            },
        }
    write_json(processed / "beacon_target_benchmark_v02.json", {
        "version": "0.2", "tracks": tracks,
    })
    vista_methods = {}
    for index, name in enumerate((
        "random", "gc_first30", "tsgen2", "fused_mlp_first30", "fused_mlp_last30"
    )):
        vista_methods[name] = {
            "spearman_with_truncated": -0.2 + index * 0.1,
            "spearman_with_full": -0.15 + index * 0.08,
            "paired_context_difference": {
                "full_minus_truncated_spearman": 0.05 - index * 0.02,
                "site_bootstrap_ci95": [-0.1, 0.2],
                "n_sites": 189,
            },
            "top10_overlap_with_truncated_oracle": 0.1,
            "top10_overlap_with_full_oracle": 0.2,
        }
    write_json(processed / "vista_paired_context_v02.json", {
        "version": "0.2",
        "scope": "single_target_single_study_paired_context_stress_test",
        "methods": vista_methods,
    })


def test_build_artifacts_from_v02_results():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        processed = root / "processed"
        output = root / "paper"
        processed.mkdir()
        synthetic_results(processed)
        os.environ["MPLCONFIGDIR"] = str(root / "mplconfig")
        manifest = build_artifacts(processed, output)
        assert manifest["version"] == "0.2"
        assert (output / "artifact_manifest.json").is_file()
        assert (output / "tables" / "canonical_main.md").is_file()
        assert (output / "figures" / "figure_1_objective_alignment.pdf").is_file()
        assert (output / "figures" / "figure_2_beacon_tracks.png").is_file()
        assert (output / "figures" / "figure_3_alt_text.txt").is_file()
        with Image.open(output / "figures" / "figure_1_objective_alignment.png") as figure:
            assert figure.mode == "RGB"
            assert figure.info["dpi"][0] >= 599
        table_text = (output / "tables" / "vista_context.md").read_text()
        assert "One mCherry target" in table_text
        assert "nan" not in json.dumps(manifest).lower()


def test_missing_result_fails_closed():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        try:
            build_artifacts(root, root / "paper")
        except FileNotFoundError as exc:
            assert "required v0.2 result is missing" in str(exc)
        else:
            raise AssertionError("missing results should stop paper artifact generation")


if __name__ == "__main__":
    test_build_artifacts_from_v02_results()
    test_missing_result_fails_closed()
    print("paper artifact tests passed")
