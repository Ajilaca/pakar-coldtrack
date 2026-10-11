"""Grafik PNG laporan benchmark (matplotlib). Data dari bench.report.analysis -- tidak ada angka manual.

Warna mengikuti ENTITAS (device), bukan urutan: g16-gpu biru, g16-cpu oranye, d0-old aqua
(tiga slot pertama palet referensi dataviz, lolos cek semua-pasangan CVD). Aqua < 3:1 di
permukaan terang, jadi semua grafik memberi label nilai langsung, dan tabel ada di REPORT.md.
Varian dibedakan dengan garis putus-putus (encoding sekunder), bukan warna baru.
Satu sumbu y per grafik: besaran berbeda skala -> small multiples.
"""

import csv

import numpy as np

from bench.report import analysis as an

WARNA = {"g16-gpu": "#2a78d6", "g16-cpu": "#eb6834", "d0-old": "#1baf7a"}
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERI_W7 = [("g16-cpu", "cpu", "-", "CPU EP"), ("d0-old", "cpu", "-", "CPU EP"),
           ("g16-gpu", "cuda", "-", "CUDA EP"), ("g16-gpu", "cuda_notf32", "--", "CUDA EP, TF32 mati")]
KOMPONEN = [("muat_s", "muat data"), ("praproses_s", "praproses"), ("transfer_ke_device_s", "transfer ke GPU"),
            ("latih_loop_s", "latih (+ val per epoch)"), ("eval_s", "evaluasi")]
WARNA_KOMPONEN = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]   # slot 1-5, urutan tetap


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "axes.edgecolor": GRID, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
        "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    })
    return plt


def _simpan(fig, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160, bbox_inches="tight")
    import matplotlib.pyplot as plt

    plt.close(fig)
    return path


def grafik_speedup(out, g2=None):
    """(1) Speedup GPU murni (g16-cpu -> g16-gpu) per workload/config, dengan CI 95 % bootstrap."""
    plt = _plt()
    rows = [r for w in ("W1", "W2", "W7") for r in an.speedups(w, g2)
            if (r["pembanding"], r["dibandingkan"]) == ("g16-cpu", "g16-gpu")]
    if not rows:
        return None
    rows.sort(key=lambda r: (r["workload"], r["speedup"]))
    fig, ax = plt.subplots(figsize=(8, 0.32 * len(rows) + 1.4))
    y = np.arange(len(rows))
    for i, r in enumerate(rows):
        lo, hi = r["ci95"]
        ok = r["dilaporkan_sebagai_speedup"]
        ax.barh(i, r["speedup"], height=0.6, color=WARNA["g16-gpu"] if ok else "#c9c8c3",
                hatch=None if ok else "//", edgecolor=SURFACE, linewidth=2)
        ax.errorbar(r["speedup"], i, xerr=[[r["speedup"] - lo], [hi - r["speedup"]]], color=INK, lw=1, capsize=2)
        label = f"{r['speedup']:.2f}×" + ("" if ok else "  (tidak setara G2)")
        ax.text(hi * 1.03, i, label, va="center", fontsize=8, color=INK)
    ax.axvline(1, color=INK2, lw=1, ls="--")
    ax.set_xscale("log")
    ax.set_yticks(y, [f"{r['workload']} {r['config']}" for r in rows], fontsize=8)
    ax.set_xlabel("speedup = median waktu g16-cpu / median waktu g16-gpu (log; < 1 = GPU lebih lambat)")
    ax.set_title("Efek GPU murni per workload (mesin sama, CI 95 % bootstrap)")
    return _simpan(fig, out / "1_speedup_gpu_murni.png")


def grafik_komponen(out, cid="b256_fp32"):
    """(2) Waktu per komponen W1 per device (median), batang bertumpuk."""
    plt = _plt()
    data = [(t, an.komponen_w1(t, cid)) for t in an.TAGS]
    data = [(t, k) for t, k in data if k]
    if not data:
        return None
    fig, ax = plt.subplots(figsize=(8, 0.7 * len(data) + 1.4))
    for i, (t, k) in enumerate(data):
        kiri = 0.0
        for (key, nama), c in zip(KOMPONEN, WARNA_KOMPONEN):
            v = k.get(key) or 0.0
            if v <= 0:
                continue
            ax.barh(i, v, left=kiri, height=0.6, color=c, edgecolor=SURFACE, linewidth=2,
                    label=nama if i == 0 else None)
            kiri += v
        ax.text(kiri * 1.01, i, f"{kiri:.0f} s", va="center", fontsize=9)
    ax.set_yticks(range(len(data)), [t for t, _ in data])
    ax.set_xlabel("detik (median 5 ulangan)")
    ax.set_title(f"W1 {cid}: waktu per komponen")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=5, frameon=False, fontsize=8)
    return _simpan(fig, out / f"2_komponen_W1_{cid}.png")


