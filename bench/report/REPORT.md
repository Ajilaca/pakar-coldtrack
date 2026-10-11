# Laporan latih ulang ColdTrack + benchmark device

> Dibangkitkan oleh `bench/report/build_report.py` pada 2026-10-11T22:47:19+00:00. Jangan diedit manual:
> setiap angka berasal dari JSON di `bench/results/`. Tabel lengkap: `summary.csv`.

## Ringkasan

Pertanyaan: seberapa besar laptop baru (ASUS ROG Strix G16, RTX 5070 Laptop) mempercepat pekerjaan ColdTrack dibanding laptop lama (Lenovo Yoga 6, CPU saja), dan di mana GPU tidak membantu. `g16-cpu` = G16 dengan GPU dimatikan, sehingga efek GPU murni dan efek mesin baru dapat dipisah.

| pekerjaan | perbandingan | speedup (median) | CI 95 % | kesimpulan | n run |
|---|---|---|---|---|---|
| Latih GRU 30 epoch (konfigurasi asli, data di GPU) (W1) | g16-cpu → g16-gpu | 26.02× | [24.82, 26.98] | lebih cepat | 5 |
| Sweep GRU 8 trial × 5 epoch (W3) | g16-cpu → g16-gpu | 25.98× | - (1 run) | lebih cepat (1 run, tanpa CI) | 1 |
| Ablation GRU 5 seed × 2 varian × 10 epoch (W4) | g16-cpu → g16-gpu | 23.61× | - (1 run) | lebih cepat (1 run, tanpa CI) | 1 |
| Latih XGBoost TTB (W2) | g16-cpu → g16-gpu | 0.42× | [0.38, 0.44] | lebih LAMBAT | 5 |
| Sweep XGBoost 20 trial (W3) | g16-cpu → g16-gpu | 1.10× | - (1 run) | selisih kecil, 1 run (tidak dapat disimpulkan) | 1 |
| Sensor-health Berkeley (fitur + latih) (W6) | g16-cpu → g16-gpu | 1.05× | [0.96, 1.16] | tidak berbeda nyata | 5 |
| Inferensi GRU ONNX, batch 1 (W7) | g16-cpu → g16-gpu | 0.04× | [0.04, 0.06] | lebih LAMBAT; ⚠ sebaran run besar: g16-cpu 36% | 5 |
| Inferensi GRU ONNX, batch 1024 (W7) | g16-cpu → g16-gpu | 22.18× | [21.83, 22.38] | lebih cepat | 5 |
| Latih GRU 30 epoch: laptop lama → G16 tanpa GPU (W1) | d0-old → g16-cpu | 1.60× | [1.57, 1.66] | lebih cepat | 5 |
| Latih GRU 30 epoch (DataLoader): laptop lama → G16 tanpa GPU (W1) | d0-old → g16-cpu | 2.62× | [1.75, 2.95] | lebih cepat; ⚠ sebaran run besar: d0-old 43% | 5 |
| Latih XGBoost: laptop lama → G16 CPU (W2) | d0-old → g16-cpu | 2.26× | [2.19, 2.52] | lebih cepat | 5 |
| Inferensi GRU batch 1: laptop lama → G16 CPU (W7) | d0-old → g16-cpu | 3.09× | [2.44, 3.42] | lebih cepat; ⚠ sebaran run besar: g16-cpu 36% | 5 |
| Latih GRU 30 epoch: laptop lama → G16 GPU (W1) | d0-old → g16-gpu | 41.69× | [39.65, 43.30] | lebih cepat | 5 |
| Sweep GRU: laptop lama → G16 CPU (W3) | d0-old → g16-cpu | 2.01× | - (1 run) | lebih cepat (1 run, tanpa CI) | 1 |
| Ablation GRU: laptop lama → G16 CPU (W4) | d0-old → g16-cpu | 1.89× | - (1 run) | lebih cepat (1 run, tanpa CI) | 1 |
| Ablation GRU: laptop lama → G16 GPU (W4) | d0-old → g16-gpu | 44.65× | - (1 run) | lebih cepat (1 run, tanpa CI) | 1 |
| Siklus inferensi 100 truk: laptop lama → G16 CPU (kode berbeda, lihat B5) (W8) | d0-old → g16-cpu | 2.44× | [2.28, 2.54] | lebih cepat | 5 |

Cara membaca: speedup = waktu median pembanding / waktu median yang dibandingkan; > 1 berarti yang dibandingkan lebih cepat. Kualitas model antar-device dicek terpisah (G2 dan tabel B5). ⚠ = rentang (maks − min) / median antar-run > 25%, mis. akibat throttling termal; angka median baris itu kurang andal.

## Device dan kondisi

| tag | CPU | inti fisik/logis | RAM WSL (GB) | GPU | lingkungan | mode daya | env capture |
|---|---|---|---|---|---|---|---|
| g16-gpu | AMD Ryzen 9 8940HX with Radeon Graphics | 16/32 | 11.68 | NVIDIA GeForce RTX 5070 Laptop GPU | WSL2 Ubuntu | Turbo | `bench/results/g16-gpu/env/env_20261011-170742.json` |
| g16-cpu | AMD Ryzen 9 8940HX with Radeon Graphics | 16/32 | 11.68 | dimatikan (CUDA_VISIBLE_DEVICES="") | WSL2 Ubuntu | Turbo | `bench/results/g16-cpu/env/env_20261011-184051.json` |
| d0-old | AMD Ryzen 7 5700U with Radeon Graphics | 8/16 | 11.68 | - | WSL2 Ubuntu 24.04 | Lenovo Extreme Performance (Fn+Q) + Windows "Best performance" | `bench/results/d0-old/env/env_20261011-212135.json` |

### Provenance (commit tiap run)

| tag | commit | dirty | n run | ada di repo |
|---|---|---|---|---|
| g16-gpu | `009ed57` | False | 150 | ya |
| g16-gpu | `5d13490` | False | 9 | ya |
| g16-gpu | `5b64886` | False | 6 | ya |
| g16-cpu | `009ed57` | False | 78 | ya |
| g16-cpu | `5d13490` | False | 33 | ya |
| g16-cpu | `5b64886` | False | 6 | ya |
| d0-old | `fcd0fb0` | False | 78 | ya |
| d0-old | `fd61a98` | False | 33 | ya |
| d0-old | `9d97fe9` | False | 6 | ya |

