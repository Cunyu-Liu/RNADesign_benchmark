# ToeholdDesignBench terminology ledger v0.2.1

This ledger controls wording in the revised manuscript and paper artifacts.

| Preferred term | Meaning in this work | Do not replace with |
| --- | --- | --- |
| target or source | The full virus genome or human-TF-derived source sequence from which candidate trigger windows were generated | sample, replicate, or patient |
| candidate | One tested trigger/switch construct associated with a target | independently designed sensor |
| canonical track | The 52,861 paired, label-bearing canonical records with signed `ON - OFF` | the 91,534-row BEACON track |
| BEACON track | The separately normalized 91,534-row PRS reconstruction | an extension of the canonical label scale |
| VISTA stress test | Paired truncated/full measurements for 189 sites from one mCherry target | external multi-target validation |
| source-disjoint | No target/source identity crosses the specified training and test sets | sequence-nonredundant at every similarity threshold |
| candidate-ranking utility | Retrospective ability to prioritize experimentally measured candidates within an unseen target | de novo design validity or prospective hit rate |
| success@K | Whether at least one of the top K candidates meets `ON >= 0.5` and `OFF <= 0.5` in the canonical assay | biochemical specificity |
| exact random expectation | Analytic expectation over all uniformly random candidate permutations within each target | a fixed random seed or a Monte Carlo replicate |
| pooled prediction Spearman | Auxiliary row-pooled association between model score and label | the primary design endpoint |
| target NDCG@10 | Target-averaged ranking quality after a within-target relevance shift | success probability |
| normalized regret@10 | Normalized gap between the best available relevance and the best candidate in the top 10 | statistical regret bound |
| Pareto-front coverage@10 | Fraction of the global ON-high/OFF-low Pareto front recovered in the top 10 | Pareto-front size within the selected set |
| learned baseline ensemble | Mean prediction from independently initialized training seeds | biological replicate |
| deeper CNN proxy | Repository-defined two-convolution baseline | a reproduction of STORM, NuSpeak, or another named system |
| local biophysical feature concatenation | Five local supplied features concatenated to one-hot trigger sequence | target-context modeling |
| context agreement | Association between VISTA truncated- and full-target measurements | proof that target structure is irrelevant |
| exploratory bootstrap P value | Finite-resampling tail summary with add-one correction | multiplicity-controlled confirmatory evidence |

## Frozen claim boundary

The benchmark supports retrospective, source-isolated candidate-ranking claims
within the evaluated assays. It does not support biochemical specificity,
prospective hit rate, universal context transfer, trans-sensing performance, or
de novo design claims.
