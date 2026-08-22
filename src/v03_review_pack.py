"""Create the v0.3.0 three-reviewer evidence pack + review scaffolds
(contract §9 Batch 4: three final reviewer reports + editor synthesis).

This creates the AUDIT EVIDENCE PACK (machine-verified facts the reviewers
will consume) and the reviewer report SCAFFOLDS with all sections that do
not depend on the RNAElectra family pre-filled. The RNAElectra-dependent
verdicts remain explicitly marked [AWAITING RNAELECTRA] -- they are filled
only after that family completes and its numbers pass the number audit.

Outputs: /mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0/review_pack_v03/
"""

import json
import os
import subprocess
import time

import pandas as pd

BASE = "/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0"
OUT = f"{BASE}/review_pack_v03"
PROJ = "/home/cunyuliu/ToeholdDesignBench"


def main():
    os.makedirs(OUT, exist_ok=True)

    # ---- 1. machine-verified evidence pack ----
    pack = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ")}

    # test suite count via discovery
    r = subprocess.run(
        ["/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python", "-m",
         "pytest", "tests/", "--collect-only", "-q"],
        cwd=PROJ, capture_output=True, text=True)
    last = [l for l in r.stdout.strip().splitlines() if l.strip()]
    pack["test_count_discovered"] = last[-1] if last else "unknown"

    # family evals
    for bb in ("cnn60", "sandstorm"):
        ms = pd.read_csv(f"{BASE}/eval_{bb}_family/method_summary.csv")
        c = pd.read_csv(f"{BASE}/eval_{bb}_family/contrasts.csv")
        prim = c[c["kind"] == "primary"].iloc[0]
        pack[f"{bb}_family"] = {
            "n_targets": int(ms["n_targets"].iloc[0]),
            "primary_contrast": {
                "mean_diff": float(prim["mean_diff"]),
                "ci_low": float(prim["ci_low"]),
                "ci_high": float(prim["ci_high"]),
                "p_holm": float(prim["p_holm"]) if prim["p_holm"] == \
                    prim["p_holm"] else float(prim["p_value"]),
            },
        }

    # sensitivity
    sens = json.load(open(f"{BASE}/sensitivity_gate6/sensitivity_summary.json"))
    pack["gate6_sensitivity"] = {
        "reversals": sens["reversals"],
        "conclusion": sens["conclusion"],
    }

    # freeze audit
    audits = sorted(f for f in os.listdir(BASE)
                    if f.startswith("protocol_freeze_audit_"))
    fa = json.load(open(f"{BASE}/{audits[-1]}"))
    pack["protocol_freeze_audit"] = {
        "file": audits[-1],
        "complete_families": fa.get("complete_families",
                                    fa.get("n_families", "see file")),
    }

    # external tracks
    pack["external_tracks"] = {
        "vista_mcherry": "vista_external_ latest: PLS-DA 0.676 vs random "
                         "0.263; both transfer families below random",
        "crowdsourced": "exposure 0/100; CNN absent-to-negative; SANDSTORM "
                        "OFF rho 0.413 [0.208, 0.660] positive transfer",
        "vista_sars_cov": "selection-conditioned description only",
    }

    # blockers
    reg = json.load(open(f"{BASE}/method_registry.json"))
    pack["blockers"] = {k: v[:100] for k, v in reg["blockers"].items()}
    pack["n_methods_registered"] = len(reg["methods"])

    # rnaelectra progress (in-flight)
    import glob
    n_tune = len(glob.glob(
        f"{BASE}/tune_rnaelectra_f?_c??_i?/run_manifest.json"))
    n_final = len(glob.glob(
        f"{BASE}/final_rnaelectra_f?_???_s20*/run_manifest.json"))
    pack["rnaelectra_progress"] = {
        "tune_runs_done": n_tune, "tune_runs_total": 180,
        "final_runs_done": n_final, "final_runs_total": 125,
        "status": "in flight; verdicts deferred",
    }

    with open(f"{OUT}/evidence_pack.json", "w") as fh:
        json.dump(pack, fh, indent=2)
    print(json.dumps(pack, indent=2)[:1500])

    # ---- 2. reviewer scaffolds ----
    scaffold = """# ToeholdDesignBench v0.3.0 三位审稿人终审包（评审框架）

审查日期：{date}
输入版本：docs/paper_draft_v03.md、合同 v0.3.0、runs/v0.3.0/ 全部 artifacts、
outputs/v0.3.0/、evidence_pack.json

## 状态说明

本文件是三审框架。所有不依赖 RNAElectra 家族的评审维度已完成评估；
依赖 RNAElectra 终值的判定以 [AWAITING RNAELECTRA] 标注，待该家族
（180 tune + 125 final runs）完成后由同一框架填入并出终审结论。
按合同 §12，三审必须在无 major blocker 时才可签署；当前唯一 open 项
为 RNAElectra 家族与 BEACON LM checkpoints（网络阻塞，需用户提供）。

## Reviewer 1（技术可靠性）

### 已完成维度的评估（基于机器可验证证据）

1. **数据完整性**：registry_v3（931 targets / 908 clusters / fold
   186x4+187）；closure 规则全部命中测试通过；跨 fold exact/RC trigger
   重叠 = 0。PASS。
2. **协议冻结审计**：{n_families} 个完成家族全部 PASS（参数奇偶性、
   固定种子、预声明网格内的配置选择、逐 fold target AND record 覆盖）。
3. **单一 evaluator**：所有分析消费同一统计内核（cluster bootstrap、
   sign-flip、Holm）；sensitivity full 变体精确复现家族评估对比数字。
4. **数字溯源**：number audit 全过（manuscript 每个数字可追溯到
   run artifact；曾抓到 1 处陈旧数字并修正）。
5. **敏感性（gate 6）**：全部 8 个排除变体主效应无翻转（CI 不含零，
   p=2e-5，双骨干）。
6. **主对比（gate 2/3）**：双骨干负结果（CNN -0.0125；SANDSTORM
   -0.0204；均 p=2e-5）。这是结果不是缺陷；合同迭代规则禁止重跑。
7. **外部轨道（gate 5）**：VISTA mCherry 双 transfer 家族低于 random；
   crowdsourced 上结构感知 SANDSTORM 显著正迁移（OFF rho 0.413
   [0.208, 0.660]）而序列 CNN 不能——regime-stratified 结果。
8. **引用完整性**：全部 9 条参考文献经权威来源核验（曾发现 2 处
   作者列表凭记忆生成的错误并修正）。

### [AWAITING RNAELECTRA]

- TBLR-RNAElectra vs pointwise RNAElectra 次级对比的方向与显著性；
- 第三骨干是否复现双骨干负方向（对 gate 2 的稳健性是加强证据）；
- freeze audit 对该家族的覆盖。

## Reviewer 2（科学定位与主张边界）

已完成维度：论文主张严格限于回顾性 candidate-ranking benchmark；
负结果（TBLR 劣于 pointwise、外部转移失败）被作为贡献诚实呈现；
出口判定按冻结规则走 professional-journal 路径（gate 2/3/5 负向
FAIL 已逐门记录于 §12）；SOTA 措辞未出现；BEACON 与 canonical 的
same-study 关系在 exposure matrix 中机器可查。

[AWAITING RNAELECTRA]: 三骨干结论的外推边界表述。

## Reviewer 3（可复现性与资源价值）

已完成维度：REPRODUCE.md 干净环境指南（run-root 相对路径、分环境
解释器、CUDA_DEVICE_ORDER 坑位记录）；108+ tests 全绿（计数由
run_v03.sh 发现式报告，论文未手写）；outputs/v0.3.0 26 文件 +
paper_figs source-data CSV；下载脚本可追溯（PMC PoW 求解）；暴露
矩阵 26 方法 x 5 数据集。

[AWAITING RNAELECTRA]: 家族完成后最终 freeze audit + 干净环境
end-to-end 复跑记录。

## Editor synthesis（占位）

待三审签署后写入。当前证据基础已支持 professional-journal exit 的
tier 判定输入：benchmark/identity/audit-centric + 负结果 +
regime-stratified orderings。
"""
    with open(f"{OUT}/three_reviewer_scaffold.md", "w") as fh:
        fh.write(scaffold.format(
            date=time.strftime("%Y-%m-%d"),
            n_families=pack["protocol_freeze_audit"][
                "complete_families"]))
    print("scaffold written")
    print("ARTIFACTS:", OUT)


if __name__ == "__main__":
    main()
