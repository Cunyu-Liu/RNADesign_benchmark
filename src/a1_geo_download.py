"""A1 (authoritative): download the GEO GSE149225 processed datafile for the
Angenent-Mari et al. 2020 programmable RNA-switch library. Records provenance.
Output: external/gse149225/GSE149225_toehold_processed_datafile.csv.gz
"""
import os
import urllib.request

URL = ("https://www.ncbi.nlm.nih.gov/geo/download/?acc=GSE149225&format=file"
       "&file=GSE149225%5Ftoehold%5Fprocessed%5Fdatafile%2Ecsv%2Egz")
OUT_DIR = "/mnt/cunyuliu/ToeholdDesignBench/external/gse149225"
OUT = os.path.join(OUT_DIR, "GSE149225_toehold_processed_datafile.csv.gz")
EXPECTED_MD5 = None  # set after first download; record in provenance

if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    if not os.path.exists(OUT):
        print("downloading GSE149225 ...")
        urllib.request.urlretrieve(URL, OUT)
    print("local file:", OUT, "exists:", os.path.exists(OUT),
          "size:", os.path.getsize(OUT) if os.path.exists(OUT) else 0)