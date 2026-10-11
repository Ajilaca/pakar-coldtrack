"""Bagian laporan B6 yang dibangkitkan dari JSON: ringkasan, spesifikasi device, metodologi, B5, keterbatasan.

Dipanggil oleh bench/report/build_report.py. Semua angka berasal dari bench/results/ lewat
bench/report/analysis.py; teks kualitatif hanya memilih kata (lebih cepat/lambat/setara) dari angka itu.
"""

from statistics import mean, median

from bench.report import analysis as an

PERBANDINGAN_UTAMA = [
    # (workload, config sisi "dibandingkan", pembanding, dibandingkan, label)
    ("W1", "b256_fp32_resident", "g16-cpu", "g16-gpu", "Latih GRU 30 epoch (konfigurasi asli, data di GPU)"),
    ("W3", "gru", "g16-cpu", "g16-gpu", "Sweep GRU 8 trial × 5 epoch"),
    ("W4", "stat_vs_tanpa", "g16-cpu", "g16-gpu", "Ablation GRU 5 seed × 2 varian × 10 epoch"),
    ("W2", "cuda_hist", "g16-cpu", "g16-gpu", "Latih XGBoost TTB"),
    ("W3", "xgb_cuda", "g16-cpu", "g16-gpu", "Sweep XGBoost 20 trial"),
    ("W6", "cuda_hist", "g16-cpu", "g16-gpu", "Sensor-health Berkeley (fitur + latih)"),
    ("W7", "gru_cuda_b1", "g16-cpu", "g16-gpu", "Inferensi GRU ONNX, batch 1"),
    ("W7", "gru_cuda_b1024", "g16-cpu", "g16-gpu", "Inferensi GRU ONNX, batch 1024"),
    ("W1", "b256_fp32", "d0-old", "g16-cpu", "Latih GRU 30 epoch: laptop lama → G16 tanpa GPU"),
    ("W2", "cpu_hist", "d0-old", "g16-cpu", "Latih XGBoost: laptop lama → G16 CPU"),
    ("W7", "gru_cpu_b1", "d0-old", "g16-cpu", "Inferensi GRU batch 1: laptop lama → G16 CPU"),
    ("W1", "b256_fp32_resident", "d0-old", "g16-gpu", "Latih GRU 30 epoch: laptop lama → G16 GPU"),
    ("W3", "gru", "d0-old", "g16-cpu", "Sweep GRU: laptop lama → G16 CPU"),
    ("W4", "stat_vs_tanpa", "d0-old", "g16-cpu", "Ablation GRU: laptop lama → G16 CPU"),
    ("W4", "stat_vs_tanpa", "d0-old", "g16-gpu", "Ablation GRU: laptop lama → G16 GPU"),
    ("W8", "truk100", "d0-old", "g16-cpu", "Siklus inferensi 100 truk: laptop lama → G16 CPU (kode berbeda, lihat B5)"),
]


def _cari_speedup(w, cid, a, b, g2):
    for r in an.speedups(w, g2):
        if r["pembanding"] == a and r["dibandingkan"] == b and r["config"].split(" -> ")[-1] == cid:
            return r
    return None


def _n_run(tag, w, cid):
    return len(an.load_runs(tag, w, cid)[0])


def _kata(s):
    if s["ci95"][0] > 1:
        return "lebih cepat"
    if s["ci95"][1] < 1:
        return "lebih LAMBAT"
    return "tidak berbeda nyata"