Catatan kondisi d0-old: Run pertama (mode Lenovo otomatis/Intelligent Cooling) dibatalkan: suhu CPU mencapai ~100 C lalu di-clamp ke ~22% performa (~400 MHz) selama 4-8 menit, berulang tiap ~10 menit. Hasilnya tidak dipakai. Claude Code desktop tetap berjalan sebagai pengendali run (beban CPU ~1-2%), ditambah perekam suhu/performa Windows tiap ~12 detik.

## Metodologi singkat

- Satu laptop baru, dua jalur: `g16-gpu` (CUDA) dan `g16-cpu` (GPU disembunyikan). Laptop lama `d0-old` jalur CPU. Semua di WSL2 Ubuntu 24.04, paket dikunci (`bench/requirements.lock.txt`), charger terpasang, mode daya performa tertinggi, aplikasi berat ditutup.
- W1/W2/W6/W7/W8: 1 pemanasan dibuang + 5 ulangan (seed 1000–1004), median [min–maks], speedup dengan CI 95 % bootstrap. W3/W4: satu run terukur yang berisi banyak pelatihan; sebaran antar-trial/seed ada di JSON, tetapi speedup-nya tanpa CI.
- Varian yang tidak bermakna di device itu (AMP, CUDA EP, XGBoost cuda di CPU; W8 di tag GPU) dicatat `tidak berlaku`, bukan dikosongkan. W5 (skala data simulator) tidak dijalankan: simulator v4 tidak dapat direproduksi dari repo.
- Kualitas dicek agar kecepatan tidak dibeli dengan model yang lebih buruk (G2 untuk B2; tabel kualitas B5).
- Split test dipakai sekali per model (`bench/results/test/test_access_log.json`); seluruh keputusan memakai val.

## Gerbang G1 (reproduksi)

**Status: lulus dengan catatan** (diputuskan 2026-10-10, user (Tsabita Khoirunnisa), lewat chat Claude Code).
Aturan ketat: acuan val berada dalam mean +/- 2 SD dari lima seed.

### g16-cpu — 6/11 metrik lulus aturan ketat

| model | metrik | mean ± SD (5 seed) | rentang ±2 SD | acuan val | aturan ketat |
|---|---|---|---|---|---|
| gru | forecast_t15_mae_c | 0.1580 ± 0.0021 | [0.1538, 0.1623] | 0.1595 | lulus |
| gru | forecast_t30_mae_c | 0.2085 ± 0.0029 | [0.2028, 0.2143] | 0.2110 | lulus |
| gru | forecast_t60_mae_c | 0.2556 ± 0.0031 | [0.2494, 0.2618] | 0.2554 | lulus |
| gru | macro_f1 | 0.5895 ± 0.0094 | [0.5707, 0.6083] | 0.5800 | lulus |
| gru | akurasi | 0.7990 ± 0.0068 | [0.7855, 0.8126] | 0.7857 | lulus |
| gru | ttb_mae_menit | 22.3346 ± 0.5131 | [21.3085, 23.3608] | 21.2361 | tidak |
| gru | anomali_pr_auc | 0.6924 ± 0.0067 | [0.6790, 0.7059] | 0.6874 | lulus |
| xgb_ttb | ttb_mae_semua_menit | 24.0148 ± 0.0000 | [24.0148, 24.0148] | 25.2174 | tidak |
| xgb_ttb | ttb_mae_le30_menit | 5.1418 ± 0.0000 | [5.1418, 5.1418] | - | tanpa acuan |
| xgb_ttb | ttb_mae_le10_menit | 3.2388 ± 0.0000 | [3.2388, 3.2388] | - | tanpa acuan |
| xgb_clf | macro_f1 | 0.6900 ± 0.0000 | [0.6900, 0.6900] | 0.6916 | tidak |
| xgb_clf | akurasi | 0.8588 ± 0.0000 | [0.8588, 0.8588] | 0.8601 | tidak |
| xgb_clf | anomali_pr_auc | 0.7580 ± 0.0000 | [0.7580, 0.7580] | 0.7546 | tidak |

Sumber: `bench/results/g16-cpu/B1/G1.json`

### g16-gpu — 6/11 metrik lulus aturan ketat

| model | metrik | mean ± SD (5 seed) | rentang ±2 SD | acuan val | aturan ketat |
|---|---|---|---|---|---|
| gru | forecast_t15_mae_c | 0.1593 ± 0.0020 | [0.1553, 0.1633] | 0.1595 | lulus |
| gru | forecast_t30_mae_c | 0.2095 ± 0.0033 | [0.2030, 0.2161] | 0.2110 | lulus |
| gru | forecast_t60_mae_c | 0.2581 ± 0.0064 | [0.2452, 0.2710] | 0.2554 | lulus |
| gru | macro_f1 | 0.5863 ± 0.0049 | [0.5765, 0.5960] | 0.5800 | lulus |
| gru | akurasi | 0.7965 ± 0.0014 | [0.7937, 0.7993] | 0.7857 | tidak |
| gru | ttb_mae_menit | 21.9331 ± 0.5888 | [20.7555, 23.1106] | 21.2361 | lulus |
| gru | anomali_pr_auc | 0.6884 ± 0.0040 | [0.6804, 0.6964] | 0.6874 | lulus |
| xgb_ttb | ttb_mae_semua_menit | 24.0148 ± 0.0000 | [24.0148, 24.0148] | 25.2174 | tidak |
| xgb_ttb | ttb_mae_le30_menit | 5.1418 ± 0.0000 | [5.1418, 5.1418] | - | tanpa acuan |
| xgb_ttb | ttb_mae_le10_menit | 3.2388 ± 0.0000 | [3.2388, 3.2388] | - | tanpa acuan |
| xgb_clf | macro_f1 | 0.6865 ± 0.0000 | [0.6865, 0.6865] | 0.6916 | tidak |
| xgb_clf | akurasi | 0.8580 ± 0.0000 | [0.8580, 0.8580] | 0.8601 | tidak |
| xgb_clf | anomali_pr_auc | 0.7566 ± 0.0000 | [0.7566, 0.7566] | 0.7546 | tidak |

Sumber: `bench/results/g16-gpu/B1/G1.json`

### Alasan "lulus dengan catatan"

