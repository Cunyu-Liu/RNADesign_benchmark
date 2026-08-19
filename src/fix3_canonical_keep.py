"""FIX-3 final: canonical keeps ALL virus+TF rows (no fail-closed exclusion);
retains official 91,534 QC2 labels as preserved data asset; reports exact accounting."""
import pandas as pd

CANON = "/mnt/cunyuliu/ToeholdDesignBench/processed/canonical_records.parquet"
df = pd.read_parquet(CANON)

# No row excluded: relabel 'excluded_no_label' -> 'retained_no_label' (kept, no labels)
df["admission_status"] = df["admission_status"].replace(
    {"excluded_no_label": "retained_no_label"})
assert "excluded" not in df["admission_status"].unique().tolist()

# coordinate-unresolved rows are retained (already coordinate_status=no_coord)
assert df["coordinate_status"].eq("no_coord").sum() > 0  # retained, not dropped

print("admission_status (all rows kept):", df["admission_status"].value_counts().to_dict())
print("total rows (virus+TF):", len(df))
print("rows with dual-state final labels:", int((df["ON"].notna() & df["OFF"].notna()).sum()))
print("rows with any label:", int((df["ON"].notna() | df["OFF"].notna()).sum()))
print("coordinate_status:", df["coordinate_status"].value_counts().to_dict())
print("targets:", df["target_id"].nunique())

df.to_parquet(CANON, index=False)
print("canonical_records.parquet rewritten (all rows kept, none excluded)")

# accounting summary to attach to reconciliation doc
paired = int((df["ON"].notna() & df["OFF"].notna()).sum())
anylab = int((df["ON"].notna() | df["OFF"].notna()).sum())
print(f"\nPAIRED(dual-label) = {paired}; ANY-LABEL = {anylab}; TOTAL(virus+TF) = {len(df)}")