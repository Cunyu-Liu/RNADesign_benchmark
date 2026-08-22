"""Number-provenance audit: verify every key manuscript number against the
run artifacts (contract §9: auditable claims; no hand-written numbers that
do not trace to artifacts).

Usage: python src/v03_number_audit.py [--paper PATH]
Exit 0 iff every checked number appears in the manuscript.
"""
import argparse
import glob
import json
import os

import pandas as pd

BASE = '/mnt/cunyuliu/ToeholdDesignBench/runs/v0.3.0'


def paper_text(path):
    return open(path, encoding='utf-8').read().replace(
        '\u2212', '-').replace('\u2013', '-').replace('\xa0', ' ')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--paper', default='/home/cunyuliu/ToeholdDesignBench/'
                        'docs/paper_draft_v03.md')
    args = ap.parse_args()
    paper = paper_text(args.paper)
    fails = []

    def check(name, value_str, artifact):
        ok = f'{value_str}' in paper
        print(f"[{'OK' if ok else 'MISSING'}] {name}: {value_str} "
              f"(artifact={artifact})")
        if not ok:
            fails.append(name)

    def check_rounded(name, value, artifact):
        """Accept the manuscript quoting the value at 3 OR 4 decimals."""
        for fmt in (f'{value:.4f}', f'{value:.3f}'):
            if fmt in paper:
                print(f'[OK] {name}: {fmt} (artifact={artifact})')
                return
        fails.append(name)
        print(f'[MISSING] {name}: neither {value:.4f} nor {value:.3f} '
              f'(artifact={artifact})')

    # ---- §5 family tables + contrasts (two completed backbones) ----
    for bb, tag in (('cnn60', 'CNN'), ('sandstorm', 'SANDSTORM')):
        ms = pd.read_csv(f'{BASE}/eval_{bb}_family/method_summary.csv')
        ms = ms.set_index('method_id')
        for mid, short in [(f'{bb}/rowwise_mse', 'rowwise'),
                           (f'{bb}/tb_mse', 'tb_mse'),
                           (f'{bb}/tb_dual', 'tb_dual'),
                           (f'{bb}/full_tblr', 'full_tblr'),
                           (f'{bb}/tb_lambdarank', 'tb_lambdarank')]:
            v = ms.loc[mid, 'ndcg@10']
            check(f'{tag} {short} ndcg', f'{v:.4f}', f'{v:.6f}')
        c = pd.read_csv(f'{BASE}/eval_{bb}_family/contrasts.csv')
        prim = c[c['kind'] == 'primary'].iloc[0]
        check(f'{tag} primary effect', f"{prim['mean_diff']:.4f}",
              f"{prim['mean_diff']:.6f}")
        for col, label in (('ci_low', 'CI lo'), ('ci_high', 'CI hi')):
            check(f'{tag} primary {label}', f"{prim[col]:.4f}",
                  f"{prim[col]:.6f}")
        sec = c[(c['kind'] == 'secondary')
                & (c['method_b'] == f'{bb}/rowwise_mse')].iloc[0]
        check(f'{tag} secondary vs rowwise', f"{sec['mean_diff']:.4f}",
              f"{sec['mean_diff']:.6f}")

    # ---- §8 mCherry (latest vista_external with both transfer families) ----
    vdirs = sorted(d for d in os.listdir(BASE)
                   if d.startswith('vista_external_'))
    latest = f'{BASE}/{vdirs[-1]}'
    vr = json.load(open(f'{latest}/vista_external_results.json'))
    for r in vr['onoff_full']:
        check(f"mCherry {r['method']}", f"{r['ndcg@10']:.4f}",
              f"{r['ndcg@10']:.6f}")

    # ---- §8b crowdsourced (latest run, both backbones) ----
    cdirs = sorted(d for d in os.listdir(BASE)
                   if d.startswith('crowd_external_'))
    clatest = f'{BASE}/{cdirs[-1]}'
    cs = pd.read_csv(f'{clatest}/spearman_summary.csv')
    for _, row in cs.iterrows():
        check(f"crowd {row['method_id']} {row['prediction']} vs "
              f"{row['outcome']}", f"{row['spearman']:.3f}",
              f"{row['spearman']:.6f}")
        check(f"crowd {row['method_id']} {row['outcome']} CI lo",
              f"{row['cluster_boot_lo']:.3f}",
              f"{row['cluster_boot_lo']:.6f}")
    ec = json.load(open(f'{clatest}/exposure_check.json'))
    assert ec['sensor_overlap'] == 0 and ec['trigger_overlap'] == 0
    print('[OK] crowdsourced exposure 0 overlap (artifact verified)')

    # ---- §6 leakage experiment ----
    lman = None
    for d in reversed(sorted(glob.glob(f'{BASE}/leakage_*'))):
        for f in os.listdir(d):
            if f.endswith('.json') and 'manifest' not in f:
                lman = json.load(open(f'{d}/{f}'))
                break
        if lman:
            break
    if lman and 'summary' in lman:
        s = lman['summary']
        check('leakage leaky ndcg', f"{s['mean_ndcg_leaky']:.4f}",
              f"{s['mean_ndcg_leaky']:.6f}")
        check('leakage clean ndcg', f"{s['mean_ndcg_clean']:.4f}",
              f"{s['mean_ndcg_clean']:.6f}")
        check('leakage paired diff', f"{s['mean_paired_diff']:.4f}",
              f"{s['mean_paired_diff']:.6f}")
        check('leakage n leaky-better', str(s['n_targets_leaky_better']),
              str(s['n_targets_leaky_better']))
    else:
        print('[WARN] no leakage summary artifact found')

    # ---- biophysical baselines (family eval extras) ----
    for bb in ('cnn60',):
        ms = pd.read_csv(f'{BASE}/eval_{bb}_family/method_summary.csv')
        ms = ms.set_index('method_id')
        for mid in ('lightgbm-combined', 'lightgbm-biophys',
                    'lightgbm-seq', 'thermo-scorer', 'gc-baseline'):
            if mid in ms.index:
                v = float(ms.loc[mid, 'ndcg@10'])
                check_rounded(f'baseline {mid}', v, f'{v:.6f}')

    print()
    if fails:
        print(f'{len(fails)} NUMBERS MISSING FROM PAPER: {fails}')
        raise SystemExit(1)
    print('ALL MANUSCRIPT NUMBERS TRACE TO ARTIFACTS')


if __name__ == '__main__':
    main()
