"""Image flash bertag untuk versi ASIC model_flash (hw/asic/xgboost/rtl/model_flash.sv): model bisa diganti tanpa chip baru.

flash = image (hw/golden/flash_image.py) || tag, dengan tag = HMAC-SHA256(kunci, SHA256(image)), 32 byte.
Kunci 32 byte sama dengan KUNCI_MODEL yang ditanam saat layout (hw/asic/xgboost/layout/run_layout.sh membacanya dari berkas
yang sama). Menerbitkan model baru = membuat image bertag dengan kunci ini lalu menulisnya ke flash.

Kunci rahasia dan tidak bisa diganti setelah chip dibuat: hilang berarti tidak bisa menerbitkan model lagi, bocor
berarti siapa pun bisa menerbitkan model. Simpan di luar repo (bawaan ~/.coldtrack/kunci_model.hex) dan cadangkan.

  python -m hw.asic.xgboost.golden.flash_tag --buat-kunci                  # sekali, sebelum layout untuk tapeout
  python -m hw.asic.xgboost.golden.flash_tag hw/model/xgb_v5_context_duty  # tulis hw/asic/xgboost/build/flash/<folder>.bin
  python -m hw.asic.xgboost.golden.flash_tag --kunci k.hex --keluar flash.bin <folder>
"""

import argparse
import hashlib
import hmac
import os
import secrets
from pathlib import Path

from hw.golden import flash_image as fi

KUNCI_BAWAAN = Path.home() / ".coldtrack" / "kunci_model.hex"
BUILD = Path(__file__).resolve().parents[1] / "build" / "flash"


def tag(kunci, img):
    return hmac.new(kunci, hashlib.sha256(img).digest(), hashlib.sha256).digest()


def image_bertag(folder, kunci):
    img = fi.image(folder)
    return img + tag(kunci, img)


def baca_kunci(path=KUNCI_BAWAAN):
    teks = Path(path).read_text().strip()
    kunci = bytes.fromhex(teks)
    if len(kunci) != 32 or not any(kunci):
        raise ValueError(f"{path}: kunci harus 64 digit hex dan tidak nol")
    return kunci


def buat_kunci(path=KUNCI_BAWAAN):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"{path} sudah ada; kunci lama tidak ditimpa")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(secrets.token_hex(32) + "\n")
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", nargs="?", type=Path, help="folder model berisi nodes/trees/base.mem")
    ap.add_argument("--kunci", type=Path, default=KUNCI_BAWAAN)
    ap.add_argument("--keluar", type=Path)
    ap.add_argument("--buat-kunci", action="store_true", help="buat kunci acak baru di --kunci")
    a = ap.parse_args()
    if a.buat_kunci:
        print(f"kunci baru: {buat_kunci(a.kunci)} (rahasia, cadangkan)")
    if a.folder:
        isi = image_bertag(a.folder, baca_kunci(a.kunci))
        keluar = a.keluar or BUILD / f"{a.folder.resolve().name}.bin"
        keluar.parent.mkdir(parents=True, exist_ok=True)
        keluar.write_bytes(isi)
        print(f"{keluar}: {len(isi)} byte (image {len(isi) - 32} + tag 32), tag {isi[-32:].hex()}")
