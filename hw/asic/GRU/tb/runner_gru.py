"""Runner verifikasi gru_engine (Verilator dari OSS CAD Suite, sama dengan hw/tb/runner.py).

  python hw/asic/GRU/tb/runner_gru.py                 # kasus acak kecil + header rusak + jendela val coldtrack_v5
  python hw/asic/GRU/tb/runner_gru.py --acak 50       # jumlah model acak
  python hw/asic/GRU/tb/runner_gru.py --tanpa-v5      # tanpa model penuh (cepat)

Tiap kasus: golden membuat image flash + memori masukan + harapan, lalu RTL dijalankan dengan jeda aliran acak.
Model v5 diambil dari hw/asic/GRU/model/coldtrack_v5_gru.bin (dibuat make_image.py), jendela dari
tb/vectors/v5_val.npz; golden dibaca dari image itu sendiri (tanpa onnx).
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np

GRU = Path(__file__).resolve().parents[1]
HW = GRU.parents[1]
sys.path.insert(0, str(GRU / "golden"))
sys.path.insert(0, str(HW / "tb"))
import gru_golden as G  # noqa: E402
from runner import OSS  # noqa: E402

KERJA = HW / "build" / "asic_gru_kasus"


def tulis_kasus(nama, img, words, exp):
    d = KERJA / nama
    d.mkdir(parents=True, exist_ok=True)
    (d / "img.hex").write_text("\n".join(f"{b:02x}" for b in img) + "\n")
    (d / "xin.hex").write_text("\n".join(f"{w & 0xFFFFFFFF:08x}" for w in words) + "\n")
    (d / "exp.txt").write_text(" ".join(str(int(v)) for v in exp) + "\n")
    return d


def kasus_acak(n, rng):
    out = []
    for i in range(n):
        L = int(rng.integers(1, 4)); H = int(rng.choice([1, 3, 8, 16, 32])); NI = int(rng.integers(1, 7))
        NC = int(rng.integers(0, 4)); T = int(rng.integers(2, 12)); NO = int(rng.integers(1, 9))
        p = G.params_acak(rng, L, H, NI, NC, NO, skala=float(rng.uniform(0.1, 1.5)))
        m = G.kuantisasi(p, T)
        xr = G.raw_q(p["mean"] + rng.normal(0, 2, (T, NI)) * p["std"])
        cr = G.raw_q(p["cmean"] + rng.normal(0, 2, NC) * p["cstd"])
        if i % 7 == 3:   # nilai ekstrem: saturasi normalisasi dan LUT
            xr = G.raw_q(p["mean"] + rng.choice([-60, 60], (T, NI)) * p["std"])
        exp = G.maju(m, xr[None], cr[None])[0]
        out.append((f"acak{i:03d}_L{L}H{H}NI{NI}NC{NC}T{T}NO{NO}", tulis_kasus(
            f"acak{i:03d}", G.image(m), G.kata_masukan(xr, cr), exp), int(rng.integers(0, 60))))
    return out


def kasus_rusak(rng):
    p = G.params_acak(rng, 1, 4, 2, 1, 2)
    m = G.kuantisasi(p, 4)
    img = bytearray(G.image(m)); img[3] = 9          # L = 9 > LMAX
    d = KERJA / "rusak"; d.mkdir(parents=True, exist_ok=True)
    (d / "img.hex").write_text("\n".join(f"{b:02x}" for b in img) + "\n")
    (d / "xin.hex").write_text("00000000\n")
    (d / "exp.txt").write_text("ERR\n")
    return [("header_rusak", d, 0)]


def kasus_v5(n, image="coldtrack_v5_gru.bin"):
    img = (GRU / "model" / image).read_bytes()
    tag = Path(image).stem.replace("coldtrack_", "").replace("_gru", "")
    m = G.baca_image(img)
    v = np.load(GRU / "tb" / "vectors" / "v5_val.npz")
    out = []
    for i in range(min(n, len(v["xr"]))):
        exp = G.maju(m, v["xr"][i:i + 1], v["cr"][i:i + 1])[0]
        out.append((f"{tag}_val{i}_{v['label'][i]}", tulis_kasus(f"{tag}_{i}", img, G.kata_masukan(v["xr"][i], v["cr"][i]), exp),
                    int([0, 25, 50][i % 3])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--acak", type=int, default=25)
    ap.add_argument("--v5", type=int, default=3)
    ap.add_argument("--tanpa-v5", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--image", default="coldtrack_v5_gru.bin", help="image di hw/asic/GRU/model/ untuk kasus model penuh")
    a = ap.parse_args()
    from cocotb_tools.runner import get_runner

    if (OSS / "bin").exists() and str(OSS / "bin") not in os.environ["PATH"]:
        os.environ["PATH"] = f"{OSS / 'bin'}{os.pathsep}{os.environ['PATH']}"
    G.tulis_lut_sv(GRU / "rtl" / "gru_lut.svh")
    rng = np.random.default_rng(a.seed)
    kasus = kasus_acak(a.acak, rng) + kasus_rusak(rng) + ([] if a.tanpa_v5 else kasus_v5(a.v5, a.image))
    build = HW / "build" / "asic_gru_tb_verilator"
    r = get_runner("verilator")
    r.build(sources=[GRU / "rtl" / "gru_engine.sv", GRU / "tb" / "gru_tb.sv"], includes=[GRU / "rtl"],
            hdl_toplevel="gru_tb", build_dir=build, timescale=("1ns", "1ps"), always=True,
            build_args=["-Wno-fatal", "--timing", "--x-initial", "unique", "--x-assign", "unique", "-O3"])
    gagal = []
    for nama, d, stall in kasus:
        xml = r.test(hdl_toplevel="gru_tb", test_module="test_gru", build_dir=build, test_dir=GRU / "tb",
                     plusargs=[f"+IMG={d / 'img.hex'}", f"+XIN={d / 'xin.hex'}", f"+STALL={stall}",
                               "+verilator+rand+reset+2", f"+verilator+seed+{len(gagal) + 1}"],
                     extra_env={"GRU_EXP": str(d / "exp.txt")}, results_xml=str(build / f"hasil_{nama}.xml"))
        teks = Path(xml).read_text()
        ok = "<failure" not in teks and "<error" not in teks
        print(f"{'LULUS' if ok else 'GAGAL'}  {nama}  (stall {stall}%)", flush=True)
        if not ok:
            gagal.append(nama)
    print(f"\n{len(kasus) - len(gagal)}/{len(kasus)} kasus lulus" + (f"; gagal: {gagal}" if gagal else ""))
    sys.exit(1 if gagal else 0)


if __name__ == "__main__":
    main()
