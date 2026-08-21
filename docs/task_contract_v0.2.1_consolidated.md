# Target-Aware Toehold Benchmark 修订执行合同 v0.2.1（合并控制版）

版本日期：2026-08-21  
文档格式：Markdown  
状态：本文件自发布起为项目唯一控制合同。v0.1、v0.2、v0.2.1 统计补充、历史阶段报告和交接文档仅保留审计价值；如有冲突，以本文件为准。

## 1. 项目目标

本项目将公开的 toehold-switch 高通量实验数据重构为逐靶标候选排序 benchmark，回答下列限定问题：

> 对训练阶段未出现的靶标，在固定实验预算 K 下，一个评分方法能否把实验上更有用的候选排在前面？

本项目不是新型传感器的湿实验论文，也不把回顾性排序等同于前瞻设计。核心贡献是评测单位、来源隔离、设计预算指标、证据语义分层和可复现执行链。

## 2. 冻结的一句话主张

公开 fused-trigger 数据可以被重构为 source-disjoint、逐靶标候选排序任务；该重构能揭示行级拆分的靶标重叠并量化固定预算下的方法效用，但不能证明前瞻性、跨上下文、真实 trans-sensing 或 de novo 设计有效性。

## 3. 证据轨道

### R1：canonical 逐靶标排序主轨道

- 主分析数据：52,861 条 admitted_paired 记录，来自 926 个有配对标签的靶标。
- provenance 保留表：92,731 条 virus/TF 记录、931 个靶标；不得把该规模写成主排行榜规模。
- 标签：有符号 ON − OFF；负值必须保留。
- 固定拆分：648 个训练、138 个验证、140 个测试靶标；训练与测试靶标重叠必须为零。
- 主终点：success@1。
- canonical 成功阈值：ON ≥ 0.5 且 OFF ≤ 0.5。
- 次要终点：success@3、success@5、NDCG@10、normalized regret@10、global Pareto-front coverage@10。
- 独立统计单位：靶标，而不是候选行或模型随机种子。
- 没有任何合格候选的测试靶标必须保留在分母中并单独报告。
- 学习型基线采用种子 0–4；论文分数为五个模型预测的逐行均值。

### R2：BEACON 来源重构轨道

- 数据：BEACON 权威映射的 91,534 行。
- 来源：23 个 virus、905 个 TF，以及一个 pooled random 来源组。
- 标签：BEACON 自身归一化 ON_OFF；不得与 R1 的 canonical ON − OFF 合并或互换。
- pooled random 来源组不形成可用的逐靶标候选集合，不进入排名评价。
- 轨道一：TF+virus 分层 source-disjoint mixed ranking。
- 轨道二：全部 TF 训练、全部 23 个 virus 测试的 domain-OOD ranking。
- 指标：target Spearman、NDCG@10、normalized regret@10 和 normalized regret@1。
- canonical 绝对成功阈值不得迁移到 BEACON。
- BEACON 原有行/QC 拆分保留为 published_row_split，仅用于泄漏审计；当测试靶标与训练重叠时，不得把其性能描述为 unseen-target generalization。

### R3：VISTA 配对上下文压力测试

- 数据：一个 mCherry 靶标、一个研究中的 189 个完整配对位点。
- 比较：同一位点在 truncated cognate target 与 full-length target 下的测量。
- 报告：两种测量的 Spearman、top-10 overlap、绝对秩变化，以及每个 scorer 对两种上下文的相关性和相关性差。
- 不确定性：位点自举只描述该 mCherry 靶标内的不确定性。
- 该轨道不是多靶标外部验证，不得推断普遍的 fused-to-full 迁移结论。

## 4. 随机基线

论文中的随机基线必须是每个靶标候选全集上均匀随机排列的解析期望，不得使用单个固定随机排列代替。

- success@K：无放回抽样中至少抽到一个合格候选的精确概率。
- expected NDCG：利用候选在排名位置上的可交换性计算。
- expected regret：使用有限总体无放回抽样最大值的次序统计量。
- expected Pareto coverage：每个全局 Pareto 前沿候选被 top-K 纳入的概率 K/N。
- 随机排序的期望 pooled Spearman 记为 0。
- 行级 score 文件可以保留 seed-0 随机列供审计，但不得用于论文指标、配对比较或主要结论。

## 5. 统计合同

- R1 和 R2 的均值及区间按靶标重采样；均值使用 2,000 次非参数自举。
- 方法差异使用逐靶标配对差值和 5,000 次配对自举。
- R3 使用 5,000 次 mCherry 位点内自举；不得将位点数解释成独立靶标数。
- 有限自举双侧尾概率采用 add-one 校正，任何结果不得报告 P = 0。
- 效应量和 95% CI 承担主要解释；P 值为探索性辅助结果。
- 本项目未做多重比较校正，论文不得暗示 family-wise 或 FDR 受控的验证性推断。
- 模型初始化种子不是生物学重复，也不是统计样本量。
- 主终点为 canonical success@1；不得因次要指标更有利而隐藏主终点结果。

## 6. 基线身份与实现要求

### 允许的基线身份

