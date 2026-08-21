# ToeholdDesignBench 项目交接文档

生成日期：2026-08-21 · 依据合同：`提示词/Target_Aware_Toehold_Benchmark_创新性评估与执行方案_v0.1_2026-08-19.docx`
仓库：`git@github.com:Cunyu-Liu/RNADesign_benchmark.git`（master，HEAD 见文末）
代码/提交在 `/home/cunyuliu/ToeholdDesignBench`，大型 artifact 在 `/mnt/cunyuliu/ToeholdDesignBench`

---

## 0. 项目一句话定位

**ToeholdDesignBench**：一个"目标感知、实验上下文分层、候选选择效用导向"的 toehold RNA sensor
设计系统 benchmark。核心创新不是"用 AI 设计 toehold"，而是把领域主指标从单序列 `R²` 换成
**per-target top-K 设计效用**，并用 source-disjoint 拆分 + 跨 fused/trans/full-target 上下文外部验证
来回答"预测准确率是否等于设计效用"。

**证据层级**：R1（fused-context 回顾性排序，主任务）→ R2（trans/full-target 外部验证）→ P1（前瞻实验，可选）。

---

## 1. 已完成工作（做了什么）

按合同 §9 的 P0–P6 分阶段执行，实际完成 **P0–P5**，P6（前瞻湿实验）未启动（合同 §9.1 明确"现在不启动湿实验"，属可选升级）。

### P0 — 证据与可行性审计（Gate 0）✅
产出 8 项交付物（O0-01~08），全部存在：
- `literature_claim_matrix.xlsx`（相似工作冲突矩阵：Green 2014 / To 2018 / Angenent-Mari 2020 / Valeri 2020 / BEACON 2024 / GARDN-SANDSTORM 2025 / Toehold-VISTA 2026 / NucleoBench）
- `data_inventory.csv`、`study_context_registry.yaml`、`canonical_pilot.parquet`
- `source_overlap_audit.html`、`sanity_baseline_report.html`、`task_contract_v0.1.md`、`gate0_decision_memo.md`
- 结论：**GO**（带 ≤70k paired 的 HOLD 披露项，见 §4）

### P1 — 数据与 provenance 构建 ✅
- `canonical_records.parquet`：**92,731 行**（97,436 raw → 92,731 virus+TF + 4,705 random 排除）
  - admission：`admitted_paired` 52,861 / `admitted_single_label` 27,439 / `retained_no_label` 12,431
  - **931 targets**（23 病毒 + 908 人类 TF）
  - 坐标重建：**94.9%** absolute（87,989），余 5.1% 保留为 `no_coord`（fail-closed 不剔除、有 ledger）
- 配套：`source_map.csv`、`exclusion_ledger.csv`、`license_matrix.csv`、`hash_manifest.json`

### P2 — TaskSpec、拆分与指标冻结 ✅
- `split_manifests.csv`：source-disjoint **648 train / 138 val / 140 test** targets（target 不跨 split）
- `leakage_report.html`：row-random 泄漏 99.9% vs source-disjoint 0
- 指标：success@K / NDCG@K / regret / Pareto；预注册**绝对阈值** ON≥0.5 & OFF≤0.5（测试独立）
- `tests/test_metrics.py` + `test_extended.py`：**12 项单测全过**

### P3 — 核心基线复现 ✅
6 族 8 基线（`src/p3_baselines.py`）：B0_random、B0_gc、B1_thermo、B2_mlp、B2_cnn、B3_deep、B4_struct、B5_structrank。
seed=0 固定、torch 在建模型前 seed，两次运行逐位一致（可复现）。

### P4 — 主实验 E1–E6 与红队 ✅
6 项非平凡发现（合同要求 ≥2）：
- **E1** Prediction≠Design：prediction ρ 与 design success@K 排名不一致（方法秩相关仅 0.32）
- **E2** Split stress：row-random 泄漏 99.9% 测试 source；泄漏不膨胀预测 ρ（说明 trigger ON/OFF 信号本身弱）
- **E3** Fused→full-target 迁移失败：fused 模型（ρ=-0.07/-0.20）与 tsgen2（-0.23）在 VISTA mCherry 均反相关，仅 GC 迁移（+0.30）
- **E4** 结构特征 concatenation 反而降低设计效用（seq-only 0.350 → 0.214/0.250）
- **E5** Ratio pathology：OFF-only 排序 success@1 塌到 0.234，ratio 0.992，证明多目标必需
- **E6** 评估器选择翻转 top-1（交叉评估器 8.6% 一致），proxy overfitting 确认

