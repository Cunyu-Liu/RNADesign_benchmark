"""Generate Gate 0 structured deliverables from computed summaries.

Produces: data_inventory.csv (O0-02), study_context_registry.yaml (O0-03),
literature_claim_matrix.xlsx (O0-01), source_overlap_audit.html (O0-05),
sanity_baseline_report.html (O0-07).
"""
import json
import os

import pandas as pd

BASE = "/mnt/cunyuliu/ToeholdDesignBench"
DOCS = f"{BASE}/docs"
PROC = f"{BASE}/processed"
os.makedirs(DOCS, exist_ok=True)

# ---------------- O0-02 data_inventory.csv ----------------
inventory = [
    {
        "asset": "Toehold_Dataset_Final_2019-10-23.csv",
        "source": "Angenent-Mari et al. 2020 Nat Commun 11:5057 (GitHub lrsoenksen/CL_RNA_SynthBio)",
        "size_bytes": 165235695,
        "sha256": "1b3aec89aa4d06f467187ebc68ee895057e3d2999b373e16a17b56c503999f31",
        "n_rows": 97436,
        "n_cols": 83,
        "key_fields": "source_sequence, sequence_id, trigger, switch sub-sequences, mfe_seq_*, SalisLab*, On/Off_Gate*, Cbn*, ON, OFF, ON_OFF, QC_*",
        "license": "CC BY 4.0 (journal article); repo has no explicit LICENSE file",
        "redistributable": "yes (attribution)",
        "notes": "165MB file served via Git LFS; raw rows 97,436 vs paper-reported 91,534 characterized",
    },
    {
        "asset": "mCH_on_off_rank.xlsx",
        "source": "Robson & Green 2026 NAR gkag097 (GitHub AlexGreenLab/vista)",
        "size_bytes": 240782,
        "sha256": "see manifest",
        "n_rows": 190,
        "key_fields": "Trigger Sequence, OFF AVG, ON AVG Truncated, ON AVG Full, ON OFF Full, MFE/IED/NED features",
        "license": "unclear (repo has no LICENSE); NAR journal",
        "redistributable": "verify",
        "notes": "R2 external full/truncated-target mCherry set (~190 sites)",
    },
    {
        "asset": "mCH_on_off_calc_params.xlsx",
        "source": "Robson & Green 2026 NAR gkag097 (GitHub AlexGreenLab/vista)",
        "size_bytes": 173398,
        "sha256": "see manifest",
        "n_rows": 190,
        "key_fields": "thermodynamic/interaction features",
        "license": "unclear",
        "redistributable": "verify",
        "notes": "feature table companion to rank file",
    },
    {
        "asset": "source_seq_list.csv",
        "source": "Robson & Green 2026 NAR (GitHub AlexGreenLab/vista)",
        "size_bytes": 1840,
        "sha256": "see manifest",
        "n_rows": None,
        "key_fields": "Gene Name, Gene Sequence, Temperature, Output Name, Output Sequence",
        "license": "unclear",
        "redistributable": "verify",
        "notes": "target sRNA list (ryhB, spot42, ...)",
    },
]
pd.DataFrame(inventory).to_csv(f"{DOCS}/data_inventory.csv", index=False)
print("wrote data_inventory.csv")