- exact random expectation；
- trigger GC rule；
- supplied Salis/MFE thermodynamic proxy；
- plain MLP；
- one-dimensional CNN；
- deeper CNN proxy；
- sequence + five local biophysical features；
- longer-trained local-feature proxy。

B3、B4、B5 等仓库基线只能描述为代表性 proxy，不得描述为 STORM、NuSpeak、SANDSTORM、Toehold-VISTA 或其他命名系统的完整复现。

### 必须保持的实现修正

1. CNN 输入必须为真实的 N × 4 × L 核苷酸通道张量。
2. canonical 回归必须保留有符号 ON − OFF。
3. 所有论文置信区间必须按正确独立单位重采样。
4. oracle 诊断必须保留全部测试靶标，并明确标注为不可提交方法。
5. Pareto 指标使用全候选集前沿覆盖率，或另行声明确定性规则。
6. local feature concatenation 不得称为 target-context ablation。
7. 方法 top-1 不一致只能称为 evaluator disagreement，不得无证据称为 proxy overfitting。
8. runner、schema、论文表格和 JSON 结果必须使用一致的指标与靶标计数。
9. BEACON 原拆分必须重命名为 published_row_split，新的 source-disjoint 字段独占 split 名称。
10. 图题、表注和替代文本必须与观察结果方向一致。

## 7. 允许主张

- prediction association 与逐靶标候选选择效用是两个不同的评价轴。
- source-disjoint 拆分是检验 unseen-target generalization 的必要条件。
- 本仓库基线可以在相同候选、输入和实验预算下进行回顾性比较。
- canonical MLP 和 deeper CNN proxy 在冻结的 success@1 上高于解析随机期望，效应大小以最终区间为准。
- 在本次八方法集合中，pooled prediction 与 NDCG 的方法排序一致；与 success@1 的排序高度但不完全一致。
- BEACON full-148-nt MLP 在重构的两个 source-disjoint 轨道中提高了 NDCG@10。
- VISTA 的 truncated 与 full-target 测量在该 mCherry 靶标上高度一致；当前 scorer 的相关性变化区间均跨越零。
- naive local feature concatenation 在本仓库实现中降低了 canonical 排名效用。

## 8. 禁止主张

- 行级靶标泄漏必然提高每个模型的性能。
- 52,861-row canonical 和 91,534-row BEACON 使用同一标签尺度。
- 一个 mCherry 靶标证明普遍的 full-target transfer 成功或失败。
- OFF 等同于生化特异性。
- 回顾性 fused-trigger 排名证明真实 trans sensing、de novo redesign 或前瞻 hit rate。
- 仓库 proxy 是任何命名已发表系统的完整复现。
- 当前结果构成新算法 SOTA。
- 未经前瞻实验即可宣称临床、诊断或部署有效性。
- 未做多重校正的探索性 P 值构成验证性显著性家族。
- 文献检索未发现相同 benchmark 等同于“全球首个”的证明。

## 9. 可复现执行与交付物

最低交付物包括：

1. 本 Markdown 控制合同；
2. 冻结 source manifests、provenance 表、exclusion ledger 和标签语义说明；
3. 可从准备好的数据一键执行的核心脚本；
4. runner 与统一 leaderboard schema；
5. 通过的单元测试与远端执行日志；
6. machine-readable JSON/CSV 结果；
7. 论文级 PDF/600-dpi PNG 图、source-data CSV、Markdown 表和 alt text；
8. 完整英文论文；
9. 独立统计审计；
10. 三份终审报告和一份综合编辑决定。

## 10. 投稿门槛

只有同时满足下列条件，项目才可被标记为“达到适配期刊的投稿就绪标准”：

1. v0.2.1 核心流程在目标服务器完整结束，且测试通过。
2. 所有正文数字来自同一最终结果包。
3. random 行和所有 paired-vs-random 比较均使用解析随机期望。
4. BEACON published split 的 TF 与 virus 靶标重叠审计进入机器可读结果和正文。
5. 没有 bootstrap probability 等于零。
6. 正文如实写出 prediction 与 NDCG 的观察到的一致方向，不保留旧假设。
7. 主结果明确报告 canonical success@1，不用次要终点替代。
8. 单靶标 VISTA、proxy baseline、fused assay、回顾性阈值、未做前瞻实验和未做多重校正等限制均在正文出现。
9. 图表通过视觉检查，不存在裁切、遮挡、错误轴域或结论方向不一致。
10. 三位审稿人的最终审查不存在阻断性的技术、统计、可复现性或主张越界问题。

“投稿就绪”只表示在当前证据边界内形成完整、诚实、可复现的稿件，不保证编辑送审、同行评议结果或最终接收。

## 11. 尚需作者提供的投稿元数据

以下内容不能由分析代理推断，投稿前必须由作者补齐：

- 作者姓名、单位、通讯作者和 ORCID；
- CRediT author contributions；
- funding 与 competing interests；
- 最终公共仓库 URL、提交版本 commit、许可证；
- 永久归档 DOI；
- VISTA workbook 的再分发许可或仅下载脚本策略；
- 目标期刊及其最新格式、字数、图表和数据政策。

