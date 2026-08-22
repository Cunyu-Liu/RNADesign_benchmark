"""Assemble v0.3.0 deliverables into local outputs/ (contract §9 Batch 4).

Copies SMALL summary artifacts (CSV/JSON/MD) from /mnt run directories into
the repo-local outputs/ tree; large artifacts (predictions, checkpoints)
stay in /mnt with their paths recorded in the manifest.
"""
import json
import os
import shutil
import time

BASE = "/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0"
OUT = "/home/cunyuliu/ToeholdDesignBench/outputs/v0.3.0"

COPIES = {
    "eval_cnn60_family/method_summary.csv": "eval_cnn60_family_method_summary.csv",
    "eval_cnn60_family/contrasts.csv": "eval_cnn60_family_contrasts.csv",
    "eval_sandstorm_family/method_summary.csv": "eval_sandstorm_family_method_summary.csv",
    "eval_sandstorm_family/contrasts.csv": "eval_sandstorm_family_contrasts.csv",
    "exposure_matrix/exposure_matrix.csv": "exposure_matrix.csv",
    "method_registry.json": "method_registry.json",
}

# newest directory per prefix
LATEST = {
    "crowd_external_": ["spearman_summary.csv", "exposure_check.json",
                        "execution_manifest.json"],
    "vista_sars_": ["group_measured_summary.csv",
                    "group_transfer_scores_cnn60.csv",
                    "group_transfer_scores_sandstorm.csv",
                    "execution_manifest.json"],
    "vista_external_": ["vista_external_results.json"],
    "protocol_freeze_audit_": None,  # handled specially (whole json)
}


def latest_dir(prefix):
    cands = sorted(d for d in os.listdir(BASE)
                   if d.startswith(prefix) and
                   os.path.isdir(f"{BASE}/{d}"))
    return f"{BASE}/{cands[-1]}" if cands else None


def main():
    os.makedirs(OUT, exist_ok=True)
    copied = []

    for src_rel, dst_name in COPIES.items():
        src = f"{BASE}/{src_rel}"
        if os.path.exists(src):
            shutil.copy2(src, f"{OUT}/{dst_name}")
            copied.append(dst_name)

    for prefix, files in LATEST.items():
        d = latest_dir(prefix)
        if d is None:
            continue
        tag = prefix.rstrip("_")
        if files is None:
            dst = f"{OUT}/{os.path.basename(d)}.json"
            shutil.copy2(d if d.endswith(".json") else f"{d}.json", dst)
            copied.append(os.path.basename(dst))
            continue
        for f in files:
            src = f"{d}/{f}"
            if os.path.exists(src):
                dst = f"{OUT}/{tag}__{f}"
                shutil.copy2(src, dst)
                copied.append(os.path.basename(dst))

    # freeze audit json files live directly under BASE
    audits = sorted(f for f in os.listdir(BASE)
                    if f.startswith("protocol_freeze_audit_")
                    and f.endswith(".json"))
    if audits:
        shutil.copy2(f"{BASE}/{audits[-1]}",
                     f"{OUT}/{audits[-1]}")
        copied.append(audits[-1])

    # paper figures + source data
    figs = "/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/paper_figs"
    if os.path.isdir(figs):
        os.makedirs(f"{OUT}/paper_figs", exist_ok=True)
        for f in os.listdir(figs):
            shutil.copy2(f"{figs}/{f}", f"{OUT}/paper_figs/{f}")
            copied.append(f"paper_figs/{f}")

    # paper draft snapshot
    shutil.copy2("/home/cunyuliu/ToeholdDesignBench/docs/paper_draft_v03.md",
                 f"{OUT}/paper_draft_v03.md")
    copied.append("paper_draft_v03.md")

    manifest = {
        "assembled_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": ("small deliverables copied locally; large artifacts "
                 "(predictions/checkpoints) remain under "
                 "/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/"),
        "files": copied,
    }
    with open(f"{OUT}/outputs_manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"assembled {len(copied)} files -> {OUT}")


if __name__ == "__main__":
    main()
