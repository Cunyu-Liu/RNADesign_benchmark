"""Traceable download of the Toehold-VISTA NAR 2026 supplementary data.

Source: Robson & Green, Nucleic Acids Research 2026, gkag097 (PMC12907555),
supplemental zip (SI PDF + Supplementary Data xlsx). Used for the
selection-conditioned SARS-CoV groups analysis (Supplementary Table 9).
Protected by the same PMC proof-of-work challenge as the crowdsourced data;
see scripts/download_crowdsourced.py for the PoW algorithm note.

Usage:
  python scripts/download_vista_nar.py \
      --out /mnt/cunyuliu/ToeholdDesignBench/external_data/vista_nar
"""
import argparse
import hashlib
import os
import re
import time
import urllib.request

ZIP_URL = ("https://pmc.ncbi.nlm.nih.gov/articles/instance/12907555/bin/"
           "gkag097_supplemental_files.zip")
ARTICLE = "https://pmc.ncbi.nlm.nih.gov/articles/PMC12907555/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")


def http_get(url, cookie=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    if cookie:
        req.add_header("Cookie", cookie)
    return urllib.request.urlopen(req, timeout=180).read()


def solve_pow(page):
    m = re.search(r'POW_CHALLENGE = "([^"]+)"', page)
    d = re.search(r'POW_DIFFICULTY = "(\d+)"', page)
    if not m or not d:
        return None
    challenge, diff = m.group(1), int(d.group(1))
    target = "0" * diff
    nonce = 0
    while True:
        h = hashlib.sha256(
            (challenge + str(nonce)).encode()).hexdigest()
        if h.startswith(target):
            return f"cloudpmc-viewer-pow={challenge},{nonce}"
        nonce += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(f"{args.out}/supplemental", exist_ok=True)
    zip_path = f"{args.out}/gkag097_supplemental_files.zip"
    if not os.path.exists(zip_path):
        raw = http_get(ZIP_URL)
        if raw[:2] == b"PK":
            open(zip_path, "wb").write(raw)
        else:
            cookie = solve_pow(raw.decode("utf-8", "replace"))
            if cookie is None:
                raise SystemExit("no PoW challenge found")
            time.sleep(1)
            data = http_get(ZIP_URL, cookie)
            if data[:2] != b"PK":
                raise SystemExit(f"payload not a zip: {data[:80]!r}")
            open(zip_path, "wb").write(data)
    print(f"zip: {zip_path} ({os.path.getsize(zip_path)} bytes)")
    os.system(f"cd {args.out} && unzip -o -q "
              f"gkag097_supplemental_files.zip -d supplemental")
    art = f"{args.out}/article.html"
    if not os.path.exists(art):
        open(art, "wb").write(http_get(ARTICLE))
    print("OK")


if __name__ == "__main__":
    main()
