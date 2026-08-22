"""Start-only watchdog for TBLR orchestrator streams (contract: never kill).

Monitors (backbone, outer_fold) work plans; when a stream's orchestrator and
trainer child are both gone while work remains, relaunches the orchestrator
(resume-safe: completed run manifests are skipped by v03_tune.py). For the
rnaelectra fold queue, starts the next queued fold when a stream finishes and
concurrency allows. Relaunch prefers the stream's last GPU, falling back to
the non-MIG GPU with the most free memory. Exits when all planned work is
complete. All PIDs are rediscovered at runtime via ps; nothing is killed.
"""
import argparse
import json
import os
import re
import subprocess
import time

PROJ = "/home/cunyuliu/ToeholdDesignBench"
MNT = "/mnt/cunyuliu/ToeholdDesignBench"
BASE = f"{MNT}/runs/v0.3.0"
PY = "/home/cunyuliu/miniconda3/envs/toeholdbench/bin/python"
LOG = f"{PROJ}/logs/v03_watchdog.log"
STATE = f"{BASE}/watchdog_state.json"
ABLATIONS = ["rowwise_mse", "tb_mse", "tb_dual", "tb_lambdarank", "full_tblr"]
SEEDS = [20260821, 20260822, 20260823, 20260824, 20260825]
CHECK_INTERVAL = 600
MIN_FREE_GB = 7.0
MIG_MAX_GB = 20.0


def fold_state(base, backbone, fold):
    """'tune' | 'final' | 'done' from on-disk artifacts."""
    sel = f"{base}/tune_{backbone}_f{fold}/selection.json"
    if not os.path.exists(sel):
        return "tune"
    for abl in ABLATIONS:
        for s in SEEDS:
            m = f"{base}/final_{backbone}_f{fold}_{abl}_s{s}/run_manifest.json"
            if not os.path.exists(m):
                return "final"
    return "done"


def parse_ps(ps_text):
    """Extract live (kind, backbone, fold, cuda_device) tuples from ps output.

    kind: 'orchestrator' (v03_tune.py) or 'trainer' (v03_tblr.py).
    """
    out = []
    for line in ps_text.splitlines():
        if "v03_tune.py" in line:
            kind = "orchestrator"
        elif "v03_tblr.py" in line:
            kind = "trainer"
        else:
            continue
        m = re.search(r"--backbone (\w+)", line)
        f = re.search(r"--outer-fold (\d+)", line)
        if not (m and f):
            continue
        d = re.search(r"--cuda-device (\d+)", line)
        out.append((kind, m.group(1), int(f.group(1)),
                    int(d.group(1)) if d else None))
    return out


def stream_active(entries, backbone, fold):
    """True if an orchestrator or trainer child for this stream is alive."""
    return any(e[0] in ("orchestrator", "trainer") and e[1] == backbone
               and e[2] == fold for e in entries)


def pick_gpu(free_by_gpu, prefer=None):
    """Prefer  if it has room; else the non-MIG GPU with most free.

    free_by_gpu: {gpu_index: free_gb}. MIG slices (total below MIG_MAX_GB)
    must be pre-filtered by the caller.
    """
    if prefer is not None and free_by_gpu.get(prefer, 0.0) >= MIN_FREE_GB:
        return prefer
    ok = {g: f for g, f in free_by_gpu.items() if f >= MIN_FREE_GB}
    if not ok:
        return None
    return max(ok, key=lambda g: ok[g])


def gpu_free_map():
    """{gpu_index: free_gb} for non-MIG GPUs, via nvidia-smi."""
    out = {}
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.used,memory.total",
             "--format=csv,noheader,nounits"], capture_output=True, text=True,
            timeout=60)
        for line in r.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 3:
                continue
            idx, used, total = int(parts[0]), float(parts[1]), float(parts[2])
            if total >= MIG_MAX_GB * 1024:
                out[idx] = (total - used) / 1024.0
    except Exception as exc:  # noqa: BLE001 - watchdog must never crash
        log(f"gpu_free_map failed: {exc}")
    return out


def log(msg):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {msg}"
    with open(LOG, "a") as fh:
        fh.write(line + "\n")
    print(line, flush=True)


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as fh:
            return json.load(fh)
    return {"last_device": {}}


def save_state(st):
    with open(STATE, "w") as fh:
        json.dump(st, fh, indent=2)


def launch(backbone, fold, device, phase):
    env = dict(os.environ)
    env["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    cmd = [PY, "-u", "src/v03_tune.py", "--backbone", backbone,
           "--outer-fold", str(fold), "--phase", phase,
           "--cuda-device", str(device)]
    logf = f"{PROJ}/logs/v03_watchdog_{backbone}_f{fold}.log"
    with open(logf, "a") as fh:
        fh.write(f"\n=== watchdog relaunch {cmd} ===\n")
        subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=PROJ,
                         env=env)
    log(f"launched {backbone} fold {fold} phase={phase} device={device}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rnaelectra-max-streams", type=int, default=3)
    args = ap.parse_args()

    sandstorm_folds = [2, 3, 4]  # f0/f1 already complete at watchdog start
    rnae_folds = [0, 1, 2, 3, 4]
    st = load_state()
    log("watchdog started")
    while True:
        ps_text = subprocess.run(["ps", "aux"], capture_output=True,
                                 text=True).stdout
        entries = parse_ps(ps_text)
        free = gpu_free_map()

        # remember devices of live streams
        for kind, bb, fold, dev in entries:
            if kind == "orchestrator" and dev is not None:
                st["last_device"][f"{bb}_f{fold}"] = dev
        save_state(st)

        all_done = True
        # sandstorm: keep remaining folds alive
        for fold in sandstorm_folds:
            state = fold_state(BASE, "sandstorm", fold)
            if state == "done":
                continue
            all_done = False
            if not stream_active(entries, "sandstorm", fold):
                dev = pick_gpu(free, st["last_device"].get(f"sandstorm_f{fold}"))
                if dev is None:
                    log(f"sandstorm f{fold} needs relaunch, no GPU with "
                        f">={MIN_FREE_GB}GB free; will retry")
                else:
                    launch("sandstorm", fold, dev, "all")

        # rnaelectra: queue with bounded concurrency
        active = [f for f in rnae_folds
                  if stream_active(entries, "rnaelectra", f)]
        for fold in rnae_folds:
            state = fold_state(BASE, "rnaelectra", fold)
            if state == "done":
                continue
            all_done = False
            if stream_active(entries, "rnaelectra", fold):
                continue
            if fold in active:
                continue
            if len(active) >= args.rnaelectra_max_streams:
                break
            dev = pick_gpu(free, st["last_device"].get(f"rnaelectra_f{fold}"))
            if dev is None:
                log(f"rnaelectra f{fold} waiting: no GPU with "
                    f">={MIN_FREE_GB}GB free")
                break
            launch("rnaelectra", fold, dev, "all")
            active.append(fold)

        if all_done:
            log("all planned work complete; watchdog exiting")
            return
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
