# ToeholdDesignBench v0.2.1 最终执行与交付报告

日期：2026-08-21  
服务器：36.137.135.49:22  
远端代码目录：/home/cunyuliu/ToeholdDesignBench  
远端数据目录：/mnt/cunyuliu/ToeholdDesignBench  
控制合同：Target-Aware Toehold Benchmark 修订执行合同 v0.2.1（Markdown 合并版）

## 1. 最终结论

项目已经完成从“审稿批判 → 合同修订 → 代码与统计修复 → 远端全量重跑 → 论文重写 → 三位审稿人终审”的闭环。

三位终审者均未发现会使当前限定论证失效的阻断性技术、统计或主张越界问题，并认为稿件可向适配的专业 benchmark、计算生物学或合成生物学期刊投稿。该判断不等同于保证接收，也不表示当前证据达到 Nature 综合期刊所要求的 outstanding、far-reaching 影响力。

## 2. 初始审稿发现的主要问题

早期版本存在会影响可发表性的真实问题：

1. canonical 与 BEACON 数据规模和标签语义混写；
2. CNN 通道布局错误；
3. canonical signed ON − OFF 被不当处理；
4. 置信区间没有按 target 作为独立单位；
5. 单个随机种子被当成论文随机基线；
6. Pareto 指标定义依赖选中集合；
7. BEACON published row split 被误读为 unseen-target 证据；
8. BEACON 原 split 字段与新 source split 合并后发生 split_x/split_y collision；
9. VISTA 单 mCherry target 被过度解释为普遍 transfer failure；
10. 旧论文坚持“prediction 与 design 方法排序背离”，但最终数据不支持；
11. baseline proxy 名称容易被误读为完整复现已发表系统；
12. 稿件缺完整 Results、Methods、statistics、figure references 与 submission-grade legends。

这些问题已在 v0.2/v0.2.1 合同中转化为明确验收条件。

## 3. 已完成的实现与统计修复

- 修正 CNN 输入为 N × 4 × L。
- canonical 保留 signed ON − OFF，NDCG 在 target 内平移 relevance 而不截断负值。
- success@1 冻结为主终点，阈值 ON ≥ 0.5 且 OFF ≤ 0.5。
- targets with no feasible candidate 保留在分母。
- 学习型 canonical 基线采用 5 seeds 并报告 mean prediction。
- 随机基线改为逐 target 解析期望：
  - exact success@K；
  - expected NDCG；
  - finite-sample expected regret；
  - expected Pareto coverage。
- mean CI 改为 target bootstrap；method comparison 改为 paired target bootstrap。
- finite bootstrap P 使用 add-one correction，结构化检查确认没有 P = 0。
- Pareto 改为 global-front coverage。
- oracle 保留全部 test targets，并明确为 diagnostic。
- BEACON published row split 重命名为 published_row_split。
- 增加 BEACON TF/virus train-test target overlap audit。
- 新建 BEACON source-disjoint mixed 与 TF-to-virus tracks。
- VISTA 解释改为 outcome-neutral single-target stress test。
- figure title、table note 与 alt text 按最终观察方向修正。
- runner、schema、JSON、tables 和 manuscript 的 metric/target accounting 对齐。

## 4. 远端执行记录

### 环境

- Python 3.10.20
- PyTorch 2.5.1+cu121
- CUDA available
- 环境：/home/cunyuliu/miniconda3/envs/toeholdbench

### 迭代过程

1. 初次 v0.2 run 完成 canonical 与 revision analyses，在 BEACON 阶段因 split column collision 中止。
2. 修复 published split 与 source split 字段冲突并加入 regression test。
3. 恢复运行完成 BEACON、VISTA、runner 和 paper artifacts。
4. 统计复核发现 seed-0 random 的 success@1 = 0.350，而解析随机期望约为 0.275；这一差异会改变主要结论。
5. 将所有 paper-facing random metrics 和 paired comparisons 改为解析期望。
6. 归档 superseded single-random 结果到：
   /mnt/cunyuliu/ToeholdDesignBench/iterations/v02_single_random_20260821
7. 执行正式 v0.2.1 全量重跑，成功结束。

### 最终运行日志

/home/cunyuliu/ToeholdDesignBench/logs/v02_exact_random_20260821T2002.log

该日志以以下信息结束：