- **gru** — GRU tereproduksi: 6 dari 7 metrik lulus per tag, meleset tipis pada metrik yang berbeda di tiap device. Acuan (ml/reports/metrics.json: metrik_val_pembanding) adalah satu run tunggal dari ml/finetune.py yang tidak menyetel seed, sehingga acuan itu sendiri satu sampel acak. Dengan 14 perbandingan (7 metrik x 2 device), 1-2 metrik di luar +/- 2 SD adalah wajar secara kebetulan. Tidak ada metrik yang gagal di kedua device. (sumber: `bench/results/g16-cpu/B1/G1.json`, `bench/results/g16-gpu/B1/G1.json`)
- **xgb_ttb, xgb_clf** — Aturan +/- 2 SD tidak bermakna untuk XGBoost: deterministik (SD 0), dan acuannya basi. XGB_PARAMS tanpa subsample/colsample sehingga seed tidak berpengaruh dan kelima seed identik; aturan +/- 2 SD berubah menjadi 'harus identik'. Acuan ml/reports/baseline_metrics.json terakhir diubah 2026-08-06, sebelum commit 55a30fe (2026-08-13) yang mengubah cara jendela menghitung reefer_duration_min. Builder lama + data v4 mendekati acuan klasifikasi; sisa selisih TTB tidak terjelaskan oleh versi XGBoost 2.1.4-3.2.0 dan versi asli tidak tercatat. (sumber: `bench/results/g16-cpu/B1/G1_investigasi.json`)

Investigasi acuan XGBoost (XGBoost 3.2.0, split val):

| kombinasi | ttb_mae_menit | macro_f1 | akurasi | anomali_pr_auc |
|---|---|---|---|---|
| **acuan baseline_metrics.json** | 25.2174 | 0.6916 | 0.8601 | 0.7546 |
| builder_lama_350cb41+v3 | 24.5883 | 0.4937 | 0.6940 | 0.6785 |
| builder_lama_350cb41+v4 | 24.5883 | 0.6856 | 0.8591 | 0.7564 |
| builder_sekarang+v3 | 24.0209 | 0.4939 | 0.6925 | 0.6797 |
| builder_sekarang+v4 | 24.0209 | 0.6900 | 0.8588 | 0.7580 |

Sumber: `bench/results/g16-cpu/B1/G1_investigasi.json`

**Baseline baru:** Nilai B1 dari pipeline sekarang menjadi baseline pembanding untuk B3 dan G3 (split val). Sumber: `bench/results/g16-cpu/B1/`, `bench/results/g16-gpu/B1/`.

Catatan terbuka: Selisih XGBoost CPU vs GPU pada seed yang sama (classifier) diperiksa di gerbang G2.

## B2: benchmark W1 / W2 / W7

Protokol: 1 pemanasan dibuang + 5 ulangan (seed 1000–1004), median [min–maks]. Kondisi per run tercatat di JSON (`kondisi_manual`, `env`, `telemetri`). `belum diukur` = device belum menjalankan; `tidak berlaku` = varian tidak bermakna di device itu.

### W1: latih GRU (30 epoch, split val)

| config | g16-gpu detik latih | g16-cpu detik latih | d0-old detik latih | F1 val (mean, GPU) | time-to-target GPU |
|---|---|---|---|---|---|
| b1024_bf16 | 45.9 [40.5–54.6] | tidak berlaku | tidak berlaku | 0.4759 | tidak tercapai (0/5) |
| b1024_fp16 | 46.8 [46.2–48.1] | tidak berlaku | tidak berlaku | 0.4780 | tidak tercapai (0/5) |
| b1024_fp32 | 38.8 [38.6–39.2] | 809 [807–832] | 1.46e+03 [1.45e+03–1.5e+03] | 0.4751 | tidak tercapai (0/5) |
| b1024_fp32_pin | 42.4 [42–44] | tidak berlaku | tidak berlaku | 0.4751 | tidak tercapai (0/5) |
| b1024_fp32_resident | 17.7 [17.5–18] | 706 [690–726] | 1.25e+03 [1.21e+03–1.39e+03] | 0.4742 | tidak tercapai (0/5) |
| b1024_fp32_w2pin | 35.5 [34.9–37.1] | tidak berlaku | tidak berlaku | 0.4751 | tidak tercapai (0/5) |
| b256_bf16 | 70.1 [63.5–73.9] | tidak berlaku | tidak berlaku | 0.5927 | 37 s (4/5) |
| b256_fp16 | 70.1 [67.1–78.1] | tidak berlaku | tidak berlaku | 0.5871 | 37 s (4/5) |
| b256_fp32 | 60.5 [57.1–61.7] | 928 [882–1.05e+03] | 2.43e+03 [1.62e+03–2.68e+03] | 0.5863 | 29 s (5/5) |
| b256_fp32_resident | 35.1 [34.3–36.8] | 913 [905–928] | 1.46e+03 [1.45e+03–1.51e+03] | 0.5839 | 20 s (5/5) |
| b4096_bf16 | 47.9 [47.3–51] | tidak berlaku | tidak berlaku | 0.4715 | tidak tercapai (0/5) |
| b4096_fp16 | 54.8 [53.2–57.4] | tidak berlaku | tidak berlaku | 0.4723 | tidak tercapai (0/5) |
| b4096_fp32 | 46.8 [46–48] | 902 [883–909] | 1.25e+03 [1.19e+03–1.36e+03] | 0.4710 | tidak tercapai (0/5) |

Sumber: `bench/results/<tag>/W1/<config>/run_*.json`

### Speedup (median pembanding / median yang dibandingkan, CI 95 % bootstrap)

