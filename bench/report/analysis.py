"""Agregasi hasil benchmark untuk laporan: median, min-maks, speedup + selang bootstrap, summary.csv.

Semua angka berasal dari bench/results/<tag>/<workload>/<config>/run_*.json (run pemanasan dibuang).
"""

import json

import numpy as np

from bench.common import RESULTS_DIR, ROOT, rel  # noqa: F401  (ROOT dipakai bagian_b6)

TAGS = ["g16-gpu", "g16-cpu", "d0-old"]

# metrik waktu utama per workload (lebih kecil = lebih baik) dan cara mengambilnya dari JSON run
WAKTU_UTAMA = {
    "W1": ("latih_loop_s", lambda r: r["waktu"]["latih_loop_s"]),
    "W2": ("latih_s", lambda r: r["waktu"]["latih_s"]),
    "W7": ("latensi_p50_ms", lambda r: r["inferensi"]["latensi_ms"]["p50"]),
    # B5: W3/W4 = satu run terukur berisi banyak pelatihan (tanpa CI); W6/W8 = 5 ulangan
    "W3": ("sweep_s", lambda r: r["waktu"]["sweep_s"]),
    "W4": ("ablation_total_s", lambda r: r["waktu"]["ablation_total_s"]),
    "W6": ("dinding_total_s", lambda r: r["waktu"]["dinding_total_s"]),
    "W8": ("siklus_median_s", lambda r: r["waktu"]["siklus_median_s"]),
}
B2 = ("W1", "W2", "W7")
B5 = ("W3", "W4", "W6", "W8")

# pasangan perbandingan (pembanding, yang dibandingkan): speedup = median pembanding / median lainnya
PASANGAN = [
    ("g16-cpu", "g16-gpu", "efek GPU murni (mesin sama)"),
    ("d0-old", "g16-cpu", "efek mesin baru tanpa GPU"),
    ("d0-old", "g16-gpu", "sebelum vs sesudah (gabungan)"),
]


def load_runs(tag, workload, cid):
    d = RESULTS_DIR / tag / workload / cid
    files = sorted(d.glob("run_*.json"))
    runs = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    return [r for r in runs if not r["pemanasan"]], [rel(f) for f in files]


def status_config(tag, workload, cid):
    """'ada' | 'tidak berlaku' | 'belum diukur'."""
    d = RESULTS_DIR / tag / workload / cid
    if (d / "tidak_berlaku.json").exists():
        return "tidak berlaku"
    return "ada" if any(d.glob("run_*.json")) else "belum diukur"


def configs(workload):
    out = set()
    for t in TAGS:
        p = RESULTS_DIR / t / workload
        if p.exists():
            out |= {c.name for c in p.iterdir() if c.is_dir()}
    return sorted(out)


def ringkas(vals):
    v = np.asarray(vals, dtype=float)
    return {"n": len(v), "median": float(np.median(v)), "min": float(v.min()), "maks": float(v.max())}


