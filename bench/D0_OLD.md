# Menjalankan benchmark di device lama (`d0-old`, Lenovo Yoga 6)

Panduan untuk user. Claude Code **tidak** mengisi hasil `d0-old`; semua angka harus berasal dari
run di laptop ini dengan skrip dan commit yang sama dengan G16.

## 0. Kondisi (wajib sama sepanjang benchmark)

- Charger **terpasang** selama seluruh run.
- Mode daya performa tertinggi (Lenovo Vantage / Windows "Best performance"), dan **jangan diubah**.
- Laptop di permukaan keras, aplikasi berat ditutup, laptop tidak dipakai selama run.
- Isi bagian `kondisi` dan `lingkungan` di `bench/devices/d0-old.yaml` sesuai kondisi nyata.

## 1. Lingkungan (sekali)

Disarankan **WSL2 Ubuntu 24.04**, sama dengan G16 (PowerShell Administrator, lalu restart):

```
wsl --install -d Ubuntu-24.04
```

Buat `%UserProfile%\.wslconfig` berisi dua baris berikut, lalu jalankan `wsl --shutdown`:

```
[wsl2]
memory=12GB
```

Bila terpaksa memakai Windows native, tulis `lingkungan: Windows native` di `d0-old.yaml`. Batas
memorinya berbeda, dan itu akan disebut di laporan.

## 2. Ambil repo pada branch yang sama (di Ubuntu)

```bash
sudo apt-get update && sudo apt-get install -y git
cd /mnt/c/Users/<user_windows>
git clone https://github.com/tsabitakhoir/pakar-coldtrack.git
cd pakar-coldtrack
git checkout feat/model-retrain-g16
bash bench/setup_wsl.sh cpu       # versi paket dikunci dari bench/requirements.lock.txt
```

## 3. Cek cepat (beberapa menit)

```bash
bash bench/wsl_run.sh python -m bench.run --tag d0-old --workloads smoke
bash bench/wsl_run.sh python -m bench.run --tag d0-old --workloads W1,W2,W7 --quick
```

Keduanya harus selesai tanpa `GAGAL` / `Traceback`. Hasil `--quick` tidak dipakai di laporan.

## 4. Run penuh (lama, bisa semalaman)

```bash
bash bench/wsl_run.sh python -m bench.run --tag d0-old --workloads W1,W2,W7 2>&1 | tee ~/d0old_b2.log
```

Bila terputus, jalankan perintah yang sama lagi: konfigurasi yang sudah lengkap dilewati.
Varian khusus GPU (AMP, CUDA EP, XGBoost cuda) otomatis tercatat "tidak berlaku".

## 5. Kirim hasil

Pilih salah satu:

- **Lewat git** (perlu login GitHub di laptop ini):
  ```bash
  git add bench/results/d0-old
  git commit -m "test(model): hasil benchmark d0-old (W1, W2, W7)"
  git push
  ```
- **Tanpa git**: kompres folder `bench/results/d0-old/`, lalu salin ke folder yang sama di repo G16.

Telemetri tidak dihasilkan di `d0-old` karena tidak ada GPU NVIDIA; itu wajar.
