# ToeholdDesignBench: source-disjoint candidate ranking for public toehold-switch assays

**Authors:** AUTHOR_INPUT_NEEDED  
**Affiliations:** AUTHOR_INPUT_NEEDED  
**Corresponding author:** AUTHOR_INPUT_NEEDED

## Abstract

High-throughput assays and sequence-to-function models have expanded the scale of
toehold-switch characterization, but pooled prediction metrics do not directly
measure whether a method can select useful candidates for an unseen RNA target
under a fixed experimental budget. We introduce ToeholdDesignBench, a
retrospective, source-disjoint candidate-ranking benchmark reconstructed from
public data. Three evidence tracks are kept separate: 52,861 canonical paired
records from 926 label-bearing targets; a 91,534-row BEACON reconstruction with
separately normalized labels; and 189 paired truncated/full measurements from
one VISTA mCherry target. A row-random canonical diagnostic shared training
targets with 99.94% of test target groups. The published BEACON split shared 772
of 773 test TF targets and all 23 test virus targets with training. Under a
frozen source-disjoint canonical split, an MLP selected a threshold-qualified
top candidate for 40.0% of 140 test targets, versus an exact uniform-random
expectation of 27.5% (paired difference 0.125, 95% target-bootstrap CI 0.048 to
0.203). A deeper CNN proxy reached 35.7% (difference 0.082, 95% CI 0.010 to
0.157). Across eight methods, pooled prediction correlation and target NDCG@10
had identical method ordering (Spearman rho = 1.00), while ordering by success@1
was similar but not identical (rho = 0.881). In BEACON, a full-148-nt MLP
improved NDCG@10 over random expectation in source-disjoint mixed and
TF-to-virus evaluations by 0.155 (0.135 to 0.175) and 0.156 (0.112 to 0.200),
respectively. VISTA truncated- and full-target measurements were highly
rank-correlated (rho = 0.933), and no scorer showed a supported change in
correlation between contexts. The benchmark reveals split leakage and
budget-specific method utility without claiming prospective, cross-context, or
de novo design validity.

## Introduction