- all metric tests passed；
- all extended metric + runner tests passed；
- canonical train records 39,517；
- canonical test records 7,041；
- canonical test targets 140；
- v0.2 core analyses completed。

本地最终测试：20 passed。

## 5. 最终核心结果

### canonical 主终点

测试集：140 targets，其中 128 个至少有一个合格候选，12 个无合格候选。

| Method | success@1 | Paired difference vs exact random | 95% CI of difference |
| --- | ---: | ---: | ---: |
| Exact random expectation | 0.275 | — | [0.251, 0.302] 为其 target-bootstrap mean CI |
| MLP | 0.400 | +0.125 | [0.048, 0.203] |
| Deeper CNN proxy | 0.357 | +0.082 | [0.010, 0.157] |
| Thermodynamic proxy | 0.343 | +0.068 | [−0.005, 0.143] |
| CNN | 0.221 | −0.054 | [−0.118, 0.013] |
| Sequence + local biophysics | 0.250 | −0.025 | [−0.089, 0.047] |

结论：MLP 和 deeper CNN proxy 在 frozen primary endpoint 上高于解析随机期望；thermodynamic proxy 的 success@1 差异不确定。

### objective alignment

- pooled prediction Spearman 与 mean target NDCG@10 的方法秩 Spearman：1.00；
- pooled prediction Spearman 与 success@1 的方法秩 Spearman：0.881；
- MLP 与 thermodynamic proxy top-1 agreement：0.114。

因此旧主张“prediction 与 design 方法排序普遍不一致”被撤回。可以主张两个评价轴定义不同、预算结论不同，不能主张必然经验背离。

### BEACON

published row split overlap：

- TF：772/773 test targets 与 train 重叠；
- virus：23/23 test targets 与 train 重叠。

source-disjoint mixed NDCG@10：

- exact random 0.591；
- MLP first 30 nt 0.611；
- MLP 148 nt 0.746。

TF-to-virus NDCG@10：

- exact random 0.524；
- MLP first 30 nt 0.575；
- MLP 148 nt 0.679。

### VISTA

- one mCherry target；
- 189 paired sites；
- truncated vs full Spearman = 0.933；
- top-10 overlap = 0.60；
- median absolute rank shift = 12；
- 所有 scorer 的 full-minus-truncated correlation difference CI 均跨越 0。

结论：该单靶标数据支持 measurement rank agreement，未支持 scorer correlation 的上下文变化；不能据此得出普遍 transfer 成功或失败。

## 6. 稿件定位

最终稿定位为 benchmark/resource + evaluation audit，而不是新算法论文。

支持的中心论证：

> 公开 fused-trigger 数据可以被重构为 source-disjoint、逐靶标的候选排序任务；这种重构揭示原有行级拆分的靶标重叠并量化固定预算效用，但不等同于前瞻、跨上下文或 de novo 设计验证。

论文已包含：

- 约 250 词结构化摘要；
- 完整 Introduction、Results、Discussion、Methods、Conclusion；
- 两张正文结果表；
- 三张正式 Figure legends；
- Data availability 与 Code availability；
- 七条经原始论文/官方 proceedings 验证的参考文献；
- 所有无法推断的作者元数据用 AUTHOR_INPUT_NEEDED 标注。

## 7. 三审结论

三位审稿人分别强调：

1. 技术可靠性：当前限定论证无阻断性技术错误；
2. 创新性和重要性：evaluation protocol/resource 有专业发表价值，但不足以主张 Nature 级综合影响；
3. 跨领域可读性：正文和图表可读，流程 schematic 是可选增强而非技术门槛。

综合结论：稿件达到适配专业期刊的投稿就绪科学标准。正式提交前不需新增计算分析来建立当前主张，但必须由作者补齐投稿元数据与许可。

## 8. 作者投稿前必须补齐

- 作者、单位、通讯作者与 ORCID；
- CRediT author contributions；
- funding 与 competing interests；
- 最终公共仓库 URL、release commit 与 license；
- Zenodo 或同类永久 archive DOI；
- VISTA workbook 再分发许可；若不能再分发，改为 download script only；
- 目标期刊选择与最新格式适配。

如果作者要扩大为 SOTA、真实 trans sensing、cross-target full-context generalization 或 prospective/de novo design 论文，则必须新增官方模型复现和/或新的湿实验；现有数据不能通过措辞调整获得这些证据。