# ---------------- O0-03 study_context_registry.yaml ----------------
registry = """# Study context registry (Gate 0, ToeholdDesignBench)
version: 0.1
studies:
  angenent2020:
    citation: "Angenent-Mari NM et al. Nat Commun 11:5057 (2020)"
    doi: "10.1038/s41467-020-18677-1"
    role: R1_primary_fused
    rna_type: prokaryotic_translation_activating_toehold_switch
    architecture: first-gen-30nt
    trigger_context: fused
    reporter: GFP
    host: Escherichia_coli_BL21
    assay: flow-seq
    temperature_C: 37
    readout: normalized_ON_OFF_fractions
    normalization: per-construct_gate_normalization
    sources:
      viral_genomes: 23
      human_TFs: 908
      random: 1
    record_count_raw: 97436
    record_count_paper_reported: 91534
    window: 30nt_trigger
    sliding_stride_nt: {virus: 5, human_TF: 10}
    label_columns: [ON, OFF, ON_OFF]
    qc_columns: [QC_ON, QC_OFF, QC_ON_OFF]
    computational_proxies: [SalisLabON, SalisLabOFF, SalisLabONOFF, mfe_seq_*]
    license: CC_BY_4.0

  green2014_valeri2020:
    citation: "Green et al. Cell 2014; Valeri et al. Nat Commun 11:5058 (2020)"
    role: R2_auxiliary_free_trigger
    trigger_context: free-truncated
    approximate_size: ~168_free_trigger_sequences
    notes: small free-trigger set; assay differs from fused

  toehold_vista_2026:
    citation: "Robson JM & Green AA. NAR 54(4):gkag097 (2026)"
    doi: "10.1093/nar/gkag097"
    role: R2_key_external_full_target
    trigger_context: truncated_and_full_length_target
    architecture: series-A-36nt
    reporter: mCherry
    target: mCherry_tiles
    approximate_size: ~200_mCherry_tiles
    label_columns: [OFF_AVG, ON_AVG_Truncated, ON_AVG_Full, ON_OFF_Full]
    notes: SARS-CoV-2 prospective validation available in paper
"""
with open(f"{DOCS}/study_context_registry.yaml", "w") as fh:
    fh.write(registry)
print("wrote study_context_registry.yaml")

# ---------------- O0-01 literature_claim_matrix.xlsx ----------------
claims = [
    ["Green 2014", "Cell", "de-novo toehold switch architecture + experimental validation",
     "device grammar, complementarity, real function", "not a benchmark; small data; no modern multi-method comparison",
     "n/a (no code)", "n/a", "sequence + structure", "experimental ON/OFF"],
    ["To 2018", "Bioinformatics", "web tool: slide window over target, learn efficacy score (~181 data)",
     "full target -> candidate site design tool", "single method; small training; no strict target OOD",
     "web tool (tsgen2)", "~181 switches", "full target", "efficacy score"],
    ["Angenent-Mari 2020", "Nat Commun", "91,534 paired ON/OFF; 23 virus + 906 TF; DNN predicts function",
     "large data, sequence predictors, partial leave-one-virus", "ON is fused; sliding windows; prediction not candidate selection",
     "github lrsoenksen/CL_RNA_SynthBio", "97,436 rows (paper 91,534)", "switch sequence", "R2 (0.43-0.70)"],
    ["Valeri 2020", "Nat Commun", "STORM/NuSpeak, transfer learning, SARS-CoV-2 validation",
     "candidate ranking, constrained redesign, free-trigger transfer", "method paper; unstandardized candidate budget; low cross-context correlation",
     "github (see paper)", "free-trigger sets", "switch+trigger", "ON/OFF regression + validation"],
    ["BEACON 2024", "NeurIPS D&B", "uses 91,534 as Programmable RNA Switches regression task (ON/OFF/ratio R2)",
     "public unified prediction benchmark", "no per-target top-K design utility; no source-disjoint; no trans condition",
     "github (BEACON repo)", "91,534", "switch sequence", "R2 / correlation"],
    ["GARDN/SANDSTORM 2025", "Nat Commun", "joint structure+sequence predictor & generator; toehold design + wet validation",
     "modern generative models, NUPACK baselines", "method+evaluator coupled; random split; selective (not blind) experiments",
     "see paper", "selected generated candidates", "sequence+structure", "prediction + validation"],
    ["Toehold-VISTA 2026", "NAR", "~200 mCherry tiles; truncated+full-length target; PLS-DA target-aware design; SARS-CoV-2",
     "explicit target RNA structure context + site ranking", "single method; limited training target (mCherry); broader-transcript OOD open",
     "github AlexGreenLab/vista", "~200 mCherry + SARS-CoV-2", "full/truncated target structure", "rank / ON-OFF"],
]
cols = ["work", "venue", "core_task_data", "covered_capabilities", "remaining_gap",
        "code", "data_scale", "input_info", "metrics"]
pd.DataFrame(claims, columns=cols).to_excel(f"{DOCS}/literature_claim_matrix.xlsx", index=False)
print("wrote literature_claim_matrix.xlsx")

# ---------------- O0-05 source_overlap_audit.html ----------------
with open(f"{PROC}/overlap_summary.json") as fh:
    ov = json.load(fh)