Toehold switches are programmable prokaryotic riboregulators in which binding of
a cognate trigger RNA opens a designed hairpin and exposes the translation
initiation region. The original architecture established wide dynamic range,
orthogonality, and programmability across experimentally tested switches
[[1]](#ref-1). Subsequent design tools combined sequence rules and predicted
thermodynamics to enumerate and rank candidate switches for a target RNA
[[2]](#ref-2). These systems made candidate prioritization a practical part of
the design-build-test cycle.

Large pooled assays changed the scale of the problem. Angenent-Mari and
colleagues characterized 91,534 paired toehold switches spanning 23 viral
genomes and 906 human transcription factors, and reported that deep neural
networks substantially improved sequence-level prediction over thermodynamic
and kinetic models [[3]](#ref-3). Valeri and colleagues developed STORM and
NuSpeak and experimentally evaluated model-guided optimization and redesign
[[4]](#ref-4). More recent work has shown that mechanistic features can improve
generalization across sequence-library regions even when they are not the most
accurate representation for local prediction [[5]](#ref-5), and Toehold-VISTA
has explicitly integrated switch and target structural features for target-aware
sensor design [[7]](#ref-7). Together, these studies establish both the value of
sequence-to-function modeling and the importance of context.

In the high-throughput assay used for the canonical and BEACON tracks, each
cognate trigger was encoded in the same construct upstream of its switch and
separated by a linker. We call this the fused-trigger context. It enables pooled
measurement but does not reproduce recognition of a separately expressed,
full-length target RNA.

The evaluation unit, however, determines what a reported performance number can
support. A pooled coefficient of determination or row-level correlation asks
whether individual assay values are predicted across a collection of constructs.
A design-budget question instead asks whether, for a target not represented in
training, the highest-ranked one, three, or ten candidates include a useful
construct. Adjacent windows from the same source share target identity and local
sequence context. If they are divided across training and test rows, an apparent
test set does not represent unseen-target generalization. BEACON broadened RNA
model evaluation to 13 tasks and included programmable RNA switches as a
sequence-level regression task, using R-squared as the task metric
[[6]](#ref-6). It did not aim to define a target-isolated candidate-selection
benchmark.

We therefore asked a narrower question: can public fused-trigger assay data be
reconstructed into a reproducible, source-disjoint candidate-ranking task whose
metrics correspond to fixed experimental budgets? A targeted literature review
identified related prediction, design, target-structure, and RNA-benchmark work,
but did not identify the same combination of source-level isolation, per-target
top-K utility, and explicit separation of assay label systems. We do not use this
bounded search to claim priority. Instead, we contribute an auditable task
definition, source manifests, exact random-ranking expectations, target-level
uncertainty, and a runner that evaluates submitted score files against the same
candidates.

The benchmark has three evidence tracks. The canonical track evaluates signed
ON − OFF ranking under a frozen source-disjoint split. The BEACON track audits
the target overlap in its published row/QC split and evaluates newly constructed
source-disjoint and TF-to-virus tracks without merging label scales. The VISTA
track compares scorer behavior against paired truncated- and full-target
measurements for one mCherry target. This structure lets each dataset answer the
question supported by its experimental context.

## Results

### Reconstructing targets changes the evaluation unit

The canonical source table contained 97,436 rows. We excluded 4,705
random-sequence controls from target ranking and retained 92,731 virus- or
TF-derived records across 931 targets. Of these, 52,861 records from 926 targets
had paired ON and OFF measurements and entered the main ranking analysis; 27,439
single-label and 12,431 no-label records remained in the provenance accounting
but were not assigned inferred paired outcomes. The paired outcome was the
signed difference ON − OFF; 7,428 paired values were negative and were retained.
Absolute source coordinates were reconstructed for 87,989 of 92,731 retained
records, while 4,742 unresolved coordinates remained explicitly marked rather
than being imputed.

We froze a target/source-disjoint split of 648 training, 138 validation, and 140
test targets. It contained no target overlap between training and test. By
contrast, a row-random diagnostic had a test-target overlap fraction of 0.99943.
This structural leakage did not increase pooled correlation for the two weak
diagnostic models: averaged over three seeds, MLP pooled Spearman correlations
were 0.0685 under source isolation and 0.0673 under row-random splitting, while
CNN correlations were −0.0874 and −0.0882. Thus the split audit establishes that
row-random evaluation does not test unseen targets; it does not establish that
leakage must inflate every model.

The same distinction appeared in BEACON. The authoritative mapping associated
the 91,534 rows with 905 TF sources, 23 virus sources, and one pooled
random-sequence group. In the published row/QC split, 772 of 773 test TF targets
(99.87%) and all 23 test virus targets also occurred in training. We preserved
this published split as a provenance field and constructed a separate
target-level split for ranking. The random-source group was excluded because it
does not define multiple within-target candidate sets.

### Canonical ranking reveals primary-endpoint gains for two learned baselines

The canonical test set contained 7,041 records from 140 targets. A target was a
success at budget K if at least one of its top-K candidates satisfied the frozen
threshold ON ≥ 0.5 and OFF ≤ 0.5. This threshold is specific to the canonical
assay and was not transferred to BEACON or VISTA. Twelve test targets had no
threshold-qualified candidate; they were retained and necessarily contributed
failure to success@K.

The paper-facing random baseline was the exact expectation over all uniformly
random candidate permutations within each target. Its expected success@1 was
0.275 (95% target-bootstrap CI 0.251 to 0.302), success@3 was 0.597 (0.554 to
0.640), and NDCG@10 was 0.652 (0.631 to 0.671). These values differ from one
seeded random ranking because the number of candidates and qualified candidates
varies by target.

The five-seed MLP ensemble achieved success@1 of 0.400 (0.321 to 0.479), a
paired increase of 0.125 over the exact random expectation (0.048 to 0.203).
The deeper CNN proxy achieved 0.357 (0.279 to 0.436), a paired increase of 0.082
(0.010 to 0.157). The thermodynamic proxy achieved 0.343 (0.264 to 0.421), but
its primary paired difference of 0.068 had an interval crossing zero (−0.005 to
0.143). The simple CNN, GC rule, and both local-feature concatenation baselines
did not improve success@1 over the exact random expectation. The MLP also had
the highest observed success@1, while the deeper CNN proxy had the highest
NDCG@10 and lowest normalized regret@10 among the evaluated canonical methods
(Table 1). Because secondary endpoints and methods were not
multiplicity-corrected, their bootstrap P values are treated as exploratory and
effect intervals carry the interpretation.

**Table 1 | Canonical source-disjoint test performance.** Intervals resample 140
targets. The Random row is an exact per-target expectation, not a sampled
permutation. Pooled prediction Spearman is auxiliary.

| Method | Pooled Spearman | Success@1 (95% CI) | Success@3 (95% CI) | NDCG@10 (95% CI) | Normalized regret@10 (95% CI) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Exact random expectation | 0.000 | 0.275 (0.251–0.302) | 0.597 (0.554–0.640) | 0.652 (0.631–0.671) | 0.085 (0.074–0.097) |
| GC rule | −0.200 | 0.129 (0.079–0.186) | 0.357 (0.271–0.436) | 0.575 (0.546–0.602) | 0.144 (0.115–0.172) |
| Thermodynamic proxy | 0.136 | 0.343 (0.264–0.421) | 0.700 (0.621–0.779) | 0.687 (0.662–0.712) | 0.085 (0.067–0.106) |
| MLP | 0.162 | 0.400 (0.321–0.479) | 0.757 (0.686–0.821) | 0.706 (0.680–0.730) | 0.049 (0.035–0.065) |
| CNN | −0.045 | 0.221 (0.157–0.293) | 0.579 (0.493–0.664) | 0.647 (0.619–0.675) | 0.088 (0.069–0.109) |
| Deeper CNN proxy | 0.208 | 0.357 (0.279–0.436) | 0.764 (0.693–0.836) | 0.716 (0.692–0.738) | 0.042 (0.029–0.056) |
| Sequence + local biophysics | −0.124 | 0.250 (0.179–0.329) | 0.500 (0.414–0.586) | 0.618 (0.591–0.644) | 0.125 (0.100–0.151) |
| Longer-trained local proxy | −0.047 | 0.229 (0.164–0.300) | 0.564 (0.486–0.650) | 0.637 (0.612–0.663) | 0.107 (0.085–0.129) |

### Prediction and target NDCG align at the method level, while selected candidates differ

The distinction between prediction and selection is a task definition, not a
guarantee that the two axes will disagree empirically. Across all eight
canonical methods, the method-rank Spearman correlation between pooled
prediction Spearman and mean target NDCG@10 was 1.00. The corresponding
correlation with success@1 was 0.881. The revised result therefore does not
support the superseded hypothesis that prediction and target-ranking method
orders generally diverge in this baseline suite (Fig. 1).

Alignment of aggregate method ordering did not imply that methods chose the
same candidates. The MLP and thermodynamic proxy selected the same top-ranked
record in only 16 of 140 targets (11.4%). Their success@1 values were 0.400 and
0.343, respectively, and the thermodynamic proxy's primary contrast with random
was uncertain. This combination illustrates why reporting both aggregate
prediction association and budget-specific selection outcomes is informative:
methods can occupy similar regions of an aggregate leaderboard while proposing
different experiments.

An oracle diagnostic quantified task headroom without treating labels as a
deployable method. Among the 140 test targets, 128 had at least one feasible
candidate. Retrospectively ranking by the observed signed ON − OFF value gave
unconditional success@1 of 0.907; ON-only and OFF-only oracles gave 0.714 and
0.086, respectively, and a deterministic Pareto-lexicographic oracle gave 0.800.
These values show that the primary threshold is not unattainable, while also
confirming that OFF alone is not a specificity surrogate and that no method can
succeed on the 12 infeasible targets.

### Naive local-feature concatenation reduces canonical ranking utility

We tested whether appending five supplied local features—trigger GC content,
the Salis ON/OFF proxy, switch MFE in OFF and ON configurations, and trigger
MFE—to the one-hot trigger representation improved ranking. It did not. Relative
to the sequence-only MLP, the 15-epoch local-feature MLP reduced success@1 by
0.150 (95% CI −0.243 to −0.050) and NDCG@10 by 0.088 (−0.112 to −0.064).
Extending training to 20 epochs reduced success@1 by 0.171 (−0.271 to −0.071)
and NDCG@10 by 0.069 (−0.091 to −0.046). This finding is limited to naive local
feature concatenation and these architectures. It does not contradict evidence
that deliberately selected mechanistic representations can improve
cross-library generalization [[5]](#ref-5), nor does it test full-target
structural context.

### Source-disjoint BEACON tracks separate input length and domain shift

BEACON's separately normalized ON_OFF outcome was evaluated without the
canonical absolute success threshold. The source-disjoint mixed track trained on
44,891 rows from 650 targets and tested on 34,075 rows from 139 targets, with
zero target overlap. The exact random expectation for mean target NDCG@10 was
0.591 (0.572 to 0.609). A first-30-nt MLP reached 0.611 (0.583 to 0.638), a
paired difference of 0.020 (0.001 to 0.040). A full-148-nt MLP reached 0.746
(0.724 to 0.769), a difference of 0.155 (0.135 to 0.175). The first-30-nt CNN
reached 0.577 (0.549 to 0.605), and its contrast with random crossed zero.

The TF-to-virus track trained on all 47,005 mapped TF rows from 905 sources and
tested on 40,824 rows from all 23 virus sources. Random expected NDCG@10 was
0.524 (0.517 to 0.531). The first-30-nt MLP reached 0.575 (0.544 to 0.606), a
paired difference of 0.051 (0.020 to 0.083), and the full-148-nt MLP reached
0.679 (0.636 to 0.726), a difference of 0.156 (0.112 to 0.200). The first-30-nt
CNN and full-sequence GC rule performed below the random expectation. These
results show that the reconstructed source identity supports a stricter ranking
question and that additional sequence context was useful for this MLP. They do
not establish prospective sensing of intact viral RNA because the underlying
BEACON assay uses fused triggers (Fig. 2).

**Table 2 | BEACON mean target NDCG@10.** Labels are BEACON-normalized and are
not on the canonical signed scale. Intervals resample targets.

| Method | Source-disjoint mixed, 139 targets | TF-to-virus, 23 targets |
| --- | ---: | ---: |
| Exact random expectation | 0.591 (0.572–0.609) | 0.524 (0.517–0.531) |
| Full-sequence GC | 0.472 (0.442–0.500) | 0.364 (0.325–0.402) |
| MLP, first 30 nt | 0.611 (0.583–0.638) | 0.575 (0.544–0.606) |
| CNN, first 30 nt | 0.577 (0.549–0.605) | 0.432 (0.388–0.476) |
| MLP, 148 nt | 0.746 (0.724–0.769) | 0.679 (0.636–0.726) |

### A single-target VISTA stress test supports measurement agreement, not a context-dependent scorer shift

The VISTA study tiled switches across an mCherry transcript and measured the
same sites with truncated and full-length cognate targets [[7]](#ref-7). After
complete-case selection, 189 paired sites entered our stress test. The two
experimental outcome rankings were highly concordant (Spearman rho = 0.933),
their top-10 sets overlapped by 60%, and the median absolute rank shift was 12
positions.

None of the five scorers had a supported change in its correlation between the
two outcome contexts. For the fused-trained MLP applied to the first 30 nt, the
full-minus-truncated correlation difference was 0.000 (95% within-target
site-bootstrap CI −0.053 to 0.055). For the last 30 nt it was −0.047 (−0.098 to
0.005); for the supplied tsgen2 rank, 0.028 (−0.023 to 0.078); for first-30-nt
GC, 0.030 (−0.022 to 0.080); and for a fixed random score, −0.004 (−0.060 to
0.051). Absolute scorer performance was weak for the learned and tsgen2 scores:
the first-30-nt fused MLP correlated −0.071 with both contexts, the last-30-nt
MLP correlated −0.171 and −0.218, and tsgen2 correlated −0.257 and −0.228.
First-30-nt GC correlated 0.273 and 0.303. Because all sites belong to one target
and study, these intervals quantify only within-mCherry uncertainty. The
analysis neither demonstrates universal transfer failure nor negates VISTA's
broader mechanistic and prospective results (Fig. 3).

## Discussion

ToeholdDesignBench changes the unit of evaluation from rows to target-specific
candidate sets. That change has three practical consequences. First, source
identity must be reconstructed and isolated to support an unseen-target claim.
The canonical row-random diagnostic and BEACON published-split audit show that
row-level partitions can share nearly every test target with training. Second,
the random reference depends on each target's candidate pool and feasible-hit
count. An exact per-target expectation avoids conclusions that hinge on a lucky
or unlucky random permutation. Third, the endpoint should reflect the intended
experimental budget. Success@1 asks a different question from NDCG@10 or pooled
correlation, even when the evaluated methods order similarly on average.

The central empirical result is deliberately narrower than the project's
original hypothesis. Pooled prediction correlation and mean target NDCG@10
ordered the evaluated canonical methods identically. We therefore find no
evidence for a general prediction-versus-ranking reversal in this suite. At the
same time, the MLP produced a supported 12.5-percentage-point gain over random
expectation on the frozen primary endpoint, and the deeper CNN proxy produced a
smaller supported gain. The thermodynamic proxy was useful at budgets of three
and ten, but its success@1 difference was uncertain. Method choice thus remains
budget-dependent even without a broad ordering reversal.

The BEACON reconstruction adds scale and a domain-oriented test while preserving
label semantics. The large target overlap in its published split is not an error
for its stated sequence-regression task; it becomes a problem only if that split
is reinterpreted as evidence for unseen-target selection. Under the new splits,
the 148-nt MLP clearly outperformed shorter inputs in both mixed and TF-to-virus
ranking. This result is compatible with sequence context carrying useful signal,
but it does not identify the causal sequence region and does not substitute for
intact-target experiments.

The VISTA stress test provides an external context check with a different assay
design. Our reanalysis found high agreement between truncated- and full-target
outcome rankings and no supported context-dependent change in any scorer's
correlation. This outcome corrects the earlier, overgeneralized narrative of
universal fused-to-full transfer failure. It also leaves an important negative
result: the fused-trained MLP and tsgen2 scores ranked these mCherry sites poorly
in both contexts. More targets would be required to separate a model failure, a
target-specific phenomenon, and a systematic context effect.

Several limitations bound the paper. All ranking results are retrospective and
reuse experimentally measured candidate libraries. The canonical and BEACON
assays fuse trigger and switch, so neither track measures hybridization to intact
RNA targets. OFF is leak expression without the cognate trigger, not biochemical
specificity. The absolute canonical threshold is operational and assay-specific.
The stronger named systems in prior work are not fully reproduced here; B3, B4,
and B5 are repository-defined proxies, and conclusions apply only to the
evaluated implementations. The source-disjoint split prevents exact target
identity overlap but is not a guarantee of independence at every possible
sequence-similarity threshold. The public data have been available since 2020,
so future external submissions must disclose prior exposure. VISTA contributes
only one mCherry target, and its site bootstrap must not be read as cross-target
uncertainty. Finally, the exploratory family of secondary metrics and method
contrasts was not adjusted for multiplicity.

These limitations also define the next experiments. A stronger benchmark would
add multiple intact-target datasets with harmonized provenance, predeclare a
primary external endpoint, and evaluate contemporary published models under
their official implementations. Prospective validation should select candidates
before measurement, include cognate and noncognate controls, and report hit rate
at a frozen budget. Such work is necessary before claims about de novo design,
specificity, or real-target sensing are warranted.

## Methods

### Study design and evidence separation

The controlling protocol was ToeholdDesignBench contract v0.2 plus statistical
addendum v0.2.1. It defined three nonmergeable evidence tracks. R1 used canonical
paired ON and OFF values and a signed ON − OFF label. R2 used the separately
normalized BEACON ON_OFF label. R3 used paired VISTA truncated- and full-target
measurements. No outcome was transformed to make its scale comparable across
tracks, and canonical success thresholds were used only in R1.

### Canonical data reconstruction

The canonical source was the public Angenent-Mari high-throughput toehold-switch
dataset [[3]](#ref-3). Random-sequence controls were excluded from target
ranking because they form no biological source target. Virus and human-TF-
derived records were grouped by their reconstructed source sequence. Records
were classified as paired, single-label, or no-label; only paired records with a
finite signed ON − OFF entered R1. Trigger windows were exactly matched to
source sequences to reconstruct coordinates. Unresolved coordinates were marked
no_coord and retained in provenance accounting. The resulting data table,
source map, exclusion ledger, and study-context registry were versioned together.

### Splits and leakage diagnostics

The frozen canonical manifest assigned 648 targets to training, 138 to
validation, and 140 to test, with no target identifier crossing partitions. A
row-random split was generated only as a diagnostic. For each split we measured
the fraction of test target identities also present in training. Diagnostic MLP
and CNN models were trained with seeds 0, 1, and 2 under both partitions using a
training-row count matched to the smaller source-disjoint training set. These
models were used to test whether leakage inflated their pooled and target-level
correlations; the overlap fraction itself was the evidence about whether the
partition represented unseen targets.

For BEACON, the distributed split field was renamed published_row_split. Source
sequences were assigned to a new deterministic stratified 70/15/15 manifest
within TF and virus categories (random seed 0). The source-disjoint mixed track
used manifest training and test targets. The domain track trained on all TF
sources and tested on all virus sources. Target overlap was checked directly.
The pooled random-source category was not ranked.

### Canonical outcomes and metrics

The primary endpoint was success@1. A candidate was threshold-qualified when
ON ≥ 0.5 and OFF ≤ 0.5; a target-level success@K value was one when any of the
top K ranked candidates qualified and zero otherwise. Targets with no qualified
candidates were included. Secondary endpoints were success@3, success@5,
NDCG@10, normalized regret@10, and global Pareto-front coverage@10.

For NDCG, relevance was the signed ON − OFF value shifted by the minimum value
within each target, preserving within-target order while avoiding silent
clipping of negative outcomes. Normalized regret was (best available − best in
top K) / (best available − worst available), with zero assigned to constant-
outcome targets. Pareto-front coverage was the fraction of the global candidate-
set front recovered in the top 10 when maximizing ON and minimizing OFF. Ties
in submitted scores were resolved deterministically by record identifier.

### Exact random-ranking reference

For every target, we calculated the analytic expectation over all uniformly
random permutations. Success@K used the probability of drawing at least one
qualified candidate without replacement. Expected DCG followed from
exchangeability of candidates across ranks and was divided by the target's
fixed ideal DCG. Expected regret used the finite-sample distribution of the
maximum among K draws without replacement. Every global Pareto-front member had
inclusion probability min(K,N)/N, giving expected coverage. The expected pooled
Spearman correlation was set to zero. A seed-0 random score column was retained
only for row-level audit and was never used in paper metrics or paired
comparisons.

### Canonical baselines

All learned baselines were trained from scratch on canonical training targets to
predict signed ON − OFF, using mean squared error and Adam with learning rate
0.001. Trigger sequences were encoded as 30 positions with four nucleotide
channels. The MLP flattened this representation and used hidden layers of 64
and 32 units with ReLU activations. The CNN used a 64-channel width-5
convolution, adaptive average pooling, and a 32-unit hidden layer. The deeper CNN
proxy used consecutive 64-channel width-5 and 128-channel width-3 convolutions,
adaptive average pooling, and a 64-unit hidden layer. The local-feature models
concatenated five supplied biophysical values to the flattened one-hot sequence
and used the same MLP hidden layers. Learned models ran for 15 epochs, except
the longer local proxy, which ran for 20. Each paper-facing learned score was
the mean prediction from seeds 0–4.

Nonlearned methods were trigger GC fraction and a thermodynamic proxy using the
supplied Salis ON/OFF feature, with the supplied switch-OFF MFE used when that
feature was zero or missing. These repository baselines sample broad method
families; they are not complete reproductions of STORM, NuSpeak, Toehold-VISTA,
or other named published systems.

### BEACON models and metrics

BEACON models predicted its normalized ON_OFF value. The first-30-nt MLP had
128- and 64-unit hidden layers. The first-30-nt CNN used 64-channel width-7 and
width-5 convolutions, adaptive average pooling, and a 32-unit hidden layer. The
full-context MLP used the same hidden sizes on a flattened 148-nt one-hot input.
Models were trained for 12 full-batch epochs with Adam at learning rate 0.001
and averaged across seeds 0–2. The GC rule used the full 148-nt sequence.
Metrics were target Spearman correlation, NDCG@10, normalized regret@10, and
normalized regret@1. Canonical absolute thresholds were not applied.

### VISTA paired context stress test

The VISTA workbook was read from its calculated-values sheet. Complete cases
required a trigger sequence and both ON OFF Truncated and ON OFF Full values,
leaving 189 sites. A canonical fused-trained MLP was fitted for 20 epochs with
seeds 0–4 and applied separately to the first and last 30 nt of each VISTA
trigger sequence. Additional scorers were negative supplied tsgen2 rank,
first-30-nt GC fraction, and one seed-0 random score used as a diagnostic. We
reported Spearman correlation with each context, the full-minus-truncated
correlation difference, top-10 overlap with each context's observed ranking,
experimental top-10 overlap between contexts, and median absolute rank shift.

### Statistical analysis

Targets were the independent resampling unit for canonical and BEACON estimates.
We used 2,000 nonparametric bootstrap samples for means and percentile 95%
intervals. Method contrasts used paired target differences with 5,000 bootstrap
samples. Two-sided finite-bootstrap tail probabilities used an add-one
correction and had minimum attainable reported value approximately 0.0004.
Effect estimates and confidence intervals were primary; P values for the family
of method and secondary-endpoint contrasts were exploratory and were not
multiplicity-adjusted. Model seeds quantified training initialization
sensitivity and were not treated as independent experimental observations.
VISTA used 5,000 site-bootstrap samples within one mCherry target; its intervals
do not estimate cross-target variability.

All analyses used Python 3.10.20. Learned models used PyTorch 2.5.1 with CUDA
12.1. Tabular operations used pandas and NumPy; correlations used SciPy. The
core run executed 20 repository tests before regenerating results. Figures were
exported as vector PDF and 600-dpi PNG with source-data CSVs and alt text.

## Conclusion

ToeholdDesignBench provides an auditable way to ask whether a scoring method
prioritizes useful candidates for an unseen target under a fixed budget. The
reconstructed source manifests reveal that commonly available row-level splits
do not support unseen-target claims. Under source isolation, two learned
canonical baselines improved the frozen success@1 endpoint over exact random
expectation, full-sequence input improved BEACON ranking, and aggregate
prediction and NDCG method orders aligned rather than diverged. The single-
target VISTA analysis supported context agreement but not a scorer-specific
context shift. These findings justify a retrospective candidate-ranking
benchmark and define, rather than erase, the need for multi-target intact-RNA
and prospective validation.

## Figure legends

**Figure 1 | Prediction association and target-ranking quality across canonical
methods.** Each marker represents one canonical method, positioned by its
pooled prediction Spearman correlation and mean target NDCG@10. Vertical bars
are 95% target-bootstrap confidence intervals for NDCG@10. The dashed vertical
line marks zero pooled correlation. Axes display the full bounded ranges. The
exact-random point is a theoretical per-target expectation rather than one
sampled permutation. Marker shape and color redundantly identify methods; source
data are provided with the figure.

**Figure 2 | BEACON ranking under source-disjoint mixed and TF-to-virus
evaluation.** Point-range plots show mean target NDCG@10 for the exact random
expectation, full-sequence GC rule, first-30-nt MLP and CNN, and full-148-nt MLP.
Horizontal bars are 95% target-bootstrap confidence intervals. The left panel
contains 139 source-disjoint test targets; the right panel contains all 23 virus
targets after training on 905 TF sources. Both panels use the same zero-to-one
scale. BEACON-normalized labels are not on the canonical ON − OFF scale.

**Figure 3 | Paired VISTA context stress test for one mCherry target.** For each
scorer, a circle gives Spearman correlation with truncated-target measurements
and a square gives correlation with full-target measurements across 189 paired
sites; lines connect the two contexts. The dashed vertical line marks zero.
Differences are assessed by within-target site bootstrap and do not estimate
cross-target generalization. The fixed random score is a diagnostic only.

## Data availability

The underlying Angenent-Mari data are associated with the original publication
[[3]](#ref-3), and the BEACON data and source code are available from its
official project [[6]](#ref-6). VISTA data access follows the original study
[[7]](#ref-7); redistribution permission must be confirmed before bundling its
workbook. The ToeholdDesignBench release includes derived source maps, frozen
split manifests, exclusion ledgers, target-level metrics, and figure source
data. **Permanent archive DOI, final public repository URL, release license, and
exact release commit: AUTHOR_INPUT_NEEDED.**

## Code availability

The analysis runner, metric implementation, tests, reconstruction scripts, and
paper-artifact builder are versioned in the ToeholdDesignBench repository. The
complete v0.2.1 workflow is invoked by scripts/run_v02.sh after the documented
prepared data are placed in the configured data directory. **Final public URL,
archived release DOI, and commit corresponding to the submitted manuscript:
AUTHOR_INPUT_NEEDED.**

## Ethics, competing interests, funding, and author contributions

This study reanalyzes public synthetic-biology assay data and contains no human
participants or vertebrate-animal experiments. **Competing interests, funding,
and CRediT author contributions: AUTHOR_INPUT_NEEDED.**

## References

<a id="ref-1"></a>1. Green, A. A., Silver, P. A., Collins, J. J. & Yin, P.
Toehold switches: de-novo-designed regulators of gene expression. *Cell* **159**,
925–939 (2014). [https://doi.org/10.1016/j.cell.2014.10.002](https://doi.org/10.1016/j.cell.2014.10.002)

<a id="ref-2"></a>2. To, A. C.-Y. *et al.* A comprehensive web tool for
toehold switch design. *Bioinformatics* **34**, 2862–2864 (2018).
[https://doi.org/10.1093/bioinformatics/bty216](https://doi.org/10.1093/bioinformatics/bty216)

<a id="ref-3"></a>3. Angenent-Mari, N. M., Garruss, A. S., Soenksen, L. R.,
Church, G. & Collins, J. J. A deep learning approach to programmable RNA
switches. *Nature Communications* **11**, 5057 (2020).
[https://doi.org/10.1038/s41467-020-18677-1](https://doi.org/10.1038/s41467-020-18677-1)

<a id="ref-4"></a>4. Valeri, J. A. *et al.* Sequence-to-function deep learning
frameworks for engineered riboregulators. *Nature Communications* **11**, 5058
(2020). [https://doi.org/10.1038/s41467-020-18676-2](https://doi.org/10.1038/s41467-020-18676-2)

<a id="ref-5"></a>5. Shen, Y., Kudla, G. & Oyarzún, D. A. Improving the
generalization of protein expression models with mechanistic sequence
information. *Nucleic Acids Research* **53**, gkaf020 (2025).
[https://doi.org/10.1093/nar/gkaf020](https://doi.org/10.1093/nar/gkaf020)

<a id="ref-6"></a>6. Ren, Y. *et al.* BEACON: benchmark for comprehensive RNA
tasks and language models. *Advances in Neural Information Processing Systems*
**37** (2024).
[https://proceedings.neurips.cc/paper_files/paper/2024/hash/a8ea503d91320fcfe12cba61c8a6d285-Abstract-Datasets_and_Benchmarks_Track.html](https://proceedings.neurips.cc/paper_files/paper/2024/hash/a8ea503d91320fcfe12cba61c8a6d285-Abstract-Datasets_and_Benchmarks_Track.html)

<a id="ref-7"></a>7. Robson, J. M. & Green, A. A. Toehold-VISTA: a machine
learning approach to decipher programmable RNA sensor-target interactions.
*Nucleic Acids Research* **54**, gkag097 (2026).
[https://doi.org/10.1093/nar/gkag097](https://doi.org/10.1093/nar/gkag097)
