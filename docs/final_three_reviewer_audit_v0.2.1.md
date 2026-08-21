# ToeholdDesignBench v0.2.1 三位审稿人终审包

审查日期：2026-08-21  
输入版本：docs/manuscript_v0.2.1.md、合并合同 v0.2.1、最终远端结果包、三张图及 source data、统计审计、测试与运行日志

## Review setup

### Input scope

本次审查覆盖完整英文稿、方法、结果、讨论、数据/代码可用性声明、图注、控制合同、机器可读结果和远端复现日志。作者姓名、单位、资金、贡献、利益冲突、永久 DOI、最终公共仓库 commit 和 VISTA 再分发许可尚未提供，均已在稿件中标为 AUTHOR_INPUT_NEEDED。

### Assessment boundary

审稿结论只评价当前稿件能否作为回顾性 benchmark / evaluation-audit 论文在适配的专业方法、计算生物学或合成生物学期刊发表。它不等同于编辑决定，也不表示该证据足以支持 Nature 级综合影响力、前瞻设计或真实完整靶 RNA 传感主张。

### Shared manuscript claim summary

论文主张公开 fused-trigger toehold 数据可被重构为 source-disjoint、逐靶标的候选排序 benchmark。该 benchmark 揭示行级拆分的靶标重叠，使用解析随机排序期望量化固定预算效用，并把 canonical、BEACON 和单靶标 VISTA 证据分层；论文明确不主张 prospective、cross-context、trans-sensing 或 de novo design validity。

### Visible evidence base

- canonical：52,861 paired records、926 label-bearing targets、648/138/140 target split；
- canonical test：7,041 rows、140 targets，其中 12 个无合格候选；
- BEACON：91,534 rows、905 TF sources、23 virus sources；
- VISTA：一个 mCherry target、189 paired sites；
- exact random expectation、target bootstrap、paired target bootstrap；
- 20 项本地测试通过；
- 远端完整流程成功结束并生成 JSON、CSV、Markdown tables、PDF/PNG figures、source-data CSV 和 alt text；
- 三张最终图已做视觉检查。

## Reviewer 1

*本报告最重视技术可靠性与在作者论证成立前必须修复的技术问题。*

### Overall assessment

修订稿已经从存在多项实质性错误的早期项目，转变为技术边界清楚、结果方向与数据一致的回顾性候选排序 benchmark。关键修正——有符号标签、正确 CNN 通道、target-level uncertainty、global Pareto coverage、解析随机期望、BEACON split collision 与 target-overlap audit、VISTA outcome-neutral interpretation——均进入代码、结果和正文。当前版本未发现会使核心结论失效的阻断性技术问题。

### Who would be interested in the results, and why

最直接的读者是 RNA 传感器设计、合成生物学、序列到功能建模和生物序列 benchmark 研究者。更广义的机器学习评测读者也会关心“行级预测任务如何被误读为组级决策任务”、group leakage 和预算相关 endpoint 的问题。

### Major strengths

1. 论文把评测单位从 candidate row 改为 target candidate set，并用显式 source manifest 验证训练/测试重叠。
2. canonical、BEACON 与 VISTA 标签系统没有被合并，避免了规模和语义混淆。
3. success@1 保留所有 140 个测试靶标，包括 12 个无可行候选的靶标。
4. 随机基线使用解析期望，不再受单一随机种子支配。
5. paired target bootstrap 与 target-level interval 对应任务的独立单位。
6. 负面结果被保留：thermodynamic proxy 的 success@1 区间不排除零差异；CNN 和 local-feature proxy 未优于随机；VISTA 未发现 scorer 的上下文相关性变化。
7. 代码、机器可读结果、runner、图表 source data 和日志形成完整证据链。

### Major concerns

当前最大限制不是实现错误，而是 baseline coverage。B3/B4/B5 是仓库 proxy，并未执行命名已发表系统的官方复现；因此论文不能提出算法 SOTA 或“全面比较现有设计器”。修订稿已经多次明确这一点，并将工作定位为 evaluation protocol/resource。对该定位而言，这是显著限制但不是阻断性错误。

canonical success 阈值 0.5/0.5 是操作性 benchmark 定义，并非经独立生物学验证的临床或设计阈值。稿件已把它称为 frozen、assay-specific operational threshold，并提供 threshold-free NDCG/regret 作为次要指标。只要不扩大生物学含义，该处理可以接受。

### Technical failings that need to be addressed before the case is established

没有剩余的可由当前数据和代码修复、且会阻断该限定论证的技术 failing。投稿前必须完成的是发布元数据和许可闭合，而非重新分析：

- 提供最终公共仓库 URL、提交 commit、许可证和永久归档 DOI；
- 确认 VISTA workbook 能否再分发，否则只发布获取脚本；
- 补齐作者、资金、贡献和 competing-interest 声明。

若作者希望把主张扩展为“当前最佳设计模型比较”或“真实 trans/full-target 设计有效”，则必须新增官方模型实现和前瞻/多靶标实验；当前稿件没有提出这些主张。

### Assessment against Nature-style criteria