| workload | config | perbandingan | arti | speedup | CI 95 % | G2 |
|---|---|---|---|---|---|---|
| W1 | b1024_fp32 -> b1024_bf16 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 17.65× | [14.83, 19.98] | setara |
| W1 | b1024_fp32 -> b1024_bf16 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 31.84× | [26.76, 36.05] | setara |
| W1 | b1024_fp32 -> b1024_fp16 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 17.29× | [16.81, 17.92] | setara |
| W1 | b1024_fp32 -> b1024_fp16 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 31.20× | [30.35, 32.13] | setara |
| W1 | b1024_fp32 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 20.84× | [20.65, 21.49] | setara |
| W1 | b1024_fp32 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 1.80× | [1.75, 1.86] | - |
| W1 | b1024_fp32 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 37.59× | [37.25, 38.72] | setara |
| W1 | b1024_fp32 -> b1024_fp32_pin | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 19.09× | [18.33, 19.74] | setara |
| W1 | b1024_fp32 -> b1024_fp32_pin | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 34.45× | [33.15, 35.48] | setara |
| W1 | b1024_fp32_resident | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 39.96× | [39.01, 41.10] | setara |
| W1 | b1024_fp32_resident | d0-old → g16-cpu | efek mesin baru tanpa GPU | 1.78× | [1.71, 1.97] | - |
| W1 | b1024_fp32_resident | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 70.98× | [68.17, 78.90] | setara |
| W1 | b1024_fp32 -> b1024_fp32_w2pin | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 22.83× | [21.79, 23.59] | setara |
| W1 | b1024_fp32 -> b1024_fp32_w2pin | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 41.19× | [39.31, 42.42] | setara |
| W1 | b256_fp32 -> b256_bf16 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 13.23× | [12.31, 14.97] | setara |
| W1 | b256_fp32 -> b256_bf16 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 34.60× | [23.14, 41.49] | setara |
| W1 | b256_fp32 -> b256_fp16 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 13.24× | [11.61, 14.98] | setara |
| W1 | b256_fp32 -> b256_fp16 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 34.63× | [23.16, 38.61] | setara |
| W1 | b256_fp32 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 15.35× | [14.58, 17.36] | setara |
| W1 | b256_fp32 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 2.62× | [1.75, 2.95] | - |
| W1 | b256_fp32 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 40.13× | [26.84, 45.22] | setara |
| W1 | b256_fp32_resident | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 26.02× | [24.82, 26.98] | setara |
| W1 | b256_fp32_resident | d0-old → g16-cpu | efek mesin baru tanpa GPU | 1.60× | [1.57, 1.66] | - |
| W1 | b256_fp32_resident | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 41.69× | [39.65, 43.30] | setara |
| W1 | b4096_fp32 -> b4096_bf16 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 18.84× | [17.70, 19.14] | setara |
| W1 | b4096_fp32 -> b4096_bf16 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 26.06× | [24.07, 28.48] | setara |
| W1 | b4096_fp32 -> b4096_fp16 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 16.48× | [15.73, 16.97] | setara |
| W1 | b4096_fp32 -> b4096_fp16 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 22.79× | [21.69, 24.90] | setara |
| W1 | b4096_fp32 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 19.28× | [18.69, 19.61] | setara |
| W1 | b4096_fp32 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 1.38× | [1.32, 1.51] | - |
| W1 | b4096_fp32 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 26.66× | [25.41, 29.14] | setara |
| W2 | cpu_hist | d0-old → g16-cpu | efek mesin baru tanpa GPU | 2.26× | [2.19, 2.52] | - |
| W2 | cpu_hist -> cuda_hist | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 0.42× | [0.38, 0.44] | setara |
| W2 | cpu_hist -> cuda_hist | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 0.95× | [0.85, 1.06] | setara |
| W7 | gru_cpu_b1 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 3.09× | [2.44, 3.42] | - |
| W7 | gru_cpu_b1024 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 1.88× | [1.84, 1.92] | - |
| W7 | gru_cpu_b256 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 1.82× | [1.79, 1.86] | - |
| W7 | gru_cpu_b32 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 2.07× | [1.72, 2.51] | - |
| W7 | gru_cpu_b1 -> gru_cuda_b1 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 0.04× | [0.04, 0.06] | setara |
| W7 | gru_cpu_b1 -> gru_cuda_b1 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 0.14× | [0.13, 0.15] | setara |
| W7 | gru_cpu_b1024 -> gru_cuda_b1024 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 22.18× | [21.83, 22.38] | setara |
| W7 | gru_cpu_b1024 -> gru_cuda_b1024 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 41.65× | [40.86, 42.58] | setara |
| W7 | gru_cpu_b256 -> gru_cuda_b256 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 7.65× | [7.34, 7.79] | setara |
| W7 | gru_cpu_b256 -> gru_cuda_b256 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 13.92× | [13.39, 14.19] | setara |
| W7 | gru_cpu_b32 -> gru_cuda_b32 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 1.02× | [0.84, 1.23] | setara |
| W7 | gru_cpu_b32 -> gru_cuda_b32 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 2.11× | [1.97, 2.41] | setara |
| W7 | gru_cpu_b1 -> gru_cuda_notf32_b1 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 0.05× | [0.04, 0.06] | setara |
| W7 | gru_cpu_b1 -> gru_cuda_notf32_b1 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 0.16× | [0.13, 0.16] | setara |
| W7 | gru_cpu_b1024 -> gru_cuda_notf32_b1024 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 21.49× | [21.14, 21.65] | setara |
| W7 | gru_cpu_b1024 -> gru_cuda_notf32_b1024 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 40.35× | [39.59, 41.24] | setara |
| W7 | gru_cpu_b256 -> gru_cuda_notf32_b256 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 5.76× | [5.23, 5.87] | setara |
| W7 | gru_cpu_b256 -> gru_cuda_notf32_b256 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 10.48× | [9.51, 10.68] | setara |
| W7 | gru_cpu_b32 -> gru_cuda_notf32_b32 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 0.90× | [0.74, 1.08] | setara |
| W7 | gru_cpu_b32 -> gru_cuda_notf32_b32 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 1.87× | [1.70, 1.88] | setara |
| W7 | xgb_ttb_cpu_b1 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 1.64× | [1.57, 1.77] | - |
| W7 | xgb_ttb_cpu_b1024 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 2.82× | [2.72, 3.32] | - |
| W7 | xgb_ttb_cpu_b256 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 1.88× | [1.80, 2.23] | - |
| W7 | xgb_ttb_cpu_b32 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 3.16× | [2.13, 3.32] | - |
| W7 | xgb_ttb_cpu_b1 -> xgb_ttb_cuda_b1 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 0.07× | [0.06, 0.07] | setara |
| W7 | xgb_ttb_cpu_b1 -> xgb_ttb_cuda_b1 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 0.11× | [0.11, 0.12] | setara |
| W7 | xgb_ttb_cpu_b1024 -> xgb_ttb_cuda_b1024 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 0.61× | [0.53, 0.65] | setara |
| W7 | xgb_ttb_cpu_b1024 -> xgb_ttb_cuda_b1024 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 1.72× | [1.50, 2.03] | setara |
| W7 | xgb_ttb_cpu_b256 -> xgb_ttb_cuda_b256 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 0.46× | [0.41, 0.48] | setara |
| W7 | xgb_ttb_cpu_b256 -> xgb_ttb_cuda_b256 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 0.87× | [0.78, 1.00] | setara |
| W7 | xgb_ttb_cpu_b32 -> xgb_ttb_cuda_b32 | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 0.27× | [0.25, 0.39] | setara |
| W7 | xgb_ttb_cpu_b32 -> xgb_ttb_cuda_b32 | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 0.84× | [0.81, 0.93] | setara |