def grafik_time_to_target(out):
    """(3) Time-to-target W1: hanya config yang mencapai target di >= 1 device; sisanya dicantumkan
    sebagai catatan di bawah grafik (batch besar tidak pernah mencapai target)."""
    plt = _plt()
    from matplotlib.ticker import FuncFormatter

    semua = an.configs("W1")
    nilai = {c: {t: an.time_to_target(t, c) for t in an.TAGS} for c in semua}
    cfgs = [c for c in semua if any(v and v["median_detik"] for v in nilai[c].values())]
    gagal = [c for c in semua if c not in cfgs and any(nilai[c].values())]
    if not cfgs:
        return None
    tags = [t for t in an.TAGS if any(nilai[c][t] and nilai[c][t]["median_detik"] for c in cfgs)]
    fig, ax = plt.subplots(figsize=(8, 0.75 * len(cfgs) + 2.0))
    h = 0.8 / len(tags)
    sudah_label = set()
    for i, c in enumerate(cfgs):
        for j, t in enumerate(tags):
            v = nilai[c][t]
            yy = i + (j - (len(tags) - 1) / 2) * h
            if not v:
                continue
            if v["median_detik"] is None:
                ax.text(ax.get_xlim()[0], yy, f"  {t}: tidak tercapai (0/{v['n_run']})", va="center",
                        fontsize=7, color=INK2)
                continue
            ax.barh(yy, v["median_detik"], height=h * 0.9, color=WARNA[t], edgecolor=SURFACE, linewidth=2,
                    label=None if t in sudah_label else t)
            sudah_label.add(t)
            ax.text(v["median_detik"] * 1.04, yy, f"{v['median_detik']:.0f} s ({v['n_tercapai']}/{v['n_run']})",
                    va="center", fontsize=8)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda x, _: ""))
    ax.set_xlim(right=ax.get_xlim()[1] * 1.6)
    ax.set_yticks(range(len(cfgs)), cfgs, fontsize=9)
    target = next(v["target"] for c in semua for v in nilai[c].values() if v)
    ax.set_xlabel(f"detik sampai val loss <= {target:.3f} (median run yang mencapai target, skala log)")
    ax.set_title("W1 time-to-target (lebih pendek = lebih baik)")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    if gagal:
        fig.text(0.01, -0.02, "Tidak pernah mencapai target di device mana pun: " + ", ".join(gagal),
                 fontsize=7, color=INK2, wrap=True)
    return _simpan(fig, out / "3_time_to_target_W1.png")


def _seri_w7():
    """{model: [(label, tag, gaya_garis, [(batch, p50, throughput)])]}"""
    out = {}
    for m in ["gru", "xgb_ttb"]:
        seri = []
        for t, ep, gaya, nama in SERI_W7:
            pts = []
            for b in [1, 32, 256, 1024]:
                runs, _ = an.load_runs(t, "W7", f"{m}_{ep}_b{b}")
                if runs:
                    p50 = float(np.median([r["inferensi"]["latensi_ms"]["p50"] for r in runs]))
                    pts.append((b, p50, b / (p50 / 1000)))
            if pts:
                seri.append((f"{t} {nama}", t, gaya, pts))
        out[m] = seri
    return out


def grafik_inferensi(out):
    """(4) Latensi dan throughput inferensi vs batch -- dua grafik terpisah (tanpa sumbu ganda),
    masing-masing small multiples per model."""
    plt = _plt()
    seri = _seri_w7()
    if not any(seri.values()):
        return []
    paths = []
    for idx, (judul, ylabel, fname) in enumerate([
            ("Latensi inferensi p50 per panggilan", "ms (median 5 ulangan, log)", "4a_latensi_W7.png"),
            ("Throughput inferensi", "jendela / detik (log)", "4b_throughput_W7.png")]):
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=False)
        for ax, (m, ss) in zip(axes, seri.items()):
            for label, t, gaya, pts in ss:
                xs = [p[0] for p in pts]
                ys = [p[1 + idx] for p in pts]
                ax.plot(xs, ys, gaya, color=WARNA[t], lw=2, marker="o", ms=5, label=label)
                ax.annotate(f"{ys[-1]:.3g}", (xs[-1], ys[-1]), textcoords="offset points", xytext=(4, 0),
                            fontsize=7, color=INK)
            ax.set_xscale("log", base=2)
            ax.set_yscale("log")
            ax.set_xticks([1, 32, 256, 1024], ["1", "32", "256", "1024"])
            ax.set_xlabel("ukuran batch")
            ax.set_ylabel(ylabel)
            ax.set_title(f"{judul}: {m}", fontsize=10)
            ax.legend(frameon=False, fontsize=7)
        paths.append(_simpan(fig, out / fname))
    return paths


def grafik_telemetri(out, csv_path, judul):
    """(5) Daya, suhu, clock GPU selama satu run -- tiga small multiples, satu sumbu masing-masing."""
    plt = _plt()
    from bench.telemetry import FIELDS

    rows = []
    with open(csv_path, encoding="utf-8") as f:
        for r in csv.reader(f):
            if len(r) == len(FIELDS):
                rows.append(dict(zip(FIELDS, (v.strip() for v in r))))
    if not rows:
        return None

    def col(k):
        return np.array([float(r[k]) if r[k] not in ("", "[N/A]") else np.nan for r in rows])

    t = np.arange(len(rows))
    fig, axes = plt.subplots(3, 1, figsize=(9, 6.5), sharex=True)
    for ax, (k, nama) in zip(axes, [("power.draw", "daya GPU (W)"), ("temperature.gpu", "suhu GPU (°C)"),
                                    ("clocks.sm", "clock SM (MHz)")]):
        v = col(k)
        ax.plot(t, v, color=WARNA["g16-gpu"], lw=1.5)
        ax.set_ylabel(nama)
        ax.annotate(f"median {np.nanmedian(v):.0f}, maks {np.nanmax(v):.0f}", xy=(0.99, 0.9),
                    xycoords="axes fraction", ha="right", fontsize=8, color=INK2)
    axes[-1].set_xlabel("detik sejak awal run (sampel 1 Hz)")
    axes[0].set_title(judul)
    return _simpan(fig, out / "5_telemetri_run_terpanjang.png")
