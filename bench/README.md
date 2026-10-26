# bench/: latih ulang ColdTrack dan benchmark device

Skrip untuk melatih ulang model ColdTrack dan membandingkan waktunya antar device. Aturannya:

1. Tidak ada angka karangan: setiap angka laporan berasal dari JSON di `bench/results/`.
2. Perbandingan hanya antar device yang benar-benar dijalankan dengan skrip dan data yang sama.
3. Split test dipakai sekali per model, di akhir. Semua keputusan memakai split validasi.
4. Hasil yang tidak menguntungkan GPU tetap dilaporkan.

## Device tag

| Tag | Jalur | Arti |
|---|---|---|
| `g16-gpu` | CUDA | Hasil utama |
| `g16-cpu` | CPU (`CUDA_VISIBLE_DEVICES=""`) | Kontrol internal: efek GPU murni = `g16-cpu` vs `g16-gpu` |
| `d0-old` | CPU | Lenovo Yoga 6 (Ryzen 7 5700U). Variasi khusus GPU dicatat "tidak berlaku" |

Tag didefinisikan di `bench/devices/*.yaml`. Spesifikasi perangkat keras tidak ditulis
manual; `bench/core/env_capture.py` mencatatnya dari mesin. Yang diisi manual hanya bagian `kondisi`
(charger, mode daya, pendingin), diisi sebelum tiap sesi.

## Lingkungan

Keputusan: **WSL2 Ubuntu** untuk seluruh benchmark G16. Repo tetap di disk Windows dan dibaca
dari WSL lewat `/mnt/c/...`; venv di sistem berkas Linux. Pakai susunan yang sama di `d0-old`
agar biaya I/O setara. Bila `d0-old` terpaksa Windows native, tulis di `bench/devices/d0-old.yaml`.

### Sekali per laptop (PowerShell Administrator, lalu restart)

```
wsl --install -d Ubuntu-24.04
```

Batas memori WSL2 (bawaan ~setengah RAM). Buat `%UserProfile%\.wslconfig`:

```
[wsl2]
memory=12GB
```

lalu `wsl --shutdown`. Nilainya ikut tercatat otomatis di `env.json`.

### Di dalam WSL (dari root repo, mis. `cd /mnt/c/Users/<user>/pakar-coldtrack`)

```bash
bash bench/scripts/setup_wsl.sh cuda    # G16
bash bench/scripts/setup_wsl.sh cpu     # d0-old
```

Skrip memasang uv, Python 3.11, dan paket dengan versi dari `bench/requirements.lock.txt`
(dibangkitkan di G16 oleh `bench/scripts/freeze_lock.sh`), jadi `d0-old` memakai versi yang sama.

**Dua venv di G16 (temuan B0, 2026-10-10).** `onnxruntime-gpu` 1.31 dibangun untuk CUDA 13,
sedangkan PyTorch cu128 memakai CUDA 12. Memasang pustaka CUDA 13 di venv torch menimpa
`libcudnn.so.9` milik torch (cuDNN 9.19 -> 9.27) tanpa error. Karena itu:

| venv | Isi | Dipakai untuk |
|---|---|---|
| `~/.venvs/coldtrack` | torch cu128 + `onnxruntime` CPU (sama di semua device) | semua workload |
| `~/.venvs/coldtrack-ort` | `onnxruntime-gpu[cuda,cudnn]` (CUDA 13) | hanya jalur CUDA EP (smoke, W7) lewat `bench/core/ort_probe.py` |

Catatan paritas ONNX Runtime CUDA EP vs CPU EP (jendela val asli):
- GRU: TF32 bawaan CUDA EP membuat selisih forecast ~4e-3 C; dengan `use_tf32=0` ~1e-5.
  W7 mengukur keduanya dan menyebut mana yang dipakai.
- XGBoost TTB: ~35-39% jendela berbeda > 1e-3 (maks ~30-37 menit) dengan atau tanpa TF32, tetapi
  MAE agregat setara (23,67 vs 23,65 menit). Agregat float dihitung dengan urutan berbeda di GPU
  sehingga sebagian nilai melewati ambang split pohon. Kualitas dinilai lewat MAE, bukan selisih maks.

## Menjalankan

