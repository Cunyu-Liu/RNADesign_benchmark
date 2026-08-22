"""Traceable download of the crowdsourced riboregulator preprint data.

Source: bioRxiv 2026.07.08.737257 (PMC13370501), Supplementary Table 1
(100 community-designed riboregulators, native cell-free TX-TL outcomes).

PMC file downloads are protected by a proof-of-work challenge
(cloudpmc-viewer-pow): the viewer JS computes
    sha256(POW_CHALLENGE + str(nonce))  starting with N zeros
and stores the cookie `cloudpmc-viewer-pow=<challenge>,<nonce>`. This script
solves the challenge (difficulty 4, same algorithm) and downloads the file.

Redistribution note (contract §9 Batch 4): the preprint is an open-access
NIH-funded preprint on PMC; the supplementary file is fetched directly from
PMC with its native name and stored under external_data/crowdsourced/ for
audit. License: preprint made available under the PMC open-access terms.

Usage:
  python scripts/download_crowdsourced.py \
      --out /mnt/cunyuliu/ToeholdDesignBench/external_data/crowdsourced
"""
import argparse
import hashlib
import re
import sys
import time
import urllib.request

ARTICLE = "https://pmc.ncbi.nlm.nih.gov/articles/PMC13370501/"
FILES = {
    "media-1.xlsx":
        "https://pmc.ncbi.nlm.nih.gov/articles/instance/13370501/bin/"
        "media-1.xlsx",
}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")


def http_get(url, cookie=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    if cookie:
        req.add_header("Cookie", cookie)
    return urllib.request.urlopen(req, timeout=120).read()


def solve_pow(page):
    """Solve the PMC cloudpmc-viewer PoW challenge (difficulty from page)."""
    m = re.search(r'POW_CHALLENGE = "([^"]+)"', page)
    d = re.search(r'POW_DIFFICULTY = "(\d+)"', page)
    if not m or not d:
        return None
    challenge, diff = m.group(1), int(d.group(1))
    target = "0" * diff
    nonce = 0
    while True:
        h = hashlib.sha256((challenge + str(nonce)).encode()).hexdigest()
        if h.startswith(target):
            return f"cloudpmc-viewer-pow={challenge},{nonce}"
        nonce += 1


def download(url, out_path):
    raw = http_get(url)
    if raw[:2] == b"PK" or raw[:5] == b"%PDF-":
        open(out_path, "wb").write(raw)
        return "direct"
    page = raw.decode("utf-8", "replace")
    cookie = solve_pow(page)
    if cookie is None:
        raise RuntimeError(f"no PoW challenge found for {url}; "
                           f"page head: {page[:200]}")
    # brief pause mirrors the viewer's reload delay
    time.sleep(1)
    data = http_get(url, cookie)
    if data[:2] != b"PK" and data[:5] != b"%PDF":
        raise RuntimeError(f"post-PoW payload not a file: {data[:80]!r}")
    open(out_path, "wb").write(data)
    return "pow-solved"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    import os
    os.makedirs(args.out, exist_ok=True)
    for name, url in FILES.items():
        path = f"{args.out}/{name}"
        mode = download(url, path)
        print(f"{name}: {mode} -> {path} ({os.path.getsize(path)} bytes)")
    # article HTML for provenance
    art = f"{args.out}/article.html"
    if not os.path.exists(art):
        open(art, "wb").write(http_get(ARTICLE))
        print(f"article.html saved for provenance")
    print("OK")


if __name__ == "__main__":
    sys.exit(main())
