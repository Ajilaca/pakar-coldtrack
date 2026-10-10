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

### Di dalam WSL

```bash
sudo apt-get update && sudo apt-get install -y git
curl -LsSf https://astral.sh/uv/install.sh | sh && source ~/.local/bin/env
uv venv --python 3.11 ~/.venvs/coldtrack && source ~/.venvs/coldtrack/bin/activate
cd /mnt/c/Users/<user>/pakar-coldtrack

# G16 (CUDA, Blackwell butuh CUDA 12.8+):
uv pip install torch --index-url https://download.pytorch.org/whl/cu128
uv pip install -r bench/requirements.txt onnxruntime-gpu

# d0-old (CPU saja):
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -r bench/requirements.txt onnxruntime
```

Versi persis yang dipakai di G16 ada di `bench/requirements.lock.txt`; samakan di `d0-old`.

## Menjalankan

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