Dari PowerShell, `bench/scripts/wsl_run.sh` menjalankan perintah di venv WSL dari root repo:
`wsl -e bash bench/scripts/wsl_run.sh python -m bench.run --tag g16-gpu --workloads smoke`

```bash
python -m bench.run --list                         # daftar workload + status
python -m bench.core.env_capture --tag g16-gpu          # catat lingkungan saja
python -m bench.run --tag g16-gpu --workloads smoke
python -m bench.run --tag g16-cpu --workloads smoke
python -m bench.run --tag d0-old  --workloads smoke

# B2: benchmark W1 (latih GRU), W2 (XGBoost), W7 (inferensi ONNX); 1 pemanasan + 5 ulangan (seed 1000-1004)
python -m bench.run --tag g16-gpu --workloads W1,W2,W7
python -m bench.run --tag g16-cpu --workloads W1,W2,W7
python -m bench.run --tag d0-old  --workloads W1,W2,W7       # varian khusus GPU tercatat "tidak berlaku"
python -m bench.gates.g2_check --cpu-tag g16-cpu --gpu-tag g16-gpu  # gerbang G2 (paritas kualitas)
```

Konfigurasi yang sudah lengkap dilewati (bisa dilanjutkan setelah terputus); `--overwrite` mengulang,
`--configs b256_fp32,b1024_fp32` membatasi ke config tertentu. W7 memakai jeda 15 detik (run ~3-20 detik),
workload lain 60 detik.

`--quick` menjalankan versi kecil untuk menguji harness; hasilnya ke `bench/results/_quick/`
(tidak dikomit, bukan angka benchmark).

## Susunan folder

| Path | Isi |
|---|---|
| `run.py` | CLI benchmark: `python -m bench.run` |
| `core/` | Kerangka harness: `harness.py`, `common.py`, `env_capture.py`, `telemetry.py`, `train_lib.py`, `ort_bench.py`, `ort_probe.py`, `w8_cycle.py` |
| `workloads/` | Workload benchmark W1 sampai W8 dan `smoke`; `w8_ab_code.py` untuk uji A/B kode backend |
| `gates/` | Gerbang G1 (reproduksi) dan G2 (paritas kualitas CPU vs GPU) |
| `experiments/b1/` | B1: reproduksi baseline |
| `experiments/b3/` | B3: diagnosis, sweep Optuna, konfirmasi, ekspor kandidat, uji split test (G3) |
| `experiments/b7/` | B7: banding model, tes `/analyze` ujung ke ujung, fixture paritas ONNX |
| `experiments/b8/` | B8: label v5 (A1/A7 sementara) dan fitur konteks trip |
| `experiments/b9/` | B9: sinyal kompresor sintetis |
| `experiments/b10/` | B10: uji split test sekali untuk kandidat chip |
| `scripts/` | Skrip shell untuk WSL: `setup_wsl.sh`, `wsl_run.sh`, `freeze_lock.sh`, `chain_b2b3.sh`, `fe.sh` |
| `devices/` | Konfigurasi per device (`g16.yaml`, `d0-old.yaml`) |
| `report/` | Pembangun laporan (`REPORT.md`, grafik) |
| `results/` | Semua hasil run (JSON) |

Perintah modul memakai jalur lengkap, misalnya `python -m bench.experiments.b3.b3_sweep` dan
`python -m bench.gates.g1_check`. Berkas JSON di `bench/results/` dan `D0_OLD.md` mencatat nama skrip
seperti saat run dijalankan (mis. `bench/b3_sweep.py`); skrip itu sekarang ada di folder di atas.

## Susunan hasil

```
bench/results/<tag>/env.json                    lingkungan saat run
bench/results/<tag>/<workload>/run_<n>.json     satu berkas per run
bench/results/telemetry/                        CSV nvidia-smi (tidak dikomit)
```

## Hash commit di hasil run

Berkas JSON di `bench/results/` mencatat hash commit tempat run dijalankan. Riwayat repo ditulis ulang pada
2026-10-25 (baris `Co-Authored-By` dan nama author dibersihkan), sehingga hash lama tidak ada lagi di fork ini.
`bench/results/commit_map.txt` memetakan hash lama (kolom 1) ke hash baru (kolom 2); cari hash dari JSON di
kolom 1 untuk menemukan commit yang sama di riwayat sekarang. Isi berkas dan pohon kodenya tidak berubah.
