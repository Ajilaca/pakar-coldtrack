# Laporan latih ulang ColdTrack + benchmark device

> Dibangkitkan oleh `bench/report/build_report.py` pada 2026-10-10T10:39:12+00:00. Jangan diedit manual:
> setiap angka berasal dari JSON di `bench/results/`.

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
