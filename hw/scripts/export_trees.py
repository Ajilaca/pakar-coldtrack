"""Ekspor model XGBoost beku (bench/results/local-cpu/B10/) ke berkas memori hw/rtl/tree_engine.sv.

Ambang sudah dikonversi ke domain bilangan bulat fitur oleh hw/golden/trees.py. Hasil di hw/model/<folder>/:
  nodes.mem  satu simpul per baris, 72 bit hex:
                cabang: [71]=0 | [70:64] indeks fitur | [63:16] ambang s48 | [15:0] alamat anak kiri
                        (anak kanan = kiri + 1, diverifikasi)
                daun  : [71]=1 | [31:0] nilai s32 Q8.16
  trees.mem   satu pohon per baris: [18:16] kelas | [15:0] alamat akar
  base.mem    base_score per kelas, s32 Q8.16
  meta.json   jumlah simpul/pohon/kelas/fitur dan lebar
  flash.bin   image flash QSPI untuk mode flash (hw/golden/flash_image.py), flash.sha256 = HASH_MODEL

  python -m hw.scripts.export_trees
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hw.golden import flash_image
from hw.golden import trees as ph

FW, AW, SW = 48, 16, 32
# nama JSON beku di bench/results/local-cpu/B10/ -> (folder hw/model/, pakai siklus kerja)
MODEL = {"b8_xgb_chip_v5_context": ("xgb_v5_context", False),
         "b9_xgb_chip_v5_context_synthetic_duty": ("xgb_v5_context_duty", True)}


def hexs(v, bits):
    return f"{v & ((1 << bits) - 1):0{(bits + 3) // 4}x}"


def ekspor(nama, folder, duty):
    m = ph.muat_model(ROOT / f"bench/results/local-cpu/B10/{nama}.json", duty)
    simpul, pohon = [], []
    for p in m["pohon"]:
        dasar = len(simpul)
        pohon.append((p["kelas"], dasar))
        for s in p["simpul"]:
            if s[0] == "daun":
                assert -(1 << (SW - 1)) <= s[1] < (1 << (SW - 1))
                simpul.append((1 << 71) | (s[1] & ((1 << SW) - 1)))
            else:
                _, fi, thr, ki, ka = s
                assert ka == ki + 1, "anak kanan harus kiri + 1"
                assert -(1 << (FW - 1)) <= thr < (1 << (FW - 1)), f"ambang {thr} melebihi s{FW}"
                simpul.append((fi << 64) | ((thr & ((1 << FW) - 1)) << 16) | (dasar + ki))
    assert len(simpul) < (1 << AW)
    out = ROOT / "hw/model" / folder
    out.mkdir(parents=True, exist_ok=True)
    (out / "nodes.mem").write_text("".join(hexs(v, 72) + "\n" for v in simpul))
    (out / "trees.mem").write_text("".join(hexs((k << 16) | a, 19) + "\n" for k, a in pohon))
    (out / "base.mem").write_text("".join(hexs(b, SW) + "\n" for b in m["base"]))
    meta = {"simpul": len(simpul), "pohon": len(pohon), "kelas": m["n_kelas"],
            "fitur": len(ph.jenis_fitur(duty)), "lebar_fitur": FW, "lebar_alamat": AW, "lebar_skor": SW,
            "frak_daun": ph.FRAK_DAUN}
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    flash_image.ekspor(out)
    print(nama, meta)


if __name__ == "__main__":
    for n, (f, d) in MODEL.items():
        ekspor(n, f, d)
