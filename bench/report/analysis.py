"""Agregasi hasil benchmark untuk laporan: median, min-maks, speedup + selang bootstrap, summary.csv.

Semua angka berasal dari bench/results/<tag>/<workload>/<config>/run_*.json (run pemanasan dibuang).
"""

import json

import numpy as np

from bench.common import RESULTS_DIR, rel

TAGS = ["g16-gpu", "g16-cpu", "d0-old"]

# metrik waktu utama per workload (lebih kecil = lebih baik) dan cara mengambilnya dari JSON run
WAKTU_UTAMA = {
    "W1": ("latih_loop_s", lambda r: r["waktu"]["latih_loop_s"]),
    "W2": ("latih_s", lambda r: r["waktu"]["latih_s"]),
    "W7": ("latensi_p50_ms", lambda r: r["inferensi"]["latensi_ms"]["p50"]),
}

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
    for cid, per_tag in waktu_per_config(workload).items():
        for a, b, arti in PASANGAN:
            if per_tag.get(a, {}).get("status") != "ada" or per_tag.get(b, {}).get("status") != "ada":
                continue
            s = bootstrap_speedup(per_tag[a]["nilai"], per_tag[b]["nilai"])
            setara = None
            if g2 and "gpu" in b and cid in g2.get(workload, {}):
                setara = g2[workload][cid]["setara"]
            rows.append({"workload": workload, "config": cid, "pembanding": a, "dibandingkan": b, "arti": arti,
                         "metrik": per_tag[a]["metrik"], **s, "g2_setara": setara,
                         "dilaporkan_sebagai_speedup": setara is not False})
    return rows


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
