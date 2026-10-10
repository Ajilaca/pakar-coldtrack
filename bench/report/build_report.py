"""Bangun bench/report/REPORT.md dari JSON di bench/results/ -- tidak ada angka yang diketik manual.

  python -m bench.report.build_report

Saat ini memuat bagian gerbang (G1). Bagian workload, grafik, dan summary.csv ditambahkan di B6.
"""

import json

from bench.common import RESULTS_DIR, ROOT, now_iso

OUT = ROOT / "bench" / "report" / "REPORT.md"
TAGS = ["g16-cpu", "g16-gpu", "d0-old"]


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt(x, nd=4):
    return "-" if x is None else f"{x:.{nd}f}"


def bagian_g1():
    kep_path = RESULTS_DIR / "keputusan" / "G1.json"
    if not kep_path.exists():
        return ["## Gerbang G1 (reproduksi)", "", "Belum diputuskan.", ""]
    kep = _load(kep_path)
    out = [
        "## Gerbang G1 (reproduksi)",
        "",
        f"**Status: {kep['status']}** (diputuskan {kep['tanggal']}, {kep['diputuskan_oleh']}).",
        f"Aturan ketat: {kep['hasil_aturan_ketat']['aturan']}.",
        "",
    ]
    for tag in TAGS:
        p = RESULTS_DIR / tag / "B1" / "G1.json"
        if not p.exists():
            continue
        g1 = _load(p)
        r = g1["_ringkas"]
        out += [
            f"### {tag} — {r['n_lulus']}/{r['n_dicek']} metrik lulus aturan ketat",
            "",
            "| model | metrik | mean ± SD (5 seed) | rentang ±2 SD | acuan val | aturan ketat |",
            "|---|---|---|---|---|---|",
        ]
        for model, h in g1.items():
            if model.startswith("_"):
                continue
            for metrik, m in h["metrik"].items():
                lo, hi = m["rentang_2sd"]
                status = "tanpa acuan" if m["lulus"] is None else ("lulus" if m["lulus"] else "tidak")
                out.append(
                    f"| {model} | {metrik} | {_fmt(m['mean'])} ± {_fmt(m['sd'])} | "
                    f"[{_fmt(lo)}, {_fmt(hi)}] | {_fmt(m['acuan'])} | {status} |"
                )
        out += ["", f"Sumber: `bench/results/{tag}/B1/G1.json`", ""]

    out += ['### Alasan "lulus dengan catatan"', ""]
    for a in kep["alasan"]:
        sumber = ", ".join(f"`{s}`" for s in a["sumber"])
        out.append(f"- **{a['model']}** — {a['ringkas']} {a['detail']} (sumber: {sumber})")

    inv_p = RESULTS_DIR / "g16-cpu" / "B1" / "G1_investigasi.json"
    if inv_p.exists():
        inv = _load(inv_p)
        kunci = list(inv["acuan"])
        out += [
            "",
            f"Investigasi acuan XGBoost (XGBoost {inv['xgboost']}, split val):",
            "",
            "| kombinasi | " + " | ".join(kunci) + " |",
            "|---" * (len(kunci) + 1) + "|",
            "| **acuan baseline_metrics.json** | " + " | ".join(_fmt(inv["acuan"][k]) for k in kunci) + " |",
        ]
        for nama, m in inv["kombinasi"].items():
            out.append(f"| {nama} | " + " | ".join(_fmt(m[k]) for k in kunci) + " |")
        out += ["", "Sumber: `bench/results/g16-cpu/B1/G1_investigasi.json`"]

    bb = kep["baseline_baru"]
    out += [
        "",
        f"**Baseline baru:** {bb['keputusan']} Sumber: " + ", ".join(f"`{v}`" for v in bb["sumber"].values()) + ".",
    ]
    if kep.get("catatan_terbuka"):
        out += ["", "Catatan terbuka: " + " ".join(kep["catatan_terbuka"])]
    return out + [""]


def _fmt_waktu(v):
    if v["status"] != "ada":
        return v["status"]
    r = v["ringkas"]
    return f"{r['median']:.3g} [{r['min']:.3g}–{r['maks']:.3g}]"