ov_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Source/window overlap & leakage audit</title>
<style>body{{font-family:system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;line-height:1.5}}
h1{{border-bottom:2px solid #333}} table{{border-collapse:collapse;width:100%}} td,th{{border:1px solid #ccc;padding:6px 10px;text-align:left}}
.hl{{background:#fef3c7}} </style></head><body>
<h1>Source/window overlap &amp; leakage audit (Gate 0, O0-05)</h1>
<p><strong>Data:</strong> Angenent-Mari 2020 canonical pilot (97,436 rows; 931 target groups).</p>
<h2>Key findings</h2>
<ul>
<li><strong>Sliding-window identity:</strong> adjacent 30-nt trigger windows share a median
{ov['adjacent_identity_median']:.2f} sequence identity (mean {ov['adjacent_identity_mean']:.2f}),
with {ov['share_ge_0_8']*100:.0f}% of adjacent pairs at &ge;0.8 identity.</li>
<li><strong>Tiling stride (inferred):</strong> {ov['inferred_step_by_category']}.</li>
<li><strong>Random-row-split leakage:</strong> {ov['random_split_adjacent_neighbour_leak']*100:.0f}% of test tiles
have a same-source adjacent neighbour in train &rarr; random row split leaks near-duplicate windows.</li>
</ul>
<h2>Conclusion</h2>
<p>The 91k dataset is tiled with heavy local window overlap. A row-random split places near-identical
neighbours on both sides; only a <em>source-disjoint</em> split (S1) prevents source/window leakage.</p>
</body></html>"""
with open(f"{DOCS}/source_overlap_audit.html", "w") as fh:
    fh.write(ov_html)
print("wrote source_overlap_audit.html")

# ---------------- O0-07 sanity_baseline_report.html ----------------
with open(f"{PROC}/baseline_summary.json") as fh:
    bs = json.load(fh)

def row(name, d):
    return (f"<tr><td>{name}</td><td>{d['s1']['mean']:.3f}</td><td>{d['s3']['mean']:.3f}</td>"
            f"<td>{d['s5']['mean']:.3f}</td><td>{d['ndcg']['mean']:.3f}</td><td>{d['regret']['mean']:.3f}</td></tr>")

src_rows = "".join(row(n, d) for n, d in bs["source"].items())
row_rows = "".join(row(n, d) for n, d in bs["row"].items())

bs_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Gate 0 sanity baselines</title>
<style>body{{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;line-height:1.5}}
h1{{border-bottom:2px solid #333}} table{{border-collapse:collapse;width:100%;margin:1rem 0}}
td,th{{border:1px solid #ccc;padding:6px 10px}} .k{{text-align:right}} </style></head><body>
<h1>Gate 0 sanity baselines &amp; metrics (O0-07)</h1>
<p>R1 prototype: per-target top-K candidate ranking. Success = top-20% ON/OFF within target (pre-registered placeholder).
Metrics: success@K, NDCG@10, normalized regret. 52,861 admitted-paired records, 926 targets.</p>
<h2>Source-disjoint split (rigorous)</h2>
<table><tr><th>baseline</th><th>success@1</th><th>success@3</th><th>success@5</th><th>NDCG@10</th><th>regret</th></tr>
{src_rows}</table>
<h2>Row-random split (leaky reference)</h2>
<table><tr><th>baseline</th><th>success@1</th><th>success@3</th><th>success@5</th><th>NDCG@10</th><th>regret</th></tr>
{row_rows}</table>
<h2>Reading</h2>
<ul>
<li><strong>B0_random</strong> success@1 &asymp; 0.20 matches the 20% success rate (chance).</li>
<li><strong>B1_thermo</strong> (RBS-calculator ON:OFF / MFE proxy) beats random under source-disjoint split,
demonstrating learnable signal after source isolation.</li>
<li><strong>B2_mlp</strong> (small GPU MLP on trigger one-hot) is competitive but does not clearly exceed the
thermodynamic baseline for intrinsic ranking &mdash; consistent with the &ldquo;prediction &ne; design&rdquo; thesis.</li>
<li>Row-random split inflates NDCG and lowers regret (leakage), but the raw comparison is confounded by target
size; rigorous E2 measurements are deferred to P4.</li>
</ul>
</body></html>"""
with open(f"{DOCS}/sanity_baseline_report.html", "w") as fh:
    fh.write(bs_html)
print("wrote sanity_baseline_report.html")
print("\nAll structured artifacts written to", DOCS)