Speedup < 1 berarti yang dibandingkan lebih LAMBAT. Batch besar (b1024/b4096) setara antar-device pada batch yang sama, tetapi kualitasnya di bawah konfigurasi asli b256 dan tidak mencapai target time-to-target: kecepatannya tidak boleh dibaca sebagai percepatan pelatihan model yang sama.

### W2: XGBoost TTB (detik latih)

| config | g16-gpu | g16-cpu | d0-old |
|---|---|---|---|
| cpu_hist | belum diukur | 0.516 [0.501–0.531] | 1.17 [1.14–1.3] |
| cuda_hist | 1.23 [1.18–1.36] | tidak berlaku | tidak berlaku |

Sumber: `bench/results/<tag>/W2/<config>/run_*.json`

### W7: inferensi ONNX (latensi p50, ms)

| config | g16-gpu | g16-cpu | d0-old |
|---|---|---|---|
| gru_cpu_b1 | belum diukur | 0.152 [0.138–0.193] | 0.471 [0.461–0.479] |
| gru_cpu_b1024 | belum diukur | 98.6 [97–98.9] | 185 [182–189] |
| gru_cpu_b256 | belum diukur | 24.1 [23.6–24.6] | 43.9 [43.4–44.8] |
| gru_cpu_b32 | belum diukur | 3.61 [2.97–4.33] | 7.46 [7.35–7.52] |
| gru_cuda_b1 | 3.44 [3.06–3.74] | tidak berlaku | tidak berlaku |
| gru_cuda_b1024 | 4.45 [4.41–4.47] | tidak berlaku | tidak berlaku |
| gru_cuda_b256 | 3.16 [3.1–3.28] | tidak berlaku | tidak berlaku |
| gru_cuda_b32 | 3.53 [3.09–3.77] | tidak berlaku | tidak berlaku |
| gru_cuda_notf32_b1 | 3 [2.98–3.49] | tidak berlaku | tidak berlaku |
| gru_cuda_notf32_b1024 | 4.59 [4.56–4.61] | tidak berlaku | tidak berlaku |
| gru_cuda_notf32_b256 | 4.19 [4.19–4.62] | tidak berlaku | tidak berlaku |
| gru_cuda_notf32_b32 | 4 [3.97–4.39] | tidak berlaku | tidak berlaku |
| xgb_ttb_cpu_b1 | belum diukur | 0.0397 [0.0386–0.0416] | 0.0653 [0.0648–0.0701] |
| xgb_ttb_cpu_b1024 | belum diukur | 0.978 [0.97–0.992] | 2.76 [2.66–3.25] |
| xgb_ttb_cpu_b256 | belum diukur | 0.388 [0.371–0.406] | 0.73 [0.722–0.841] |
| xgb_ttb_cpu_b32 | belum diukur | 0.153 [0.149–0.226] | 0.483 [0.473–0.499] |
| xgb_ttb_cuda_b1 | 0.597 [0.571–0.606] | tidak berlaku | tidak berlaku |
| xgb_ttb_cuda_b1024 | 1.6 [1.52–1.84] | tidak berlaku | tidak berlaku |
| xgb_ttb_cuda_b256 | 0.843 [0.827–0.938] | tidak berlaku | tidak berlaku |
| xgb_ttb_cuda_b32 | 0.576 [0.521–0.59] | tidak berlaku | tidak berlaku |

Sumber: `bench/results/<tag>/W7/<config>/run_*.json`

## Gerbang G2 (paritas kualitas CPU vs GPU)

**26/26 config setara.** Kriteria ditetapkan sebelum run penuh (`bench/g2_check.py`): W1 selisih mean ≤ rentang antar-seed; W2/W7 selisih relatif ≤ 2%, akurasi ≤ 0.005.
Tidak setara: tidak ada.

Sumber: `bench/results/G2.json`

### Grafik

![1_speedup_gpu_murni](figures/1_speedup_gpu_murni.png)
![2_komponen_W1_b256_fp32](figures/2_komponen_W1_b256_fp32.png)
![2_komponen_W1_b256_fp32_resident](figures/2_komponen_W1_b256_fp32_resident.png)
![3_time_to_target_W1](figures/3_time_to_target_W1.png)
![4a_latensi_W7](figures/4a_latensi_W7.png)
![4b_throughput_W7](figures/4b_throughput_W7.png)
![5_telemetri_run_terpanjang](figures/5_telemetri_run_terpanjang.png)

## B3: latih ulang sesuai PRD (split val)

### Diagnosis baseline

| kelas | F1 GRU (mean 5 seed) | F1 XGBoost | n |
|---|---|---|---|
| A0 | 0.876 | 0.913 | 12325 |
| A1 | 0.586 | 0.617 | 594 |
| A3 | 1.000 | 1.000 | 541 |
| A7 | 0.436 | 0.627 | 545 |
| A8 | 0.332 | 0.348 | 700 |
| degradasi_bertahap | 0.194 | 0.381 | 1122 |
| masalah_sensor | 0.663 | 0.918 | 587 |

| menit sejak onset | 0-10 | 10-30 | 30-60 | 60-120 | 120-inf |
|---|---|---|---|---|---|
| akurasi mode GRU | 0.568 | 0.648 | 0.673 | 0.522 | 0.287 |

Sumber: `bench/results/g16-gpu/B3/diagnosis.json`

### Batas label implisit (dari data, tanpa model)

Label `failure_mode` bertahan dari onset sampai akhir trip, sedangkan A1 (pintu) dan A7 (kejut ambien) adalah peristiwa sementara. Porsi jendela berlabel kelas itu yang tidak memuat jejak peristiwanya:

| kelas | total tanpa jejak | 0-10 | 10-30 | 30-60 | 60-120 | 120-inf | jendela A0 dengan jejak |
|---|---|---|---|---|---|---|---|
| A1 | 58.4% | 0.0% | 0.0% | 0.0% | 60.6% | 100.0% | 0.0% |
| A7 | 50.5% | 0.0% | 0.0% | 0.0% | 44.5% | 100.0% | 0.0% |

Jendela tanpa jejak tidak bisa dibedakan dari jendela sehat oleh model berbasis jendela apa pun; ini membatasi Macro F1 yang dapat dicapai. Definisi metrik dan target TIDAK diubah.
Sumber: `bench/results/g16-gpu/B3/label_check.json`

### Sweep (W3) dan konfirmasi 5 seed + ablation (W4)

- Sweep gru: 60 trial, 71 menit (51 trial/jam, g16-gpu), skor terbaik 0.7540.
- Sweep xgb: 60 trial, 11 menit (336 trial/jam, g16-gpu), skor terbaik 0.7294.