def bagian_b2(g2, gambar):
    from statistics import mean

    from bench.report import analysis as an

    out = [
        "## B2: benchmark W1 / W2 / W7",
        "",
        (
            "Protokol: 1 pemanasan dibuang + 5 ulangan (seed 1000–1004), median [min–maks]. Kondisi per run "
            "tercatat di JSON (`kondisi_manual`, `env`, `telemetri`). `belum diukur` = device belum menjalankan; "
            "`tidak berlaku` = varian tidak bermakna di device itu."
        ),
        "",
    ]

    # W1
    out += [
        "### W1: latih GRU (30 epoch, split val)",
        "",
        "| config | "
        + " | ".join(f"{t} detik latih" for t in an.TAGS)
        + " | F1 val (mean, GPU) | time-to-target GPU |",
        "|---" * (len(an.TAGS) + 3) + "|",
    ]
    for cid, per in an.waktu_per_config("W1").items():
        g_runs, _ = an.load_runs("g16-gpu", "W1", cid)
        f1 = _fmt(mean(r["metrik_val"]["macro_f1"] for r in g_runs)) if g_runs else "-"
        tt = an.time_to_target("g16-gpu", cid)
        tts = (
            "-"
            if not tt
            else (
                f"{tt['median_detik']:.0f} s ({tt['n_tercapai']}/{tt['n_run']})"
                if tt["median_detik"]
                else f"tidak tercapai (0/{tt['n_run']})"
            )
        )
        out.append(
            f"| {cid} | "
            + " | ".join(_fmt_waktu(per.get(t, {"status": "belum diukur"})) for t in an.TAGS)
            + f" | {f1} | {tts} |"
        )
    out += ["", "Sumber: `bench/results/<tag>/W1/<config>/run_*.json`", ""]

    # speedup
    out += [
        "### Speedup (median pembanding / median yang dibandingkan, CI 95 % bootstrap)",
        "",
        "| workload | config | perbandingan | arti | speedup | CI 95 % | G2 |",
        "|---|---|---|---|---|---|---|",
    ]
    for w in ("W1", "W2", "W7"):
        for r in an.speedups(w, g2):
            g2s = {None: "-", True: "setara", False: "**tidak setara: bukan speedup**"}[r["g2_setara"]]
            out.append(
                f"| {w} | {r['config']} | {r['pembanding']} → {r['dibandingkan']} | {r['arti']} | "
                f"{r['speedup']:.2f}× | [{r['ci95'][0]:.2f}, {r['ci95'][1]:.2f}] | {g2s} |"
            )
    out += [
        "",
        (
            "Speedup < 1 berarti yang dibandingkan lebih LAMBAT. Batch besar (b1024/b4096) setara antar-device "
            "pada batch yang sama, tetapi kualitasnya di bawah konfigurasi asli b256 dan tidak mencapai target "
            "time-to-target: kecepatannya tidak boleh dibaca sebagai percepatan pelatihan model yang sama."
        ),
        "",
    ]

    # W2 dan W7 ringkas
    for w, judul in (("W2", "W2: XGBoost TTB (detik latih)"), ("W7", "W7: inferensi ONNX (latensi p50, ms)")):
        out += [f"### {judul}", "", "| config | " + " | ".join(an.TAGS) + " |", "|---" * (len(an.TAGS) + 1) + "|"]
        for cid, per in an.waktu_per_config(w).items():
            out.append(
                f"| {cid} | " + " | ".join(_fmt_waktu(per.get(t, {"status": "belum diukur"})) for t in an.TAGS) + " |"
            )
        out += ["", f"Sumber: `bench/results/<tag>/{w}/<config>/run_*.json`", ""]

    if g2:
        r = g2["_ringkas"]
        out += [
            "## Gerbang G2 (paritas kualitas CPU vs GPU)",
            "",
            (
                f"**{r['n_setara']}/{r['n_config']} config setara.** Kriteria ditetapkan sebelum run penuh "
                f"(`bench/g2_check.py`): W1 selisih mean ≤ rentang antar-seed; W2/W7 selisih relatif ≤ "
                f"{g2['kriteria']['W2_W7_rel']:.0%}, akurasi ≤ {g2['kriteria']['W7_akurasi_abs']}."
            ),
            "Tidak setara: " + (", ".join(r["tidak_setara"]) or "tidak ada") + ".",
            "",
            "Sumber: `bench/results/G2.json`",
            "",
        ]
    if gambar:
        out += ["### Grafik", ""] + [f"![{p.stem}](figures/{p.name})" for p in gambar] + [""]
    return out