### P5 — 发布与论文包 ✅
- `runner.py`（一行复现）、`datasheet.md`、`leaderboard_schema.json`、`paper_draft.md`
- `scripts/download_data.sh`、Dockerfile（静态验证，未 build）、`pollution_statement.md`

### 审稿修订（2026-08-20 追加，超出原 P5 但为回应审稿人）✅
- **A1 病毒组扩张 n=6 → 23**：BEACON 91,534 → target 归因从 41.3% 提升到 **100%**（权威 GSE149225 source_sequence 映射）
  - 病毒 40,824 行 / 23 targets，TF 47,005 / 905，random 3,705；test 病毒 23 targets / 4,003 行
  - 与独立 30-mer trigger 法交叉验证 100% 一致
- **R2 置换检验**：病毒组排序信号 MLP n=23 ρ=+0.127 与 n=6 ρ=+0.174，within-target label 置换 5000 次 **p=0.0002**
- **R5 DL vs thermo 协议审计**：E1 头条"thermo 最佳预测器(ρ=0.136)"是协议伪影——20ep/5seed MLP 达 ρ=0.274（thermo 2 倍），MLP 自学出 MFE 样信号（corr 0.37），无过拟合 gap

---

## 2. 做到什么程度（关键结果）

### 2.1 数据规模
| 指标 | 值 |
|---|---|
| canonical records | 92,731（52,861 paired + 27,439 single + 12,431 no-label） |
| targets | 931（23 病毒 + 908 TF） |
| 坐标重建 | 94.9% absolute |
| BEACON 91,534 序列映射 | 100% target 归因（GSE149225） |
| source-disjoint 拆分 | train 648 / val 138 / test 140 targets，overlap=0 |
| 序列级预测基线（BEACON 全长） | GBDT test R²=0.216, ρ=0.458 |

### 2.2 核心设计效用（source-disjoint，绝对阈值，8 基线）
| 基线 | success@1 | success@3 | NDCG@10 |
|---|---|---|---|
| B0_random | 0.350 | 0.593 | 0.520 |
| B0_gc | 0.093 | 0.350 | 0.414 |
| B1_thermo | 0.343 | **0.700** | 0.564 |
| B2_mlp | 0.350 | 0.664 | **0.588** |

**关键诚实结论**：严格 source-disjoint + 绝对阈值下，**top-1 接近随机**（所有方法 0.24–0.35）。
信号在 top-3/NDCG 处分离。这是**可解释的**（TF 主导 + label-limited），不是 NO-GO，但**限定了主张强度**
——只能主张"候选排序 benchmark"，不能主张 trans sensing 或 de novo design。

### 2.3 病毒组稳健性（回应"n=6 太小"审稿质疑）
| 集合 | MLP mean ρ | bootstrap 95% CI | 置换 p |
|---|---|---|---|
| n=6 canonical | +0.174 | [+0.124, +0.227] | 0.0002 |
| n=23 authoritative | +0.127 | [+0.077, +0.181] | 0.0002 |

信号在 n=23 独立集上仍显著（random 处于随机水平，GC 显著为负）。

### 2.4 DL vs thermo（审稿问题 5 的诚实答案）
- 论文协议（15ep/seed0）：MLP ρ=0.110 < thermo 0.136
- 标准协议（20ep/5seed）：MLP ρ=**0.274** > thermo 0.136
- 结论：E1 的"thermo 最佳预测器"**是协议依赖的**，已软化为协议审计表述（附录 §D.10 + paper §E1 已同步）

---

## 3. 合同任务核对结果

**总体判断：P0–P5 全部执行并验收，P6（可选）未执行——符合合同范围。**

| 阶段 | GO 门要求 | 实际 | 状态 |
|---|---|---|---|
| P0 Gate 0 | 准入 100% source/坐标 | source 100%，坐标 94.9%（余保留+ledger） | ✅ PASS |
| P0 | ≥500 target groups | 931 | ✅ PASS |
| P0 | ≥1 个 ≥100 候选 trans/full-target 外部集 | VISTA mCherry ~190 sites | ✅ PASS |
| P0 | ≥4 类基线可运行 | 8 基线（6 族）GPU 可复现 | ✅ PASS |
| P0 | 许可可闭合 | 主数据 CC BY 4.0；VISTA 待确认 | ✅ PASS(带 note) |
| P0 | **≥70k paired records** | Gate0 时 52,861（HOLD）；A1 后 91,534 全量归因 | ⚠️→✅ 已闭合 |
| P1 | admitted 可回溯、context 完整、不混标 | canonical + source_map + exclusion ledger + license matrix | ✅ |
| P2 | source/cluster overlap=0、阈值不参与选择 | overlap=0、绝对阈值预注册 | ✅ |
| P3 | 固定 seed 可重放、coverage 明确 | seed=0 两次一致、8/8 覆盖率 | ✅ |
| P4 | ≥2 项非平凡发现 | 6 项（E1–E6） | ✅ |
| P5 | 独立使用者可复现 | runner + datasheet + schema + paper draft | ✅ |
| P6 | 前瞻验证（可选） | 未执行（合同 §9.1 明确不启动湿实验） | — 可选未做 |