def bootstrap_speedup(a, b, n=5000, seed=0):
    """Speedup = median(a)/median(b), CI 95 % bootstrap persentil (resampling run per sisi)."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, float), np.asarray(b, float)
    ia = rng.integers(0, len(a), (n, len(a)))
    ib = rng.integers(0, len(b), (n, len(b)))
    s = np.median(a[ia], axis=1) / np.median(b[ib], axis=1)
    return {"speedup": float(np.median(a) / np.median(b)), "ci95": [float(np.percentile(s, 2.5)),
                                                                    float(np.percentile(s, 97.5))]}


def waktu_per_config(workload):
    """{cid: {tag: {'ringkas': ..., 'nilai': [...], 'sumber': [...]} | status}}"""
    nama, ambil = WAKTU_UTAMA[workload]
    out = {}
    for cid in configs(workload):
        out[cid] = {}
        for t in TAGS:
            st = status_config(t, workload, cid)
            if st != "ada":
                out[cid][t] = {"status": st}
                continue
            runs, src = load_runs(t, workload, cid)
            vals = [ambil(r) for r in runs]
            out[cid][t] = {"status": "ada", "metrik": nama, "nilai": vals, "ringkas": ringkas(vals), "sumber": src}
    return out


def speedups(workload, g2=None):
    """Speedup per config untuk tiap pasangan device yang keduanya terukur.

    Bila g2 (isi bench/results/G2.json) diberikan dan config tidak setara kualitasnya, speedup
    ditandai 'tidak dilaporkan sebagai speedup' (aturan G2).
    """
    rows = []
    data = waktu_per_config(workload)
    for cid, per_tag in data.items():
        for a, b, arti in PASANGAN:
            # sisi GPU dibandingkan dengan config CPU padanannya (mis. cuda_hist <-> cpu_hist)
            cid_a = acuan_cpu(workload, cid) if b == "g16-gpu" else cid
            va = data.get(cid_a, {}).get(a, {})
            vb = per_tag.get(b, {})
            if va.get("status") != "ada" or vb.get("status") != "ada":
                continue
            s = bootstrap_speedup(va["nilai"], vb["nilai"])
            setara = None
            if g2 and b == "g16-gpu" and cid in g2.get(workload, {}):
                setara = g2[workload][cid]["setara"]
            label = cid if cid_a == cid else f"{cid_a} -> {cid}"
            rows.append({"workload": workload, "config": label, "pembanding": a, "dibandingkan": b, "arti": arti,
                         "metrik": va["metrik"], **s, "g2_setara": setara,
                         "dilaporkan_sebagai_speedup": setara is not False})
    return rows


def acuan_cpu(workload, cid):
    """Config CPU padanan sebuah config jalur GPU (sama dengan pasangan di bench/g2_check.py)."""
    import re

    from bench.g2_check import W1_ACUAN_CPU

    if workload == "W1":
        return W1_ACUAN_CPU.get(cid, cid)
    if workload in ("W2", "W6"):
        return "cpu_hist" if cid == "cuda_hist" else cid
    if workload == "W3":
        return "xgb_cpu" if cid == "xgb_cuda" else cid
    if workload in ("W4", "W8"):
        return cid
    return re.sub(r"_cuda(_notf32)?_", "_cpu_", cid)


def provenance(tag):
    """Commit git per run di tag ini, dan apakah commit itu ada di repo lokal (bisa ditelusuri)."""
    import subprocess
    from collections import Counter

    c = Counter()
    for f in (RESULTS_DIR / tag).glob("*/*/run_*.json"):
        g = json.loads(f.read_text(encoding="utf-8")).get("git") or {}
        c[(g.get("commit", "?")[:7], bool(g.get("dirty")))] += 1
    out = []
    for (commit, dirty), n in sorted(c.items(), key=lambda kv: -kv[1]):
        ada = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], capture_output=True, check=False).returncode == 0
        out.append({"commit": commit, "dirty": dirty, "n_run": n, "ada_di_repo": ada})
    return out


def env_tag(tag):
    """Isi env capture terakhir yang dirujuk run di tag ini (None bila berkasnya tidak ada)."""
    refs = set()
    for f in (RESULTS_DIR / tag).glob("*/*/run_*.json"):
        e = json.loads(f.read_text(encoding="utf-8")).get("env")
        if isinstance(e, str):
            refs.add(e)
    for ref in sorted(refs, reverse=True):  # terbaru dulu; lewati rujukan yang berkasnya hilang
        p = RESULTS_DIR.parent.parent / ref
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8")), ref
    top = RESULTS_DIR / tag / "env.json"
    if top.exists():
        return json.loads(top.read_text(encoding="utf-8")), rel(top)
    return None, (max(refs) if refs else None)


def kondisi_tag(tag):
    """kondisi_manual dari run terakhir di tag ini."""
    files = sorted((RESULTS_DIR / tag).glob("*/*/run_*.json"), key=lambda f: f.stat().st_mtime)
    return json.loads(files[-1].read_text(encoding="utf-8")).get("kondisi_manual") if files else None


def summary_rows():
    """Baris summary.csv: satu baris per (workload, config, tag)."""
    rows = []
    for w in WAKTU_UTAMA:
        for cid, per_tag in waktu_per_config(w).items():
            for t, v in per_tag.items():
                if v["status"] != "ada":
                    rows.append({"workload": w, "config": cid, "tag": t, "status": v["status"]})
                    continue
                r = v["ringkas"]
                rows.append({"workload": w, "config": cid, "tag": t, "status": "ada", "metrik": v["metrik"],
                             "n": r["n"], "median": r["median"], "min": r["min"], "maks": r["maks"],
                             "sumber": f"bench/results/{t}/{w}/{cid}/run_*.json"})
    return rows


def komponen_w1(tag, cid):
    """Median waktu per komponen W1 (detik) untuk grafik komponen."""
    runs, _ = load_runs(tag, "W1", cid)
    if not runs:
        return None
    keys = ["muat_s", "praproses_s", "transfer_ke_device_s", "latih_loop_s", "eval_s"]
    return {k: float(np.median([r["waktu"].get(k) or 0.0 for r in runs])) for k in keys}


def time_to_target(tag, cid):
    runs, _ = load_runs(tag, "W1", cid)
    if not runs:
        return None
    tt = [r["time_to_target"] for r in runs]
    capai = [t["detik"] for t in tt if t["tercapai"]]
    return {"n_run": len(tt), "n_tercapai": len(capai), "target": tt[0]["target_val_loss"],
            "median_detik": float(np.median(capai)) if capai else None,
            "epoch_median": float(np.median([t["epoch"] for t in tt if t["tercapai"]])) if capai else None}
