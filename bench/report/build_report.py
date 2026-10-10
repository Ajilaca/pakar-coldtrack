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
        out += [f"### {tag} — {r['n_lulus']}/{r['n_dicek']} metrik lulus aturan ketat", "",
                "| model | metrik | mean ± SD (5 seed) | rentang ±2 SD | acuan val | aturan ketat |",
                "|---|---|---|---|---|---|"]
        for model, h in g1.items():
            if model.startswith("_"):
                continue
            for metrik, m in h["metrik"].items():
                lo, hi = m["rentang_2sd"]
                status = "tanpa acuan" if m["lulus"] is None else ("lulus" if m["lulus"] else "tidak")
                out.append(f"| {model} | {metrik} | {_fmt(m['mean'])} ± {_fmt(m['sd'])} | "
                           f"[{_fmt(lo)}, {_fmt(hi)}] | {_fmt(m['acuan'])} | {status} |")
        out += ["", f"Sumber: `bench/results/{tag}/B1/G1.json`", ""]

    out += ["### Alasan \"lulus dengan catatan\"", ""]
    for a in kep["alasan"]:
        sumber = ", ".join(f"`{s}`" for s in a["sumber"])
        out.append(f"- **{a['model']}** — {a['ringkas']} {a['detail']} (sumber: {sumber})")

    inv_p = RESULTS_DIR / "g16-cpu" / "B1" / "G1_investigasi.json"
    if inv_p.exists():
        inv = _load(inv_p)
        kunci = list(inv["acuan"])
        out += ["", f"Investigasi acuan XGBoost (XGBoost {inv['xgboost']}, split val):", "",
                "| kombinasi | " + " | ".join(kunci) + " |", "|---" * (len(kunci) + 1) + "|",
                "| **acuan baseline_metrics.json** | " + " | ".join(_fmt(inv["acuan"][k]) for k in kunci) + " |"]
        for nama, m in inv["kombinasi"].items():
            out.append(f"| {nama} | " + " | ".join(_fmt(m[k]) for k in kunci) + " |")
        out += ["", "Sumber: `bench/results/g16-cpu/B1/G1_investigasi.json`"]

    bb = kep["baseline_baru"]
    out += ["", f"**Baseline baru:** {bb['keputusan']} Sumber: "
            + ", ".join(f"`{v}`" for v in bb["sumber"].values()) + "."]
    if kep.get("catatan_terbuka"):
        out += ["", "Catatan terbuka: " + " ".join(kep["catatan_terbuka"])]
    return out + [""]


def main():
    lines = [
        "# Laporan latih ulang ColdTrack + benchmark device",
        "",
        f"> Dibangkitkan oleh `bench/report/build_report.py` pada {now_iso()}. Jangan diedit manual:",
        "> setiap angka berasal dari JSON di `bench/results/`.",
        "",
        *bagian_g1(),
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Tersimpan: {OUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
