"""CLI tunggal benchmark ColdTrack -- sama persis di semua device.

  python -m bench.run --list
  python -m bench.run --tag g16-gpu --workloads smoke
  python -m bench.run --tag d0-old  --workloads W1,W2,W7

Tag dan jalurnya (cuda/cpu) didefinisikan di bench/devices/*.yaml. Tag jalur cpu memaksa
CUDA_VISIBLE_DEVICES="" SEBELUM torch di-import. Tag jalur cuda yang tidak menemukan GPU
langsung gagal -- tidak pernah jatuh ke CPU diam-diam.
"""

import argparse
import os
import sys
import traceback
from types import SimpleNamespace

import yaml

from bench.common import DEVICES_DIR, RESULTS_DIR, ROOT, SEEDS, rel, stamp, write_json


def load_profiles():
    profiles = {}
    for p in sorted(DEVICES_DIR.glob("*.yaml")):
        with open(p, encoding="utf-8") as f:
            prof = yaml.safe_load(f)
        for tag, spec in (prof.get("tags") or {}).items():
            profiles[tag] = (prof, spec["device"])
    return profiles


def resolve_tag(tag):
    profiles = load_profiles()
    if tag not in profiles:
        sys.exit(f"Tag '{tag}' tidak dikenal. Tag tersedia: {', '.join(profiles)}")
    return profiles[tag]


def apply_device_env(kind):
    if kind == "cpu":
        if "torch" in sys.modules:
            raise RuntimeError("torch sudah di-import sebelum CUDA_VISIBLE_DEVICES diset")
        os.environ["CUDA_VISIBLE_DEVICES"] = ""


def check_cuda_or_die(kind):
    if kind != "cuda":
        return
    import torch

    if not torch.cuda.is_available():
        sys.exit("Tag jalur cuda tetapi torch.cuda.is_available() = False. Periksa instalasi PyTorch cu128.")


def kondisi_kosong(profile):
    return [k for k, v in (profile.get("kondisi") or {}).items() if v is None and k != "catatan"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Benchmark ColdTrack")
    ap.add_argument("--tag", help="device tag, mis. g16-gpu / g16-cpu / d0-old")
    ap.add_argument("--workloads", default="smoke", help="daftar dipisah koma, mis. W1,W2,W7")
    ap.add_argument("--repeats", type=int, default=5, help="ulangan terukur per konfigurasi (protokol: >= 5)")
    ap.add_argument("--warmup", type=int, default=1, help="run pemanasan yang dibuang")
    ap.add_argument("--cooldown", type=int, default=60, help="jeda pendinginan antar run (detik)")
    ap.add_argument("--quick", action="store_true",
                    help="mode uji harness: ukuran kecil, hasil ditulis ke results/_quick (bukan benchmark)")
    ap.add_argument("--configs", default="", help="batasi ke config_id tertentu, dipisah koma")
    ap.add_argument("--overwrite", action="store_true", help="ulangi config yang sudah lengkap")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args(argv)

    from bench.workloads import REGISTRY

    if a.list:
        for w in REGISTRY.values():
            status = "siap" if w.modul else f"belum ({w.tahap})"
            print(f"{w.id:6s} {status:12s} {w.judul}")
        return 0
    if not a.tag:
        ap.error("--tag wajib (kecuali --list)")

    ids = [s.strip() for s in a.workloads.split(",") if s.strip()]
    unknown = [i for i in ids if i not in REGISTRY]
    if unknown:
        ap.error(f"workload tidak dikenal: {unknown}. Lihat --list")

    os.chdir(ROOT)                  # skrip ml/ memakai path relatif terhadap root repo
    if a.quick:                     # uji harness: 1 pemanasan + 1 ulangan, tanpa jeda
        a.repeats, a.warmup, a.cooldown = 1, 1, 0
    profile, kind = resolve_tag(a.tag)
    apply_device_env(kind)          # harus sebelum import torch di bawah
    check_cuda_or_die(kind)

    kosong = kondisi_kosong(profile)
    if kosong and not a.quick:
        print(f"PERINGATAN: kondisi device belum diisi di bench/devices/{profile['device']}.yaml: {kosong}")

    from bench.env_capture import capture

    out_root = RESULTS_DIR / ("_quick" if a.quick else "") / a.tag
    # satu env per pemanggilan (tidak menimpa env run sebelumnya, yang dirujuk hasil lama)
    env_path = write_json(out_root / "env" / f"env_{stamp()}.json", capture(a.tag, profile))

    ctx = SimpleNamespace(
        tag=a.tag, device=kind, profile=profile, out_root=out_root, env_path=rel(env_path),
        repeats=a.repeats, warmup=a.warmup, cooldown=a.cooldown, quick=a.quick, seeds=SEEDS,
        configs=[c for c in a.configs.split(",") if c], overwrite=a.overwrite or a.quick,
    )

    gagal = 0
    for wid in ids:
        w = REGISTRY[wid]
        print(f"\n=== {wid}: {w.judul} [{a.tag}] ===", flush=True)
        try:
            files = w.load().run(ctx)
            for f in files or []:
                print(f"  tersimpan: {rel(f)}")
        except NotImplementedError as e:
            print(f"  dilewati: {e}")
        except Exception:  # noqa: BLE001 -- satu workload gagal tidak boleh menghentikan sisanya
            gagal += 1
            traceback.print_exc()
            print(f"  GAGAL: {wid}")
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