- **Originality:** 评测协议和来源重构的组合具有可信的原创性；稿件没有宣称无法证明的“全球首个”。
- **Scientific importance:** 对专业领域的方法学重要性明确；尚不足以证明 outstanding、far-reaching 的 Nature 级重要性。
- **Interdisciplinary readership:** group leakage、decision-unit mismatch 和 budgeted selection 对其他生物序列任务具有可迁移启示，但当前实证集中于 toehold switches。
- **Technical soundness:** 在声明边界内成立；未发现阻断性错误。
- **Readability for nonspecialists:** fused-trigger 定义、三轨证据结构和图注已显著改善可读性。

### Recommendation posture

技术上支持在适配的专业 benchmark、计算生物学或合成生物学期刊投稿；需要完成行政元数据与许可，但不要求新增分析才能建立当前论证。若以 Nature 综合期刊为目标，则现有证据的广泛影响和前瞻验证不足。

## Reviewer 2

*本报告最重视原创性、科学重要性和相对于既有工作的定位。*

### Overall assessment

论文的价值不在提出更强模型，而在重新定义如何从公共高通量数据评估候选选择。修订稿与 Angenent-Mari 的 sequence-level prediction、Valeri 的 optimization/redesign、BEACON 的多任务 regression benchmark、Shen 等人的 mechanistic generalization 和 VISTA 的 target-aware design 做了合理区分。旧稿曾把“prediction 与 design 必然背离”和“fused-to-full 普遍迁移失败”作为头条；新稿根据最终证据撤回这些主张，这提升了可信度。

### Who would be interested in the results, and why

除 toehold/RNA synthetic biology 研究者外，构建高通量生物设计 benchmark 的研究者会关注本工作。它提供了一个具体案例：同一数据集在 row regression 与 group-isolated top-K selection 下回答不同问题，且随机基线必须随 group composition 变化。

### Major strengths

1. 创新点被约束为 task/evaluation design，而不是包装成新模型。
2. BEACON published split audit 提供清晰、可复核的数字：TF test overlap 99.87%，virus 100%。
3. 论文没有把 leakage 与 performance inflation 混为因果关系；canonical diagnostic 中两种弱模型没有受益也被如实报告。
4. canonical 主终点结果有实际可解释的效应量：MLP 相对随机期望提高 12.5 个百分点。
5. “prediction 与 NDCG 方法排序完全一致”的结果与最初假设相反，但被保留为主要观察，而不是选择性隐藏。
6. 讨论把该 benchmark 与 prospective design、intact-target recognition、specificity 的未来证据需求连接起来。

### Major concerns

本工作的 scientific importance 主要是 field-local evaluation hygiene，而非新的 RNA mechanism 或设计突破。只有一个 VISTA mCherry target，且没有新的湿实验；因此其跨上下文和生物学发现不应成为期刊选择的主要卖点。稿件已把 VISTA 降级为 single-target stress test，这是正确的。

文献检索只能支持“在定向检索中未发现相同组合”，不能证明 priority。稿件采用了这种限定措辞并明确“不据此声称 first”，已消除阻断性 novelty overclaim。

### Technical failings that need to be addressed before the case is established

没有发现会推翻当前 evaluation-resource 论证的缺失分析。更强的 official baseline suite、多阈值敏感性图和多靶标外部验证会提高论文上限，但在稿件不提出 SOTA、阈值普适性或外部泛化主张的前提下，它们属于扩展工作，不是当前论证的必需修复。

### Assessment against Nature-style criteria

- **Originality:** evaluation unit、source reconstruction、exact random expectation 和 evidence-track separation 的组合具有原创性。
- **Scientific importance:** 对 benchmark 和 RNA design evaluation 有明确价值；没有达到“outstanding scientific importance”的证据。
- **Interdisciplinary readership:** 可与其他 grouped biological design tasks 类比，但正文尚未在多个领域验证这种可迁移性。
- **Technical soundness:** 主张与证据匹配。
- **Readability for nonspecialists:** 中心问题清楚；摘要仍含较多数字，但已压缩至约 250 词并保留必要结果。

### Recommendation posture

支持向专业方法/资源类期刊投稿。对 broad, general-interest journal 的编辑吸引力可能有限，这属于意义和期刊匹配问题，不是论文技术不可发表。

## Reviewer 3

*本报告最重视跨领域读者是否能理解工作，以及论证和图文是否自洽。*

### Overall assessment

修订稿现在有清楚的叙事顺序：为什么 row prediction 不等于 target selection；如何分开三套数据；source overlap 有多大；在正确 split 下哪些方法在什么预算上有效；哪些结论不能从 VISTA 单靶标推出。语言总体直接，限制没有藏在补充材料。

### Who would be interested in the results, and why

合成生物学实验者能用 success@K 理解“需要做几个实验”；机器学习读者能用 group leakage 和 rank metrics 理解评测风险；benchmark 维护者会关注 source manifest、runner 和 data provenance 的组织方式。

### Major strengths