def bagian_ringkasan(g2):
    out = [
        "## Ringkasan",
        "",
        (
            "Pertanyaan: seberapa besar laptop baru (ASUS ROG Strix G16, RTX 5070 Laptop) mempercepat pekerjaan "
            "ColdTrack dibanding laptop lama (Lenovo Yoga 6, CPU saja), dan di mana GPU tidak membantu. "
            "`g16-cpu` = G16 dengan GPU dimatikan, sehingga efek GPU murni dan efek mesin baru dapat dipisah."
        ),
        "",
        "| pekerjaan | perbandingan | speedup (median) | CI 95 % | kesimpulan | n run |",
        "|---|---|---|---|---|---|",
    ]
    for w, cid, a, b, label in PERBANDINGAN_UTAMA:
        s = _cari_speedup(w, cid, a, b, g2)
        if not s:
            out.append(f"| {label} ({w}) | {a} → {b} | belum diukur | - | - | - |")
            continue
        cid_a = an.acuan_cpu(w, cid) if b == "g16-gpu" else cid
        n = min(_n_run(a, w, cid_a), _n_run(b, w, cid))
        ci = f"[{s['ci95'][0]:.2f}, {s['ci95'][1]:.2f}]" if n >= 3 else "- (1 run)"
        kata = _kata(s) if n >= 3 else ("lebih cepat" if s["speedup"] > 1 else "lebih LAMBAT")
        if s.get("g2_setara") is False:
            kata = "kualitas tidak setara: bukan speedup"
        out.append(f"| {label} ({w}) | {a} → {b} | {s['speedup']:.2f}× | {ci} | {kata} | {n} |")
    belum = [w for w in an.B5 if not any(an.status_config("d0-old", w, c) == "ada" for c in an.configs(w))]
    out += [
        "",
        ("Cara membaca: speedup = waktu median pembanding / waktu median yang dibandingkan; > 1 berarti yang "
        "dibandingkan lebih cepat. Kualitas model antar-device dicek terpisah (G2 dan tabel B5)."),
        "",
    ]
    if belum:
        out += [f"**Belum lengkap:** paket B5 laptop lama ({', '.join(belum)}) belum diukur.", ""]
    return out