def bagian_b3():
    b3 = RESULTS_DIR / "g16-gpu" / "B3"
    if not (b3 / "keputusan_kandidat.json").exists():
        return []
    diag = _load(b3 / "diagnosis.json")
    lab = _load(b3 / "label_check.json")
    kep = _load(b3 / "keputusan_kandidat.json")
    sw = {m: _load(b3 / f"sweep_{m}" / "ringkasan.json") for m in ("gru", "xgb")}
    out = [
        "## B3: latih ulang sesuai PRD (split val)",
        "",
        "### Diagnosis baseline",
        "",
        "| kelas | F1 GRU (mean 5 seed) | F1 XGBoost | n |",
        "|---|---|---|---|",
    ]
    for k, v in diag["ringkas_gru"]["f1_per_kelas_mean"].items():
        x = diag["xgb_clf"]["per_kelas"][k]
        out.append(f"| {k} | {_fmt(v, 3)} | {_fmt(x['f1'], 3)} | {x['n']} |")
    out += [
        "",
        "| menit sejak onset | " + " | ".join(diag["ringkas_gru"]["akurasi_per_bucket_mean"]) + " |",
        "|---" * (len(diag["ringkas_gru"]["akurasi_per_bucket_mean"]) + 1) + "|",
        "| akurasi mode GRU | "
        + " | ".join(_fmt(v, 3) for v in diag["ringkas_gru"]["akurasi_per_bucket_mean"].values())
        + " |",
        "",
        "Sumber: `bench/results/g16-gpu/B3/diagnosis.json`",
        "",
        "### Batas label implisit (dari data, tanpa model)",
        "",
        (
            "Label `failure_mode` bertahan dari onset sampai akhir trip, sedangkan A1 (pintu) dan A7 (kejut ambien) "
            "adalah peristiwa sementara. Porsi jendela berlabel kelas itu yang tidak memuat jejak peristiwanya:"
        ),
        "",
        "| kelas | total tanpa jejak | "
        + " | ".join(next(iter(lab["kelas"].values()))["per_bucket_menit_sejak_onset"])
        + " | jendela A0 dengan jejak |",
        "|---" * 8 + "|",
    ]
    for k, v in lab["kelas"].items():
        out.append(
            f"| {k} | {v['porsi_tanpa_jejak_total']:.1%} | "
            + " | ".join(f"{b['porsi_tanpa_jejak']:.1%}" for b in v["per_bucket_menit_sejak_onset"].values())
            + f" | {v['porsi_A0_dengan_jejak']:.1%} |"
        )
    out += [
        "",
        (
            "Jendela tanpa jejak tidak bisa dibedakan dari jendela sehat oleh model berbasis jendela apa pun; "
            "ini membatasi Macro F1 yang dapat dicapai. Definisi metrik dan target TIDAK diubah."
        ),
        "Sumber: `bench/results/g16-gpu/B3/label_check.json`",
        "",
        "### Sweep (W3) dan konfirmasi 5 seed + ablation (W4)",
        "",
    ]
    for m, s in sw.items():
        out.append(
            f"- Sweep {m}: {s['n_trial']} trial, {s['detik_total'] / 60:.0f} menit "
            f"({s['trial_per_jam']:.0f} trial/jam, {kep['tag']}), skor terbaik {s['terbaik'][0]['skor']:.4f}."
        )
    out += [
        "",
        "| model | varian | skor mean | rentang | Macro F1 | PR-AUC | forecast t+30 |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in ("gru", "xgb"):
        for nama, h in kep[m].items():
            out.append(
                f"| {m} | {nama} | {_fmt(h['skor_mean'])} | {_fmt(h['rentang'])} | {_fmt(h['macro_f1_mean'])} | "
                f"{_fmt(h['anomali_pr_auc_mean'])} | {_fmt(h.get('forecast_t30_mae_c_mean'))} |"
            )
    out += [
        "",
        (
            f"Aturan adopsi (didaftarkan sebelum sweep): kandidat lolos bila skor mean > mean baseline + rentang "
            f"baseline. Kandidat lolos: {kep['kandidat_terbaik']}. Untuk XGBoost, baseline deterministik (rentang 0) "
            "sehingga selisih sekecil apa pun lolos; kenaikannya tidak berarti secara praktis."
        ),
        "Sumber: `bench/results/g16-gpu/B3/keputusan_kandidat.json`",
        "",
    ]
    ex = b3 / "export_kandidat.json"
    lat = RESULTS_DIR / "g16-cpu" / "B3" / "latensi_kandidat.json"
    if ex.exists():
        e = _load(ex)
        out += [
            "### Kandidat yang diajukan ke G3",
            "",
            (
                f"`{e['onnx']}` ({e['varian']}, {e['parameter']:,} parameter, seed final {e['seed_final']}); "
                f"paritas ONNX vs PyTorch: {'OK' if e['paritas_ok'] else 'GAGAL'}. "
                "Metrik val yang dilaporkan adalah mean 5 seed di tabel atas; metrik model seed 1000 "
                "optimistis karena konfigurasinya dipilih memakai seed itu."
            ),
            "",
        ]
    if lat.exists():
        la = _load(lat)
        out += ["| model (CPU EP) | p50 batch 1 (ms) | p50 batch 1024 (ms) |", "|---|---|---|"]
        for nama, v in la["model"].items():
            out.append(
                f"| {nama} | {_fmt(v['b1']['latensi_ms']['p50'], 3)} | {_fmt(v['b1024']['latensi_ms']['p50'], 1)} |"
            )
        out += ["", "Sumber: `bench/results/g16-cpu/B3/latensi_kandidat.json`", ""]
    return out


def bagian_g3():
    tdir = RESULTS_DIR / "test"
    files = {p.stem: _load(p) for p in sorted(tdir.glob("*.json"))} if tdir.exists() else {}
    if not files:
        return []
    log = _load(RESULTS_DIR / "test_access_log.json")
    kunci = list(next(iter(files.values()))["metrik_test"])
    out = ["## Gerbang G3: split test (dipakai sekali per model)", "",
           "| metrik (test) | " + " | ".join(files) + " |", "|---" * (len(files) + 1) + "|"]
    for k in kunci:
        out.append(f"| {k} | " + " | ".join(_fmt(f["metrik_test"].get(k)) for f in files.values()) + " |")
    out += ["", "Log akses split test (dicatat sebelum evaluasi; run kedua untuk id yang sama ditolak):", ""]
    out += [f"- `{e['id']}`: {e['model']} (sha256 {e['sha256_model'][:12]}…), {e['waktu_utc']}, commit "
            f"{(e['git']['commit'] or '')[:7]}" for e in log]
    kep = RESULTS_DIR / "keputusan" / "G3.json"
    if kep.exists():
        k = _load(kep)
        out += ["", f"**Keputusan G3: {k['status']}** ({k['tanggal']}). " + " ".join(k.get("alasan", []))]
    else:
        out += ["", "**Keputusan G3: menunggu keputusan user** (model mana yang diganti, trade-off latensi)."]
    return out + ["", "Sumber: `bench/results/test/*.json`, `bench/results/test_access_log.json`", ""]


def tulis_summary_csv():
    import csv

    from bench.report import analysis as an

    rows = an.summary_rows()
    kolom = ["workload", "config", "tag", "status", "metrik", "n", "median", "min", "maks", "sumber"]
    with open(OUT.parent / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=kolom)
        w.writeheader()
        w.writerows(rows)


def buat_grafik(g2):
    from bench.report import plots

    fig = OUT.parent / "figures"
    gambar = [
        plots.grafik_speedup(fig, g2),
        plots.grafik_komponen(fig, "b256_fp32"),
        plots.grafik_komponen(fig, "b256_fp32_resident"),
        plots.grafik_time_to_target(fig),
        *plots.grafik_inferensi(fig),
    ]
    # (5) telemetri run GPU terpanjang (dinding_total_s terbesar di g16-gpu W1)
    terpanjang = None
    for p in (RESULTS_DIR / "g16-gpu" / "W1").glob("*/run_*.json"):
        r = _load(p)
        csvp = r.get("telemetri", {}).get("csv")
        if csvp and (ROOT / csvp).exists() and (not terpanjang or r["waktu"]["dinding_total_s"] > terpanjang[0]):
            terpanjang = (r["waktu"]["dinding_total_s"], ROOT / csvp, f"{r['config_id']} run {r['run']}")
    if terpanjang:
        gambar.append(
            plots.grafik_telemetri(fig, terpanjang[1], f"Telemetri GPU, run terpanjang (W1 {terpanjang[2]})")
        )
    return [g for g in gambar if g]


def main():
    g2p = RESULTS_DIR / "G2.json"
    g2 = _load(g2p) if g2p.exists() else None
    gambar = buat_grafik(g2)
    tulis_summary_csv()
    lines = [
        "# Laporan latih ulang ColdTrack + benchmark device",
        "",
        f"> Dibangkitkan oleh `bench/report/build_report.py` pada {now_iso()}. Jangan diedit manual:",
        "> setiap angka berasal dari JSON di `bench/results/`. Tabel lengkap: `summary.csv`.",
        "",
        *bagian_g1(),
        *bagian_b2(g2, gambar),
        *bagian_b3(),
        *bagian_g3(),
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Tersimpan: {OUT.relative_to(ROOT).as_posix()} + summary.csv + {len(gambar)} grafik")


if __name__ == "__main__":
    main()
