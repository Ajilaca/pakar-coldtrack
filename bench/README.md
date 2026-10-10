# bench/ — latih ulang ColdTrack + benchmark device

Jalur ML + benchmark untuk ASUS ROG Strix G16 (RTX 5070) vs device lama. Rencana lengkap:
`CONTEXT_MODEL_BENCHMARK_RTX5070.md` (handoff). Aturan yang tidak bisa ditawar:

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

Tag didefinisikan di `bench/devices/*.yaml`. Spesifikasi perangkat keras **tidak** ditulis
manual; `bench/env_capture.py` mencatatnya dari mesin. Yang diisi manual hanya bagian `kondisi`
(charger, mode daya, pendingin) — isi sebelum tiap sesi.

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
bash bench/setup_wsl.sh cuda    # G16
bash bench/setup_wsl.sh cpu     # d0-old
```

Skrip memasang uv, Python 3.11, dan paket dengan versi dari `bench/requirements.lock.txt`
(dibangkitkan di G16 oleh `bench/freeze_lock.sh`), jadi `d0-old` memakai versi yang sama.

**Dua venv di G16 (temuan B0, 2026-10-10).** `onnxruntime-gpu` 1.31 dibangun untuk CUDA 13,
sedangkan PyTorch cu128 memakai CUDA 12. Memasang pustaka CUDA 13 di venv torch menimpa
`libcudnn.so.9` milik torch (cuDNN 9.19 -> 9.27) tanpa error. Karena itu:

| venv | Isi | Dipakai untuk |
|---|---|---|
| `~/.venvs/coldtrack` | torch cu128 + `onnxruntime` CPU (sama di semua device) | semua workload |
| `~/.venvs/coldtrack-ort` | `onnxruntime-gpu[cuda,cudnn]` (CUDA 13) | hanya jalur CUDA EP (smoke, W7) lewat `bench/ort_probe.py` |

Catatan paritas ONNX Runtime CUDA EP vs CPU EP (jendela val asli):
- GRU: TF32 bawaan CUDA EP membuat selisih forecast ~4e-3 C; dengan `use_tf32=0` ~1e-5.
  W7 mengukur keduanya dan menyebut mana yang dipakai.
- XGBoost TTB: ~35-39% jendela berbeda > 1e-3 (maks ~30-37 menit) dengan atau tanpa TF32, tetapi
  MAE agregat setara (23,67 vs 23,65 menit). Agregat float dihitung dengan urutan berbeda di GPU
  sehingga sebagian nilai melewati ambang split pohon. Kualitas dinilai lewat MAE, bukan selisih maks.

## Menjalankan

Dari PowerShell, `bench/wsl_run.sh` menjalankan perintah di venv WSL dari root repo:
`wsl -e bash bench/wsl_run.sh python -m bench.run --tag g16-gpu --workloads smoke`

```bash
python -m bench.run --list                         # daftar workload + status
python -m bench.env_capture --tag g16-gpu          # catat lingkungan saja
python -m bench.run --tag g16-gpu --workloads smoke
python -m bench.run --tag g16-cpu --workloads smoke
python -m bench.run --tag d0-old  --workloads smoke
```

`--quick` menjalankan versi kecil untuk menguji harness; hasilnya ke `bench/results/_quick/`
(tidak dikomit, bukan angka benchmark).

## Susunan hasil

```
bench/results/<tag>/env.json                    lingkungan saat run
bench/results/<tag>/<workload>/run_<n>.json     satu berkas per run
bench/results/telemetry/                        CSV nvidia-smi (tidak dikomit)
```