def bagian_device():
    out = [
        "## Device dan kondisi",
        "",
        "| tag | CPU | inti fisik/logis | RAM WSL (GB) | GPU | lingkungan | mode daya | env capture |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for tag in ("g16-gpu", "g16-cpu", "d0-old"):
        env, ref = an.env_tag(tag)
        kond = an.kondisi_tag(tag) or {}
        if env:
            cpu = env.get("cpu", {})
            gpus = (env.get("gpu") or {}).get("gpus") or []
            gpu = gpus[0]["name"] if gpus and tag != "g16-cpu" else ("dimatikan (CUDA_VISIBLE_DEVICES=\"\")" if gpus else "-")
            out.append(
                f"| {tag} | {cpu.get('model', '-')} | {cpu.get('physical_cores', '-')}/{cpu.get('logical_cores', '-')} | "
                f"{(env.get('memori') or {}).get('total_gb', '-')} | {gpu} | {env.get('lingkungan_dipilih', '-')} | "
                f"{kond.get('mode_daya', '-')} | `{ref}` |"
            )
        else:
            out.append(
                f"| {tag} | AMD Ryzen 7 5700U (dari user) | - | {kond.get('wslconfig_memory', '-')} | Radeon terintegrasi, "
                f"tidak dipakai | WSL2 Ubuntu 24.04 (bench/devices/d0-old.yaml) | {kond.get('mode_daya', '-')} | "
                f"**tidak ada** (`{ref}` dirujuk tetapi tidak ikut dikirim) |"
            )
    out += ["", "### Provenance (commit tiap run)", "", "| tag | commit | dirty | n run | ada di repo |", "|---|---|---|---|---|"]
    masalah = []
    for tag in ("g16-gpu", "g16-cpu", "d0-old"):
        for p in an.provenance(tag):
            out.append(f"| {tag} | `{p['commit']}` | {p['dirty']} | {p['n_run']} | {'ya' if p['ada_di_repo'] else '**tidak**'} |")
            if not p["ada_di_repo"]:
                masalah.append(f"{tag} `{p['commit']}` ({p['n_run']} run)")
    out.append("")
    if masalah:
        out += [
            "**Terbuka:** commit " + ", ".join(masalah) + " tidak ada di repo. Kemungkinan commit lokal di device "
            "itu yang hash-nya berubah saat di-rebase/amend sebelum push. Kesamaan kodenya dengan commit di repo "
            "belum dapat diverifikasi dari sini; data tetap dipakai dengan catatan ini.",
            "",
        ]
    catatan = {t: (an.kondisi_tag(t) or {}).get("catatan") for t in ("g16-gpu", "d0-old")}
    for t, c in catatan.items():
        if c:
            out += [f"Catatan kondisi {t}: {c}", ""]
    return out


def bagian_metodologi():
    return [
        "## Metodologi singkat",
        "",
        ("- Satu laptop baru, dua jalur: `g16-gpu` (CUDA) dan `g16-cpu` (GPU disembunyikan). Laptop lama `d0-old` "
        "jalur CPU. Semua di WSL2 Ubuntu 24.04, paket dikunci (`bench/requirements.lock.txt`), charger terpasang, "
        "mode daya performa tertinggi, aplikasi berat ditutup."),
        ("- W1/W2/W6/W7/W8: 1 pemanasan dibuang + 5 ulangan (seed 1000–1004), median [min–maks], speedup dengan CI 95 % "
        "bootstrap. W3/W4: satu run terukur yang berisi banyak pelatihan; sebaran antar-trial/seed ada di JSON, tetapi "
        "speedup-nya tanpa CI."),
        ("- Varian yang tidak bermakna di device itu (AMP, CUDA EP, XGBoost cuda di CPU; W8 di tag GPU) dicatat "
        "`tidak berlaku`, bukan dikosongkan. W5 (skala data simulator) tidak dijalankan: simulator v4 tidak dapat "
        "direproduksi dari repo."),
        "- Kualitas dicek agar kecepatan tidak dibeli dengan model yang lebih buruk (G2 untuk B2; tabel kualitas B5).",
        "- Split test dipakai sekali per model (`bench/results/test/test_access_log.json`); seluruh keputusan memakai val.",
        "",
    ]


def _telemetri_b5():
    rows = []
    for w in an.B5:
        for cid in an.configs(w):
            runs, _ = an.load_runs("g16-gpu", w, cid)
            tel = [r["telemetri"] for r in runs if (r.get("telemetri") or {}).get("tersedia")]
            if not tel:
                continue
            alasan = sorted({h for t in tel for h in t.get("throttle_reasons_hex", [])})
            rows.append(
                f"| {w} | {cid} | {max(t['suhu_c']['maks'] for t in tel):.0f} | "
                f"{median(t['daya_w']['median'] for t in tel):.1f} | {median(t['utilisasi_pct_median'] for t in tel):.0f} | "
                f"{', '.join(alasan)} |"
            )
    return rows


def bagian_b5(g2):
    out = [
        "## B5: benchmark W3 / W4 / W6 / W8",
        "",
        "| workload | config | metrik | " + " | ".join(an.TAGS) + " |",
        "|---|---|---|" + "---|" * len(an.TAGS),
    ]
    for w in an.B5:
        nama = an.WAKTU_UTAMA[w][0]
        for cid, per in an.waktu_per_config(w).items():
            sel = []
            for t in an.TAGS:
                v = per.get(t, {"status": "belum diukur"})
                if v["status"] != "ada":
                    # varian CPU tidak dijalankan di tag GPU (pasangannya diukur di g16-cpu)
                    sel.append("—" if t == "g16-gpu" and "cpu" in cid and v["status"] == "belum diukur" else v["status"])
                else:
                    r = v["ringkas"]
                    sel.append(f"{r['median']:.4g}" if r["n"] == 1 else f"{r['median']:.4g} [{r['min']:.4g}–{r['maks']:.4g}]")
            out.append(f"| {w} | {cid} | {nama} (s) | " + " | ".join(sel) + " |")
    out += [
        "",
        ("Median [min–maks] dari 5 ulangan; satu angka = satu run terukur. '—' = varian CPU tidak dijalankan di tag GPU "
        "(pasangannya diukur di g16-cpu). Sumber: `bench/results/<tag>/<W3|W4|W6|W8>/<config>/run_*.json`"),
        "",
    ]

    out += ["### Speedup B5", "", "| workload | config | perbandingan | arti | speedup | CI 95 % |", "|---|---|---|---|---|---|"]
    for w in an.B5:
        for r in an.speedups(w, g2):
            cid_b = r["config"].split(" -> ")[-1]
            cid_a = r["config"].split(" -> ")[0]
            n = min(_n_run(r["pembanding"], w, cid_a), _n_run(r["dibandingkan"], w, cid_b))
            ci = f"[{r['ci95'][0]:.2f}, {r['ci95'][1]:.2f}]" if n >= 3 else "- (1 run)"
            out.append(f"| {w} | {r['config']} | {r['pembanding']} → {r['dibandingkan']} | {r['arti']} | {r['speedup']:.2f}× | {ci} |")
    out.append("")

    # kualitas: kecepatan GPU tidak boleh dibeli dengan model yang berbeda mutunya
    out += ["### Paritas kualitas B5 (val)", "", "| workload | config | metrik | g16-gpu | g16-cpu | d0-old |", "|---|---|---|---|---|---|"]

    def ambil(tag, w, cid, f):
        runs, _ = an.load_runs(tag, w, cid)
        try:
            return f(runs) if runs else None
        except (KeyError, TypeError):
            return None

    def fmt(x):
        return "-" if x is None else f"{x:.4f}"

    kual = [
        ("W3", ("gru", "gru", "gru"), "skor terbaik sweep", lambda rs: rs[0]["skor_terbaik"]),
        ("W3", ("xgb_cuda", "xgb_cpu", "xgb_cpu"), "skor terbaik sweep", lambda rs: rs[0]["skor_terbaik"]),
        ("W4", ("stat_vs_tanpa",) * 3, "macro F1 mean 5 seed, dengan statistik",
         lambda rs: mean(x["macro_f1"] for x in rs[0]["varian"]["dengan_stat"]["runs"])),
        ("W4", ("stat_vs_tanpa",) * 3, "macro F1 mean 5 seed, tanpa statistik",
         lambda rs: mean(x["macro_f1"] for x in rs[0]["varian"]["tanpa_stat"]["runs"])),
        ("W6", ("cuda_hist", "cpu_hist", "cpu_hist"), "PR-AUC mote val", lambda rs: median(r["metrik_val"]["pr_auc"] for r in rs)),
    ]
    for w, (cg, cc, cd), metrik, f in kual:
        out.append(f"| {w} | {cg} / {cc} | {metrik} | {fmt(ambil('g16-gpu', w, cg, f))} | {fmt(ambil('g16-cpu', w, cc, f))} | "
                   f"{fmt(ambil('d0-old', w, cd, f))} |")
    out.append("")

    tel = _telemetri_b5()
    if tel:
        out += [
            "### Telemetri GPU selama B5 (g16-gpu)",
            "",
            "| workload | config | suhu maks (°C) | daya median (W) | utilisasi median (%) | alasan throttle (NVML) |",
            "|---|---|---|---|---|---|",
            *tel,
            "",
            ("Alasan throttle `0x4` = batas daya perangkat lunak (wajar di laptop), `0x0` = tidak ada. Tidak ada alasan "
            "termal (`0x20`/`0x40`) yang tercatat."),
            "",
        ]
    w6 = {}
    for tag, cid in (("g16-gpu", "cuda_hist"), ("g16-cpu", "cpu_hist")):
        runs, _ = an.load_runs(tag, "W6", cid)
        if runs:
            w6[tag] = (median(r["waktu"]["bangun_total_s"] for r in runs), median(r["waktu"]["dinding_total_s"] for r in runs),
                       median(r["waktu"]["latih_s"] for r in runs))
    w6_teks = "; ".join(f"{t}: bangun fitur {v[0]:.2f} s dari total {v[1]:.2f} s, latih {v[2]:.2f} s" for t, v in w6.items())
    out += [
        "### Catatan B5",
        "",
        (f"- **W6:** waktu didominasi pemuatan data dan pembangunan fitur di CPU ({w6_teks}), jadi GPU hampir tidak "
        "mengubah waktu total. Prediksi XGBoost di jalur GPU juga jatuh ke DMatrix karena data input ada di CPU "
        "(peringatan XGBoost `mismatched devices`); ini sedikit merugikan sisi GPU dan tidak diperbaiki di tengah benchmark."),
        ("- **W8** mengukur komputasi siklus inferensi (`POST /api/v1/analyze`, sama dengan `predict_last` worker armada) "
        "tanpa database dan broker. Varian 2 inti adalah G16 yang dibatasi 2 inti, **bukan** VPS 2 vCPU; tidak ada klaim "
        "target PRD (< 30 s / 100 truk di VPS 2 vCPU) terpenuhi."),
        "- **W3/W4** satu run terukur per tag (banyak pelatihan di dalamnya), jadi speedup-nya tanpa CI.",
        "",
    ]
    return out


# jalur kode yang menentukan hasil tiap workload (untuk cek kesamaan kode antar-device)
JALUR_KODE = {
    "W3": ["bench", "ml"],
    "W4": ["bench", "ml"],
    "W6": ["bench", "ml"],
    "W8": ["bench", "backend/app", "backend/models", "backend/config.yaml"],
}


def _commit_workload(tag, w):
    import json

    return {json.loads(f.read_text(encoding="utf-8"))["git"]["commit"][:7]
            for f in (an.RESULTS_DIR / tag / w).glob("*/run_*.json")}


def _kode_sama(c1, c2, jalur):
    """(identik?, berkas berbeda) untuk jalur kode antara dua commit, tanpa hasil, laporan, dan dokumen."""
    import subprocess

    spec = [*jalur, ":(exclude)bench/results", ":(exclude)bench/report", ":(exclude)*.md"]
    r = subprocess.run(["git", "diff", "--name-only", c1, c2, "--", *spec], capture_output=True, text=True, check=False)
    if r.returncode != 0:
        return None, []
    beda = [f for f in r.stdout.split() if f]
    return not beda, beda


def _dipakai(path, w):
    """Apakah berkas yang berubah ikut menentukan hasil workload w.

    Tidak dipakai: metadata device (bench/devices/*.yaml, disalin ke JSON sebagai kondisi), modul workload lain,
    dan modul Python yang tidak di-import oleh kode mana pun di bench/ atau ml/ (mis. skrip seed armada).
    """
    import re
    from pathlib import Path

    if path.startswith("bench/devices/"):
        return False
    m = re.match(r"bench/workloads/(w\d)_", path)
    if m:
        return m.group(1).upper() == w
    if not path.endswith(".py") or path.startswith("backend/"):
        return True
    stem = Path(path).stem
    pola = re.compile(rf"(import|from)\s+[\w.]*\b{re.escape(stem)}\b")
    for f in [*an.ROOT.joinpath("bench").rglob("*.py"), *an.ROOT.joinpath("ml").rglob("*.py")]:
        if f.as_posix().endswith(path) or "__pycache__" in f.parts:
            continue
        if pola.search(f.read_text(encoding="utf-8", errors="ignore")):
            return True
    return False


def bagian_kesamaan_kode():
    out = [
        "### Kesamaan kode antar-device (B5)",
        "",
        "| workload | commit g16-cpu | commit d0-old | kode workload | berkas berbeda |",
        "|---|---|---|---|---|",
    ]
    for w, jalur in JALUR_KODE.items():
        cg, cd = sorted(_commit_workload("g16-cpu", w)), sorted(_commit_workload("d0-old", w))
        if not cg or not cd:
            out.append(f"| {w} | {', '.join(cg) or '-'} | {', '.join(cd) or '-'} | belum dapat dibandingkan | - |")
            continue
        sama, beda = _kode_sama(cg[0], cd[0], jalur)
        relevan = [b for b in beda if _dipakai(b, w)]
        if sama is None:
            status = "tidak dapat dicek"
        elif not relevan:
            status = "identik" if sama else "identik (berkas berbeda tidak dipakai workload ini)"
        else:
            status = "**berbeda**"
        daftar = ", ".join(f"`{b}`" for b in (relevan or beda)[:6]) + (" …" if len(relevan or beda) > 6 else "")
        out.append(f"| {w} | {', '.join(cg)} | {', '.join(cd)} | {status} | {daftar or '-'} |")
    out += [
        "",
        ("W8 mengirim jendela 60 bacaan ke `POST /api/v1/analyze`; di kedua versi backend model dijalankan untuk satu "
         "jendela, tetapi kodenya tidak identik (versi armada menambah `predict_last` dan konversi zona waktu). "
         "Perbandingan W8 antar-device dibaca dengan catatan ini."),
        "",
    ]
    return out


def bagian_keterbatasan():
    return [
        "## Keterbatasan",
        "",
        "- Satu unit per device dan satu mode daya; hasil laptop lain dengan seri yang sama bisa berbeda (termal, BIOS).",
        ("- Model kecil (GRU 3×128, XGBoost), sehingga GPU sering tidak terpakai penuh; percepatan GPU untuk model "
        "besar tidak dapat disimpulkan dari sini."),
        "- Data simulasi (dataset v4), bukan logger truk nyata.",
        "- WSL2 dengan batas memori 12 GB di kedua laptop; Windows native tidak diukur.",
        ("- Laptop lama mengalami throttling termal pada run pertama; run itu dibatalkan dan diulang dalam mode "
         "Extreme Performance. Menurut pesan commit `4c193ca`, CPU-nya tetap di-throttle termal secara berkala selama "
         "paket B5 (±100 °C → ±22 % performa); data suhunya tidak ada di repo. Angka laptop lama, terutama B5, bisa "
         "lebih lambat daripada kemampuan CPU itu dengan pendinginan baik, sehingga speedup laptop lama → G16 "
         "cenderung dilebih-lebihkan."),
        "- Commit run laptop lama dan berkas env capture-nya belum dapat diverifikasi dari repo (lihat Provenance).",
        "",
    ]