1. 标题准确，没有暗示新算法或前瞻设计。
2. 摘要同时报告数据规模、split leakage、主终点和主要限制。
3. fused-trigger context 已在 Introduction 中为非专业读者定义。
4. 每个结果段落都说明了“这个数字能说明什么”和“不能说明什么”。
5. 三张图使用完整有界轴域、冗余 marker/color 编码、source data 和 alt text；没有裁切或遮挡。
6. Figure legends 已补齐，并明确 random 的理论性质、BEACON 标签语义和 VISTA 单靶标限制。

### Major concerns

专业术语仍然较多，尤其是 NDCG、normalized regret 和 Pareto coverage。Methods 给出了定义，结果表也直接列出 success@1，因此不会阻止理解。若目标期刊面向更广泛读者，可在投稿版增加一张简洁 schematic，显示“source → candidates → source-disjoint split → top-K evaluation”的流程；这是可读性增强项，不是当前可发表性的技术门槛。

论文包含较多精确数值。它们对 benchmark 论文必要，但具体期刊可能要求把部分次要结果移入补充材料。期刊尚未选择，因此不能提前决定最终字数和表格布局。

### Technical failings that need to be addressed before the case is established

没有发现图文不一致或不可理解到足以阻断论证的问题。投稿前只需根据目标期刊完成格式适配，并补齐 AUTHOR_INPUT_NEEDED 字段。若期刊要求 graphical abstract，可基于现有三轨结构制作，不需要改变分析。

### Assessment against Nature-style criteria

- **Originality:** 对评测流程的原创性表达清楚。
- **Scientific importance:** 专业读者价值明确；一般读者影响依赖将 group leakage 与其他生物设计问题连接起来。
- **Interdisciplinary readership:** 基本问题可迁移，但实证范围较窄。
- **Technical soundness:** 图、表、文字方向一致，限制充分。
- **Readability for nonspecialists:** 目前可读；可选 schematic 会进一步降低门槛。

### Recommendation posture

支持专业期刊投稿。建议选定期刊后做一次格式和摘要适配；这不改变“当前科学论证已经成立”的判断。

## Cross-review synthesis

### Consensus strengths

三位审稿人一致认为，v0.2.1 已解决早期版本的核心正确性问题，并形成可审计的 benchmark 论文：

- 证据轨道和标签语义分开；
- source-disjoint evaluation 与 published row-split audit 都有机器可读证据；
- canonical 主终点、完整分母和解析随机期望得到一致使用；
- 统计独立单位、区间和探索性 P 值边界清楚；
- 旧假设与真实结果冲突时，稿件选择了真实结果；
- 图表、source data、alt text、runner 和日志闭合；
- 限制覆盖 fused assay、proxy baseline、single-target VISTA、retrospective threshold、no prospective validation 和 no multiplicity correction。

### Consensus technical risks

当前没有阻断性技术风险。剩余风险均由主张边界或作者侧投稿动作控制：

1. official published model coverage 不完整，因此不得声称 SOTA 或全面排行榜；
2. threshold 是 assay-specific operational definition，因此不得声称普适生物阈值；
3. VISTA 只有一个 target，因此不得声称跨靶标 context generalization；
4. 没有 prospective experiment，因此不得声称 de novo design 或真实 hit rate；
5. 未做多重校正，因此 P 值只能探索性使用；
6. VISTA 许可、公共仓库版本和投稿元数据仍需作者闭合。

### Where emphasis differs across reviewers

Reviewer 1 最关注技术证据链，认为当前限定论证无阻断项。Reviewer 2 认为主要不确定性是科学影响力和期刊层级，而非正确性。Reviewer 3 认为稿件已可读，流程 schematic 是面向更广读者的可选增强。

### Broad-interest / significance readout

该工作有明确的专业方法学价值，也提供了可迁移的 group leakage 案例；但当前数据不足以支持 Nature 级“outstanding、immediate and far-reaching”影响。三位审稿人均认为这不影响其在适配专业期刊中的可发表性。

### Most important issues to resolve before submission

不需要新增计算分析来建立当前稿件的科学论证。正式投稿前必须完成：

- 选择目标期刊并按其最新要求适配格式；
- 补齐作者、单位、ORCID、CRediT、funding 和 competing interests；
- 冻结并公开最终仓库 commit，建立永久归档 DOI；
- 确认 VISTA 数据再分发策略；
- 确保提交包使用本次最终 v0.2.1 结果和图表，而不是任何历史 v0.1 数字。

## Risk / unsupported claims

以下主张在当前证据中不受支持，且终稿已经避免：

- “全球首个 target-aware toehold benchmark”；
- “prediction accuracy 与 design utility 普遍背离”；
- “row leakage 必然提高模型性能”；
- “fused-to-full transfer 普遍失败”；
- “OFF 测量代表 specificity”；
- “仓库 proxy 完整复现命名已发表系统”；
- “当前方法达到 SOTA”；
- “回顾性结果证明 prospective/de novo/trans-sensing validity”；
- “探索性 P 值经过多重比较控制”。

无法从现有材料评估并需作者补齐：作者身份与贡献、资金和利益冲突、VISTA 再分发许可、公共 release 状态、目标期刊适配。除这些投稿元数据外，本次三审没有未解决的阻断性技术或主张边界问题。