| model | varian | skor mean | rentang | Macro F1 | PR-AUC | forecast t+30 |
|---|---|---|---|---|---|---|
| gru | baseline | 0.6342 | 0.0219 | 0.5839 | 0.6846 | 0.2093 |
| gru | baseline_tanpa_stat | 0.2997 | 1.0302 | 0.4146 | 0.5848 | 0.2348 |
| gru | sweep_top1 | 0.7292 | 0.0393 | 0.6756 | 0.7829 | 0.2088 |
| gru | sweep_top2 | 0.7184 | 0.0451 | 0.6737 | 0.7632 | 0.2088 |
| gru | sweep_top3 | 0.7076 | 0.0909 | 0.6582 | 0.7570 | 0.2075 |
| gru | top1_tanpa_stat | 0.7203 | 0.0260 | 0.6815 | 0.7591 | 0.2121 |
| gru | top1_bobot_asli | 0.6405 | 0.1208 | 0.5774 | 0.7035 | 0.2180 |
| xgb | baseline | 0.7215 | 0.0000 | 0.6865 | 0.7566 | - |
| xgb | sweep_top1 | 0.7247 | 0.0094 | 0.6948 | 0.7545 | - |
| xgb | sweep_top2 | 0.7260 | 0.0041 | 0.6943 | 0.7577 | - |
| xgb | sweep_top3 | 0.7231 | 0.0069 | 0.6887 | 0.7575 | - |

Aturan adopsi (didaftarkan sebelum sweep): kandidat lolos bila skor mean > mean baseline + rentang baseline. Kandidat lolos: {'gru': 'gru/sweep_top1', 'xgb': 'xgb/sweep_top2'}. Untuk XGBoost, baseline deterministik (rentang 0) sehingga selisih sekecil apa pun lolos; kenaikannya tidak berarti secara praktis.
Sumber: `bench/results/g16-gpu/B3/keputusan_kandidat.json`

### Kandidat yang diajukan ke G3

`backend/models/candidates/coldtrack_gru_b3.onnx` (sweep_top1, 254,883 parameter, seed final 1000); paritas ONNX vs PyTorch: OK. Metrik val yang dilaporkan adalah mean 5 seed di tabel atas; metrik model seed 1000 optimistis karena konfigurasinya dipilih memakai seed itu.

| model (CPU EP) | p50 batch 1 (ms) | p50 batch 1024 (ms) |
|---|---|---|
| proposal | 0.170 | 150.7 |
| kandidat_b3 | 1.474 | 464.7 |

Sumber: `bench/results/g16-cpu/B3/latensi_kandidat.json`

## Gerbang G3: split test (dipakai sekali per model)

| metrik (test) | baseline_proposal | kandidat_b3 |
|---|---|---|
| forecast_t15_mae_c | 0.1521 | 0.1565 |
| forecast_t30_mae_c | 0.1976 | 0.1924 |
| forecast_t60_mae_c | 0.2372 | 0.2346 |
| macro_f1 | 0.5807 | 0.6680 |
| akurasi | 0.8134 | 0.8694 |
| anomali_pr_auc | 0.7105 | 0.7862 |
| ttb_mae_semua_menit | 52.4063 | 48.0751 |
| ttb_mae_le10_menit | 3.4301 | 5.1161 |
| ttb_mae_le30_menit | 10.8016 | 12.1569 |

Log akses split test (dicatat sebelum evaluasi; run kedua untuk id yang sama ditolak):

- `baseline_proposal`: ml/reports/coldtrack.onnx (sha256 3948c4476313…), 2026-10-10T22:53:08+00:00, commit 1e668e1
- `kandidat_b3`: backend/models/candidates/coldtrack_gru_b3.onnx (sha256 fab911760e87…), 2026-10-10T22:53:13+00:00, commit 1e668e1
- `b4_berkeley_v1_kesehatan`: ml/sensor_health/artifacts/berkeley_v1_kesehatan.json (sha256 19fbf3cd0220…), 2026-10-11T01:49:41+00:00, commit 073756a

**Keputusan G3: disetujui dengan catatan: v3 menjadi model acuan dan diagnosis provider bawaan backend** (2026-10-11). Kandidat lebih baik dari baseline di split val (5 seed, aturan adopsi yang didaftarkan sebelum sweep) dan di split test yang dipakai sekali. Forecast tidak memburuk berarti; TTB produksi tetap XGBoost sehingga penurunan head TTB GRU tidak berdampak. Trade-off latensi diterima user: tetap jauh di bawah batas PRD 300 ms per panggilan. Target Macro F1 dan PR-AUC PRD belum tercapai; batasnya dilaporkan (label implisit).

Pembaruan 2026-10-11: Diagnosis provider bawaan backend dipindah dari checkpoint-2 ke v3 (opsi 2), dengan flag rollback model.diagnosis_provider di backend/config.yaml; checkpoint-2 dipertahankan. Mitigasi data tidak lengkap: opsi 2: data_lengkap=false + catatan_data + keyakinan dibatasi 0,5 bila ada jeda > 90 detik di 60 bacaan terakhir; status mesin fisika tidak berubah.

Catatan:

- Target PRD belum tercapai: Macro F1 test 0,668 (> 0,80) dan PR-AUC test 0,786 (> 0,85); batas utama definisi label (58 % jendela A1 dan 51 % A7 di val tanpa jejak kejadian).
- Perbandingan v3 vs checkpoint-2 dilakukan di data v4 (asing bagi checkpoint-2), v3 dituning di split val yang sama, definisi label pintu checkpoint-2 berbeda (>= 20 menit), uji di ml/dataset_v3.parquet belum dapat dijalankan (berkas tidak ada).
- Latensi v3 0,21 -> 1,38 ms per panggilan (CPU, batch 1), jauh di bawah anggaran 300 ms.
- Metrik hanya berlaku untuk jendela 60 menit tanpa bacaan hilang (32 % jendela val memuat bacaan hilang).
- Split test tidak disentuh lagi; jatah satu kali v3 sudah dipakai.

### Banding checkpoint-2 vs v2 vs v3 (split val, 16500 jendela, 105 trip)

| model | MAE t+30 | AUROC pintu | AUROC kejut | AUROC sensor | recall pintu | recall sensor | sehat dilabel gangguan |
|---|---|---|---|---|---|---|---|
| checkpoint2_backend | 1.398 | 0.613 | 0.483 | 0.341 | 0.00 | 0.58 | 23.8% |
| v2_proposal | 0.211 | 0.728 | 0.860 | 0.978 | 0.42 | 0.68 | 10.2% |
| v3_b3 | 0.208 | 0.837 | 0.894 | 0.975 | 0.44 | 0.89 | 3.6% |