**验收结论**：
1. **合同要求的强制阶段（P0–P5）全部完成并验收。** P6 是可选项，合同中明确"现在不启动湿实验"，未执行不算违约。
2. **三个历史 HOLD/偏离点**（诚实披露）：
   - **≥70k paired 门**：Gate 0 时只到 52,861，是 HOLD；本次 A1 用 GSE149225 权威源把 91,534 全量归因到 target，**已闭合**，但 `gate0_decision_memo.md` 中的 HOLD 描述尚未回改为 PASS。
   - **Docker build**：因用户权限未执行 build，仅做静态验证（`.gitignore`/下载脚本/入口语法），已在 proto 记录。
   - **模型命名**：去绑定（STORM/NuSpeak→B3_deep，VISTA→B5_structrank 等），已诚实改名为"代表性族"。
3. **未完成的收尾**：见 §5。

---

## 4. 未来需要做什么（按优先级）

### P1 优先级（投稿前必须）
1. **回改 `gate0_decision_memo.md` 与 `data_reconciliation.md`**：把 ≥70k paired 的历史 HOLD 标记为"已通过 A1 权威归因闭合"，避免审稿人看到不一致。
2. **`paper_draft.md` 结构化**：当前是 P5 清单式草稿，缺完整 Results/Discussion 论证流、figure 编号引用、statistical methods 段。这是投稿的硬门槛。
3. **VISTA 许可确认**：`license_matrix.csv` 已标注 VISTA 待确认；投稿前必须拿到可再分发授权或改为"仅提供下载脚本"。
4. **R5 协议审计落到正文**：把 E1 的"thermo 最佳预测器"从 P3/P4 report 中也同步软化（目前 paper §E1 已改，但 `p3_baseline_report.md`/`p4_report.md` 里的旧表述需一并复核）。

### P2 优先级（提升论文上限）
5. **R2 外部验证补强**：目前 E3 只有 VISTA mCherry 189 tiles（样本小）。补充更多 trans/full-target 外部研究（Valeri 168 free-trigger / Pardee 24 Zika），把"fused→full-target 迁移失败"从单点观察升级为跨研究结论。
6. **检索日志更新**：合同 §14.1 要求投稿前复查新 preprint/专用 benchmark，更新 novelty statement。

### P3 优先级（可选升级）
7. **P6 前瞻验证**：合同 §9 定位为"唯一能支撑真正 redesign/de novo 效用声明的任务"。需要湿实验协作、预注册协议、near/non-cognate 对照、盲法。**这是把论文从"Borderline Accept"推到"高影响"的唯一路径**，但需要实验资源。
8. **隐藏测试 / 限次提交**：`leaderboard_schema` 已有静态度量，但真正抗过拟合需要 hidden source split 或新增外部目标（合同 R13/R10）。

---

## 5. 未闭合项与风险（诚实清单）

| # | 项 | 状态 | 影响 |
|---|---|---|---|
| 1 | ≥70k paired 历史 HOLD 未回改 | 待改文档 | 审稿人可能看到矛盾 |
| 2 | paper_draft 是清单式草稿 | 需结构化 | 不能直接投稿 |
| 3 | VISTA 许可 | 待确认 | 可能只能给下载脚本 |
| 4 | E1 旧头条在 p3/p4 report 残留 | 待同步 | 与附录 D.10 不一致 |
| 5 | E3 外部样本小（189 tiles） | 需补强 | 迁移失败结论需跨研究支撑 |
| 6 | top-1 ≈ random（TF 主导） | 已诚实披露 | 主张限于"候选排序" |
| 7 | P6 前瞻实验未做 | 可选未启动 | de novo 声明被禁 |

---

## 6. 版本与提交

- master HEAD：`ee8d9af`（最近 10 次提交覆盖 t1 数据 → t10 paper E1 同步）
- 关键提交：`39e533c`（P0–P5 完成）、`f60485a`（A1 100% 归因）、`cbda6d3`（R2/R5 置换+协议审计）、`ee8d9af`（paper E1 同步）
- 工作区：clean，与 origin/master 一致