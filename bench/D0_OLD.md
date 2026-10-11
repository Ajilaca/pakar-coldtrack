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

## 6. Paket B5 (W3, W4, W6, W8), setelah langkah 1–5 selesai

Rencana B5 meminta paket yang sama dengan G16 (jalur CPU). Perkiraan: ±4–7 jam termasuk persiapan, atau
±2–3,5 jam tanpa W4. Kondisinya sama dengan bagian 0. Faktor kecepatan Yoga terhadap G16 belum terukur, jadi
angka ini perkiraan.

**a. Data Berkeley untuk W6.** Salin dari G16 `data/berkeley/data.txt.gz` (34 MB) dan
`data/berkeley/mote_locs.txt` ke folder yang sama di repo ini, lalu:

```bash
gunzip -k data/berkeley/data.txt.gz
```

**Jangan** salin `windows.parquet`: itu cache fitur, dan W6 ikut mengukur waktu membangun fitur.
Tanpa `data.txt`, W6 tercatat "tidak berlaku".

**b. Pindah ke commit yang sama dengan run B5 G16**, karena W8 mengukur backend versi armada:

```bash
git fetch && git checkout feat/fleet-online && git pull
```

```bash
bash bench/setup_wsl.sh cpu
```

Setup diulang karena backend di branch ini butuh paket tambahan (psycopg, paho-mqtt).
Hasil W1/W2/W7 dari branch lama tetap sah: kode workload itu tidak berubah.

**c. Cek cepat** (harus tanpa `GAGAL` / `Traceback`):

```bash
bash bench/wsl_run.sh python -m bench.run --tag d0-old --workloads W3,W4,W6,W8 --quick
```

**d. Run penuh** (semalaman):

```bash
bash bench/wsl_run.sh python -m bench.run --tag d0-old --workloads W3,W4,W6,W8 2>&1 | tee ~/d0old_b5.log
```

Bila waktunya tidak cukup, jalankan `--workloads W3,W6,W8` dulu. W4 akan ditandai "belum dijalankan"
di laporan, bukan dikosongkan diam-diam.

**e. Kirim hasil** seperti bagian 5. Folder `bench/results/d0-old/` bertambah W3, W4, W6, dan W8.