Bias: v3 dipilih di split val (sedikit optimistis); v4 out-of-distribution untuk checkpoint-2 (dilatih di simulator garis checkpoint-2).
Sumber: `bench/results/g16-cpu/B7/banding_model_val.json`


Sumber: `bench/results/test/*.json`, `bench/results/test_access_log.json`

## Gerbang G4: sensor-health Berkeley (mote test, sekali)

**tidak lulus: aturan v0 tetap default, berkeley_v1 tidak diaktifkan** (2026-10-11). H = 24 jam, kriteria dipra-registrasi sebelum data diunduh (`bench/results/keputusan/G4_kriteria.json`, `G4_definisi.json`).

| metrik (mote test) | v0 aturan | berkeley_v1 (kesehatan) |
|---|---|---|
| PR-AUC | 0.422 | 0.876 |
| recall jendela | 0.739 | 1.000 |
| alarm palsu / mote-hari | 0.239 | 0.665 |
| recall kejadian | 1.000 | 1.000 |
| lead time median (menit) | 1434.000 | 1435.000 |

Kriteria: 1_pr_auc_v1_ge_v0_plus_0.05 = ya, 2_alarm_palsu_le_v0_pada_recall_ge_v0 = tidak, G4_lulus = tidak.

- Kriteria 1 terpenuhi: PR-AUC v1 jauh di atas v0 + 0,05 di mote test.
- Kriteria 2 tidak terpenuhi: alarm palsu per mote-hari v1 lebih tinggi dari v0, meski recall v1 lebih tinggi.
- Aturan baterai v0 (< 2,4 V) hampir berimpit dengan definisi kegagalan di data lab (nilai ekstrem hanya muncul saat tegangan < 2,4 V), sehingga v0 adalah pembanding yang sangat kuat di domain ini.
- Hanya 54 kejadian kegagalan (11 di mote test): kekuatan statistik rendah.
- Domain lab (Mica2, bangunan) berbeda dari truk; skema fitur truk tidak memuat tegangan baterai, padahal tegangan adalah sinyal terkuat bagi v0 dan v1.
- Varian dengan level suhu absolut (val PR-AUC lebih tinggi) tidak dipilih karena level suhu lab dapat menjadi penanda kalender.

Sumber: `bench/results/test/b4_berkeley_v1_kesehatan.json`, `bench/results/keputusan/G4.json`

## B5: benchmark W3 / W4 / W6 / W8

| workload | config | metrik | g16-gpu | g16-cpu | d0-old |
|---|---|---|---|---|---|
| W3 | gru | sweep_s (s) | 69.02 | 1793 | 3612 |
| W3 | xgb_cpu | sweep_s (s) | — | 174.7 | 545.2 |
| W3 | xgb_cuda | sweep_s (s) | 158.8 | tidak berlaku | tidak berlaku |
| W4 | stat_vs_tanpa | ablation_total_s (s) | 102.8 | 2428 | 4592 |
| W6 | cpu_hist | dinding_total_s (s) | — | 8.414 [8.338–9.359] | 16.03 [15.34–17.53] |
| W6 | cuda_hist | dinding_total_s (s) | 8.043 [7.873–8.763] | tidak berlaku | tidak berlaku |
| W8 | truk100 | siklus_median_s (s) | tidak berlaku | 3.092 [3.039–3.23] | 7.537 [7.213–7.818] |
| W8 | truk100_2inti | siklus_median_s (s) | tidak berlaku | 2.575 [2.491–2.69] | 5.761 [5.675–6.087] |
| W8 | truk24 | siklus_median_s (s) | tidak berlaku | 0.6465 [0.6061–0.7381] | 1.719 [1.551–1.873] |
| W8 | truk500 | siklus_median_s (s) | tidak berlaku | 18.68 [17.78–19.09] | 40.32 [39.93–42.24] |

Median [min–maks] dari 5 ulangan; satu angka = satu run terukur. '—' = varian CPU tidak dijalankan di tag GPU (pasangannya diukur di g16-cpu). Sumber: `bench/results/<tag>/<W3|W4|W6|W8>/<config>/run_*.json`

### Speedup B5

| workload | config | perbandingan | arti | speedup | CI 95 % |
|---|---|---|---|---|---|
| W3 | gru | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 25.98× | - (1 run) |
| W3 | gru | d0-old → g16-cpu | efek mesin baru tanpa GPU | 2.01× | - (1 run) |
| W3 | gru | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 52.33× | - (1 run) |
| W3 | xgb_cpu | d0-old → g16-cpu | efek mesin baru tanpa GPU | 3.12× | - (1 run) |
| W3 | xgb_cpu -> xgb_cuda | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 1.10× | - (1 run) |
| W3 | xgb_cpu -> xgb_cuda | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 3.43× | - (1 run) |
| W4 | stat_vs_tanpa | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 23.61× | - (1 run) |
| W4 | stat_vs_tanpa | d0-old → g16-cpu | efek mesin baru tanpa GPU | 1.89× | - (1 run) |
| W4 | stat_vs_tanpa | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 44.65× | - (1 run) |
| W6 | cpu_hist | d0-old → g16-cpu | efek mesin baru tanpa GPU | 1.91× | [1.71, 2.08] |
| W6 | cpu_hist -> cuda_hist | g16-cpu → g16-gpu | efek GPU murni (mesin sama) | 1.05× | [0.96, 1.16] |
| W6 | cpu_hist -> cuda_hist | d0-old → g16-gpu | sebelum vs sesudah (gabungan) | 1.99× | [1.83, 2.18] |
| W8 | truk100 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 2.44× | [2.28, 2.54] |
| W8 | truk100_2inti | d0-old → g16-cpu | efek mesin baru tanpa GPU | 2.24× | [2.14, 2.36] |
| W8 | truk24 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 2.66× | [2.33, 2.93] |
| W8 | truk500 | d0-old → g16-cpu | efek mesin baru tanpa GPU | 2.16× | [2.11, 2.27] |

### Paritas kualitas B5 (val)

