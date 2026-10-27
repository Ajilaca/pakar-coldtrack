"""Image flash QSPI untuk mode aliran (hw/rtl/model_flash.sv), dibuat dari hw/model/<folder>/{nodes,trees,base}.mem.

Image = deretan rekaman 9 byte (72 bit, big-endian), dibaca chip dari alamat 0 dalam satu sapuan:
  header   [71:56] 0x4354 "CT" | [55:48] versi 1 | [47:32] n_pohon | [31:16] n_simpul | [15:8] n_kelas
  base     n_kelas rekaman, [31:0] base_score s32 Q8.16
  pohon    per pohon: rekaman kepala [18:16] kelas | [15:0] jumlah simpul, lalu simpul pohon itu
           (format simpul sama dengan nodes.mem; alamat anak tetap global)
Syarat mode aliran, dicek di sini: simpul satu pohon berurutan, akar = simpul pertama, dan anak selalu sesudah
induknya di dalam pohon yang sama. SHA-256 seluruh image menjadi parameter HASH_MODEL di RTL.

  python -m hw.golden.flash_image           # tulis flash.bin + flash.sha256 untuk setiap folder hw/model/
"""

import hashlib
import itertools
from pathlib import Path

MAGIC, VERSI, REK = 0x4354, 1, 9
MODEL = Path(__file__).resolve().parents[1] / "model"


def _baca(folder, nama):
    return [int(x, 16) for x in (Path(folder) / nama).read_text().split()]


def image(folder):
    simpul, pohon, base = _baca(folder, "nodes.mem"), _baca(folder, "trees.mem"), _baca(folder, "base.mem")
    akar = [p & 0xFFFF for p in pohon] + [len(simpul)]
    assert akar[0] == 0 and all(a < b for a, b in itertools.pairwise(akar)), "pohon harus berurutan tanpa celah"
    rek = [MAGIC << 56 | VERSI << 48 | len(pohon) << 32 | len(simpul) << 16 | len(base) << 8]
    rek += [b & 0xFFFFFFFF for b in base]
    for t, p in enumerate(pohon):
        a, z = akar[t], akar[t + 1]
        rek.append((p >> 16) << 16 | (z - a))
        for i in range(a, z):
            v = simpul[i]
            if not v >> 71:
                ki = v & 0xFFFF
                assert i < ki and ki + 1 < z, f"simpul {i}: anak {ki} harus sesudah induk, di pohon {t}"
            rek.append(v)
    return b"".join(r.to_bytes(REK, "big") for r in rek)


def sha256(img):
    return hashlib.sha256(img).hexdigest()


def tulis_hex(img, path):
    """Satu byte per baris untuk $readmemh model flash di testbench."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("".join(f"{b:02x}\n" for b in img))


def ekspor(folder):
    img = image(folder)
    (Path(folder) / "flash.bin").write_bytes(img)
    (Path(folder) / "flash.sha256").write_text(sha256(img) + "\n")
    return img


if __name__ == "__main__":
    for f in sorted(p for p in MODEL.iterdir() if (p / "nodes.mem").exists()):
        img = ekspor(f)
        print(f"{f.name}: {len(img)} byte, sha256 {sha256(img)}")
