# setup/: layout ASIC di laptop Windows (WSL2)

Panduan dari Windows kosong sampai siap menjalankan layout `coldtrack_spi` (RTL ke GDS) dengan LibreLane. Ditulis
untuk ASUS ROG Strix G16 (16 GB RAM), tapi berlaku untuk laptop Windows lain dengan WSL2. Hanya layout: tidak ada
simulasi RTL atau estimasi luas terpisah di sini. LibreLane mode Docker sudah membawa Yosys, OpenROAD, Magic,
KLayout, dan PDK sky130, jadi tidak ada tool EDA lain yang dipasang.

| Langkah | Berkas | Lama kira-kira |
|---|---|---|
| 1. WSL2, `.wslconfig`, Docker Desktop | `windows/install_wsl.ps1`, `windows/wslconfig.example` | 20 menit + restart |
| 2. Clone repo di dalam WSL | perintah di bawah | 2 menit |
| 3. Paket sistem Ubuntu | `wsl/01_system_packages.sh` | 3 menit |
| 4. LibreLane + smoke test | `wsl/02_librelane.sh` | 15 sampai 30 menit (unduh image Docker dan PDK) |
| 5. Layout | `librelane/config.json`, `librelane/run_layout.sh` | belum pernah dijalankan |

Kebutuhan: Windows 10 versi 2004 (build 19041) atau Windows 11, RAM 16 GB (minimal 8 GB), ruang disk kosong
sekitar 20 GB.

## 1. Windows: WSL2 dan Docker Desktop

PowerShell **sebagai Administrator**:

```powershell
wsl --install -d Ubuntu-24.04
```

Atau `powershell -ExecutionPolicy Bypass -File setup\windows\install_wsl.ps1` bila repo sudah ada di Windows
(sekaligus membuat `.wslconfig`). Batas memori WSL, di `%UserProfile%\.wslconfig`:

```
[wsl2]
memory=12GB
swap=8GB
```

Restart Windows, buka **Ubuntu 24.04** dari Start menu, buat user Linux, lalu cek dari PowerShell:

```powershell
wsl --list --verbose          # Ubuntu-24.04 harus VERSION 2
```

Pasang **Docker Desktop for Windows**: centang *Use WSL 2 instead of Hyper-V*, aktifkan *Start Docker Desktop when
you log in*, dan di Resources > WSL Integration aktifkan Ubuntu-24.04. LibreLane hanya mendukung Docker lewat
WSL2; VirtualBox mengganggu jalannya.

## 2. Clone repo di dalam WSL

Simpan repo di sistem berkas Linux (`~`), bukan di `/mnt/c/...`. Akses disk Windows dari WSL jauh lebih lambat.

```bash
mkdir -p ~/FPGA/Projects/Coldtrack && cd ~/FPGA/Projects/Coldtrack
git clone https://github.com/Ajilaca/pakar-coldtrack.git
cd pakar-coldtrack
git switch setup
```

## 3 dan 4. Paket sistem dan LibreLane

Dari root repo, satu per satu (Docker Desktop harus sudah menyala):

```bash
bash setup/wsl/01_system_packages.sh
bash setup/wsl/02_librelane.sh
```

Versi: LibreLane 3.0.17 (PyPI). Smoke test selesai tanpa galat berarti LibreLane siap.

## 5. Layout

`librelane/config.json` adalah titik awal untuk `coldtrack_spi`: mode flash, clock 20 ns (50 MHz), utilisasi core
40 %, `HASH_MODEL` dari `hw/model/xgb_v5_context_duty/flash.sha256`. **Belum pernah dijalankan.** Sebelum layout:

1. putuskan ring buffer `features`: flip-flop (bawaan), makro SRAM `sky130_sram_1kbyte_1rw1r_32x256_8` x4, atau PSRAM;
2. pilih shuttle dan batas luasnya;
3. tambahkan pad I/O dan penempatan pin sesuai shuttle.

```bash
bash setup/librelane/run_layout.sh
```

Hasil di `runs/RUN_<waktu>/`, tiap langkah punya subfolder dan hasil akhir ada di `final/`. Lihat layout:

```bash
.venv/bin/python -m librelane --dockerized --last-run --flow openinklayout setup/librelane/config.json
```

`run_layout.sh` menolak jalan bila `HASH_MODEL` di config berbeda dari `flash.sha256`. Kalau Yosys bawaan gagal
membaca SystemVerilog, tambahkan `"USE_SLANG": true` di config. Pengali lebar di `physics` dan `features` membuat
sintesis lama (satu core per modul); di laptop 8 GB satu modul sudah lebih dari 18 menit.

## Masalah umum

| Gejala | Penyebab dan solusi |
|---|---|
| Docker tidak terjangkau dari WSL, atau `permission denied` | Docker Desktop belum menyala, atau WSL Integration untuk Ubuntu-24.04 belum aktif |
| Proses mati tiba-tiba saat layout | Memori WSL habis: naikkan `memory` di `.wslconfig`, lalu `wsl --shutdown` dari PowerShell |
| Semua langkah sangat lambat | Repo ada di `/mnt/c/...`; clone ulang di `~` |
