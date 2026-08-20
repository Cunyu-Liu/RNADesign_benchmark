#!/usr/bin/env bash
# ToeholdDesignBench — data download script (FIX-4)
# Downloads all public raw assets needed to rebuild the benchmark.
# Uses a relative DATA_DIR (default ./data) so it works from any checkout.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${DATA_DIR:-$ROOT/data}"
RAW="$DATA_DIR/raw"
EXT="$DATA_DIR/external"
NPZ="$RAW/npz"
mkdir -p "$RAW" "$EXT" "$NPZ"

echo "== data dir: $DATA_DIR =="

# 1) Angenent-Mari 2020 primary dataset (LFS, 165 MB, CC BY 4.0)
#    Git LFS object served by media.githubusercontent; sha256 (LFS oid):
#    1b3aec89aa4d06f467187ebc68ee895057e3d2999b373e16a17b56c503999f31
CSV="$RAW/Toehold_Dataset_Final_2019-10-23.csv"
if [ ! -s "$CSV" ]; then
  echo "== downloading Angenent-Mari dataset (165 MB) =="
  curl -sL -o "$CSV" \
    "https://media.githubusercontent.com/media/lrsoenksen/CL_RNA_SynthBio/master/data/Toehold_Dataset_Final_2019-10-23.csv"
fi
echo "sha256 check:"; sha256sum "$CSV"

# 2) Official QC2 labels (91,534 x [ON, OFF, ON/OFF]) — GitHub model input
NPZF="$NPZ/scaling_data.npz"
if [ ! -s "$NPZF" ]; then
  echo "== downloading official QC2 scaling_data.npz =="
  curl -sL -o "$NPZF" \
    "https://raw.githubusercontent.com/lrsoenksen/CL_RNA_SynthBio/master/models/mlp_1d/MLP_1D-ON-OFF-ON_OFF-QC2/input/scaling_data.npz"
fi

# 3) Toehold-VISTA external full-target data (mCherry) — R2 external set
V="$EXT/mCH_on_off_rank.xlsx"
if [ ! -s "$V" ]; then
  echo "== downloading Toehold-VISTA mCherry data =="
  curl -sL -o "$V" \
    "https://raw.githubusercontent.com/AlexGreenLab/vista/main/Pairwise%20Probability/mCH_on_off_rank.xlsx"
fi

# 4) Full sequence-mapped PRS dataset (91,534) — BEACON (NeurIPS 2024) HF mirror.
#    Array of [sequence, ON, OFF, ON_OFF]; train/val/test = 73,227/9,153/9,154.
#    Mirrored from JiahaoZhang2003/beacon-programmable-rna-switches (CC BY 4.0 underlying data).
BP="$EXT/beacon_prs"
mkdir -p "$BP"
for name_md5 in "train.csv adbe31a6eba54044069e9548385ad834" "val.csv c49cf21770fdc3553bb965aee47b03b1" "test.csv b39a2ee0aed350c3a67b3248f9499f17"; do
  set -- $name_md5
  f="$1"; want="$2"
  if [ ! -s "$BP/$f" ]; then
    echo "== downloading beacon $f =="
    curl -sL -o "$BP/$f" "https://huggingface.co/datasets/jiahaozhang2003/beacon-programmable-rna-switches/resolve/main/$f"
  fi
  got=$(md5 -q "$BP/$f" 2>/dev/null || md5sum "$BP/$f" | awk '{print $1}')
  echo "$f md5: $got (expect $want)"
done

# 5) (optional) reference genomes/transcripts are fetched on demand by
#    src/data/map_virus_full.py / map_tf.py (NCBI efetch, cached in processed/sequences).

echo "== done. contents: =="
ls -la "$RAW" "$EXT" "$NPZ"
echo
echo "Next: python src/build_canonical_final.py   # rebuild canonical_records.parquet"
echo "      python src/p2_build.py                # splits + leakage + oracle"
echo "      python src/p3_baselines.py            # 6 families (reproducible, seed 0)"