# ToeholdDesignBench v0.2.1 统计审计

审计日期：2026-08-21  
审计对象：最终远端结果包、指标实现、论文 v0.2.1  
结论：在当前“回顾性、逐靶标候选排序 benchmark”的主张边界内，未发现阻断性统计错误。下列解释限制必须保留。

## 1. 独立单位

- canonical 与 BEACON 的独立单位是 target/source。
- 候选行是同一靶标内的相关观测，不作为独立样本扩大 n。
- 模型随机种子只反映训练初始化；论文使用跨种子平均预测，不把五个种子当成五个实验重复。
- VISTA 的 189 个 site 全属于一个 mCherry 靶标。其区间是靶标内 site-bootstrap 区间，不是跨靶标泛化区间。

该处理与任务结构一致。正文和图表均报告 target 数，而不是只报告行数。

## 2. 主终点与分母

canonical 主终点在分析前冻结为 success@1，合格条件为 ON ≥ 0.5 且 OFF ≤ 0.5。140 个测试靶标全部进入分母，其中 12 个没有任何合格候选。保留这些靶标避免了只在“可成功”靶标上报告条件成功率的乐观偏差。

主结果：

- exact random expectation：0.275，95% CI [0.251, 0.302]；
- MLP：0.400，[0.321, 0.479]；paired Δ = 0.125，[0.048, 0.203]；
- deeper CNN proxy：0.357，[0.279, 0.436]；paired Δ = 0.082，[0.010, 0.157]；
- thermodynamic proxy：0.343，[0.264, 0.421]；paired Δ = 0.068，[−0.005, 0.143]。

因此正文正确地区分了“MLP/deeper CNN proxy 的主终点区间支持正差异”和“thermodynamic proxy 的主终点差异仍不确定”。

## 3. 随机基线

论文指标不再依赖单个随机种子。每个靶标使用均匀随机排列的解析期望：

- success@K 使用无放回超几何概率；
- NDCG 使用位置可交换性；
- regret 使用有限总体最大值次序统计量；
- Pareto coverage 使用 K/N 纳入概率。

逐靶标解析值随后按 target bootstrap 汇总，所以总体区间反映测试靶标组成的不确定性，而不是随机排列的 Monte Carlo 误差。Random 的期望 Spearman = 0 是理论参照，不是经验估计；成果表注已明确这一点。

## 4. 区间与配对比较

- 均值：2,000 次非参数 target bootstrap，percentile 95% CI。
- 方法差异：同一靶标上的 paired difference，5,000 次 target bootstrap。
- VISTA：5,000 次 site bootstrap。
- 有限自举尾概率使用 add-one 校正；结构化审计确认最终 canonical 与 BEACON 结果中所有 two_sided_bootstrap_p 均严格大于 0。
- 最小可报告双侧值约为 0.0004，与 5,000 次重采样一致。

配对设计优于把两个方法的独立区间相减，因为它保留了靶标难度的共同变化。

## 5. P 值解释与多重比较

当前 bootstrap P 值是基于有限重采样分布的探索性尾部摘要，不应被表述为预注册、严格零假设下的验证性检验。项目同时比较多个方法和多个次要终点，未执行 family-wise error 或 FDR 校正。

处理方式：

- 论文的主要解释依据效应量与 95% CI；
- success@1 是唯一冻结主终点；
- 次要指标与所有 P 值明确标为 exploratory；
- 正文不使用“多重校正后显著”或“confirmatory”措辞；
- 论文主叙事没有依赖 P 值阈值翻转。

若目标期刊要求验证性假设检验，应在投稿前另行冻结有限个对比、选择正式检验并做适当多重校正；当前稿件不作该主张。

## 6. 目标对齐分析

八个方法的 pooled prediction Spearman 与 mean target NDCG@10 的方法秩 Spearman = 1.00；与 success@1 的方法秩 Spearman = 0.881。方法数仅为 8，因此这些值作为描述性结果，不用小样本方法秩相关的 P 值支持普遍规律。

MLP 与 thermodynamic proxy 的 top-1 agreement = 0.114（16/140）。该指标说明两种 evaluator 常选择不同候选，但不证明任一方法过拟合，也不证明 prediction 与 design 必然背离。论文已按此边界表述。

## 7. BEACON

BEACON 与 canonical 的标签语义分离。source-disjoint mixed track 的 test n = 139 targets；TF-to-virus track 的 test n = 23 virus targets。两者的区间都按 target 重采样。

published split 审计结果：

- TF：903 个 train targets、773 个 test targets、772 个重叠，test overlap fraction = 0.9987；
- virus：23 个 train targets、23 个 test targets、23 个重叠，fraction = 1.0000。

这些数字足以证明该拆分不能被重新解释为 unseen-target 测试，但不证明泄漏一定提高任意模型指标。论文保留了这一因果边界。

## 8. VISTA

truncated 与 full-target 测量的 Spearman = 0.933，top-10 overlap = 0.60，median absolute rank shift = 12。五个 scorer 的 full-minus-truncated correlation difference 的 95% site-bootstrap CI 均跨越 0。

因此允许的结论是“在这个 mCherry 靶标中，未检测到 scorer 相关性的上下文依赖变化”，而不是“上下文无影响”或“普遍迁移失败”。原研究报告的绝对表达变化与本项目的秩相关压力测试不是同一个统计问题，不构成矛盾。

## 9. 缺失信息与投稿前作者动作

统计分析本身没有需要新增计算才能修复的阻断项。投稿前仍需由作者完成：

1. 根据目标期刊确定是否保留探索性 bootstrap P 值；即使删除，效应量和 CI 应保留。
2. 补齐作者、资金、利益冲突和贡献声明。
3. 确认 VISTA workbook 的再分发许可。
4. 若声称多靶标 full-target generalization 或前瞻 design validity，必须新增相应独立实验；当前数据不能通过再分析获得该证据。