| workload | config | metrik | g16-gpu | g16-cpu | d0-old |
|---|---|---|---|---|---|
| W3 | gru / gru | skor terbaik sweep | 0.6249 | 0.6196 | 0.6283 |
| W3 | xgb_cuda / xgb_cpu | skor terbaik sweep | 0.7252 | 0.7248 | 0.7248 |
| W4 | stat_vs_tanpa / stat_vs_tanpa | macro F1 mean 5 seed, dengan statistik | 0.5096 | 0.5109 | 0.5114 |
| W4 | stat_vs_tanpa / stat_vs_tanpa | macro F1 mean 5 seed, tanpa statistik | 0.3572 | 0.3558 | 0.3558 |
| W6 | cuda_hist / cpu_hist | PR-AUC mote val | 0.8725 | 0.8738 | 0.8738 |

### Telemetri GPU selama B5 (g16-gpu)

| workload | config | suhu maks (°C) | daya median (W) | utilisasi median (%) | alasan throttle (NVML) |
|---|---|---|---|---|---|
| W3 | gru | 70 | 65.0 | 57 | 0x0000000000000000, 0x0000000000000004 |
| W3 | xgb_cuda | 60 | 37.8 | 37 | 0x0000000000000000 |
| W4 | stat_vs_tanpa | 69 | 53.0 | 45 | 0x0000000000000000 |
| W6 | cuda_hist | 49 | 3.4 | 0 | 0x0000000000000000 |

Alasan throttle `0x4` = batas daya perangkat lunak (wajar di laptop), `0x0` = tidak ada. Tidak ada alasan termal/perlambatan perangkat keras (0x8/0x20/0x40) yang tercatat.

### Catatan B5

- **W6:** waktu didominasi pemuatan data dan pembangunan fitur di CPU (g16-gpu: bangun fitur 7.68 s dari total 8.04 s, latih 0.35 s; g16-cpu: bangun fitur 8.22 s dari total 8.41 s, latih 0.16 s), jadi GPU hampir tidak mengubah waktu total. Prediksi XGBoost di jalur GPU juga jatuh ke DMatrix karena data input ada di CPU (peringatan XGBoost `mismatched devices`); ini sedikit merugikan sisi GPU dan tidak diperbaiki di tengah benchmark.
- **W8** mengukur komputasi siklus inferensi (`POST /api/v1/analyze`, sama dengan `predict_last` worker armada) tanpa database dan broker. Varian 2 inti adalah G16 yang dibatasi 2 inti, **bukan** VPS 2 vCPU; tidak ada klaim target PRD (< 30 s / 100 truk di VPS 2 vCPU) terpenuhi.
- **W3/W4** satu run terukur per tag (banyak pelatihan di dalamnya), jadi speedup-nya tanpa CI.

### Kesamaan kode antar-device (B2 + B5)

| workload | config | commit g16-cpu | commit d0-old | kode workload | berkas berbeda |
|---|---|---|---|---|---|
| W1 | 4 config | 009ed57 | fcd0fb0 | identik (berkas berbeda tidak dipakai workload ini) | `bench/devices/d0-old.yaml` |
| W1 | b256_fp32_resident | 5b64886 | 9d97fe9 | **berbeda** (tinjauan manual: tidak memengaruhi W1. `bench/harness.py` hanya menambah parameter opsional repeats/warmup (bawaan sama) untuk W3/W4; berkas lain yang berbeda tidak di-import W1; bukti: `git diff 5b64886 9d97fe9 -- bench/harness.py`) | `bench/chain_b2b3.sh`, `bench/fe.sh`, `bench/harness.py`, `ml/reports/coldtrack_b3.onnx`, `ml/reports/labels_b3.json`, `ml/sensor_health/data.py` … |
| W2 | cpu_hist | 009ed57 | fcd0fb0 | identik (berkas berbeda tidak dipakai workload ini) | `bench/devices/d0-old.yaml` |
| W7 | 8 config | 009ed57 | fcd0fb0 | identik (berkas berbeda tidak dipakai workload ini) | `bench/devices/d0-old.yaml` |
| W3 | gru, xgb_cpu | 5d13490 | fd61a98 | identik (berkas berbeda tidak dipakai workload ini) | `bench/devices/d0-old.yaml`, `bench/workloads/w8_siklus.py`, `ml/preprocess/export_fleet.py` |
| W4 | stat_vs_tanpa | 5d13490 | fd61a98 | identik (berkas berbeda tidak dipakai workload ini) | `bench/devices/d0-old.yaml`, `bench/workloads/w8_siklus.py`, `ml/preprocess/export_fleet.py` |
| W6 | cpu_hist | 5d13490 | fd61a98 | identik (berkas berbeda tidak dipakai workload ini) | `bench/devices/d0-old.yaml`, `bench/workloads/w8_siklus.py`, `ml/preprocess/export_fleet.py` |
| W8 | 4 config | 5d13490 | fd61a98 | **berbeda** | `backend/app/adapters/__init__.py`, `backend/app/clock.py`, `backend/app/db/__init__.py`, `backend/app/db/migrate.py`, `backend/app/db/seed.py`, `backend/app/fleet/__init__.py` … |

W8 mengirim jendela 60 bacaan ke `POST /api/v1/analyze`; di kedua versi backend model dijalankan untuk satu jendela, tetapi kodenya tidak identik (versi armada menambah `predict_last` dan konversi zona waktu).

**Uji A/B kode (mesin sama, g16-cpu, 100 truk, 3 ulangan bergantian):** median siklus `fd61a98` 3.184 s vs `5d13490` 3.435 s; kode `5d13490` 7.9% lebih berat. Status keluaran identik. Karena G16 menjalankan kode yang lebih berat, speedup W8 laptop lama → G16 di atas cenderung lebih kecil dari seharusnya (konservatif terhadap G16).

Sumber: `bench/results/g16-cpu/W8_ab_kode/ab.json` (`python -m bench.w8_ab_kode`).

## Keterbatasan

- Satu unit per device dan satu mode daya; hasil laptop lain dengan seri yang sama bisa berbeda (termal, BIOS).
- Model kecil (GRU 3×128, XGBoost), sehingga GPU sering tidak terpakai penuh; percepatan GPU untuk model besar tidak dapat disimpulkan dari sini.
- Data simulasi (dataset v4), bukan logger truk nyata.
- WSL2 dengan batas memori 12 GB di kedua laptop; Windows native tidak diukur.
- Laptop lama mengalami throttling termal pada run pertama; run itu dibatalkan dan diulang dalam mode Extreme Performance. Menurut pesan commit `4c193ca`, CPU-nya tetap di-throttle termal secara berkala selama paket B5 (±100 °C → ±22 % performa); data suhunya tidak ada di repo. Angka laptop lama, terutama B5, bisa lebih lambat daripada kemampuan CPU itu dengan pendinginan baik, sehingga speedup laptop lama → G16 cenderung dilebih-lebihkan.
