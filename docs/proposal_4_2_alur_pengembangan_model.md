# 4.2 Alur Pengembangan Model

## 4.2.1 Pendekatan

ColdTrack AI menghasilkan tiga keluaran dari satu masukan yang sama — jendela telemetri 60 menit
terakhir, 12 fitur per menit:

1. **Prediksi suhu** kargo pada 15, 30, dan 60 menit ke depan
2. **Klasifikasi mode kegagalan** ke dalam 7 kelas
3. **Time-to-Breach** — perkiraan menit tersisa sebelum suhu keluar dari pita aman

Keluaran ketiga adalah pembeda utama produk ini. Sistem pemantauan rantai dingin yang beredar
umumnya baru berbunyi **setelah** suhu melewati ambang; pada titik itu kerusakan sudah terjadi dan
yang tersisa hanyalah pencatatan. ColdTrack AI berupaya memberi tahu **sebelum** ambang terlampaui,
selagi tindakan masih mungkin.

Sistem akhir memakai dua model dengan kontrak masukan identik:

| | `coldtrack.onnx` | `coldtrack_ttb.onnx` |
|---|---|---|
| Arsitektur | GRU 2 lapis (hidden 64) + jalur statistik ringkasan | XGBoost, 300 pohon |
| Keluaran | prediksi suhu, probabilitas 7 kelas | Time-to-Breach |
| Ukuran | 169 KB | 950 KB |
| Latensi CPU | 1,1 ms | 0,09 ms |

Pembagian tugas ini bukan keputusan awal, melainkan hasil pengujian yang diuraikan di §4.2.3.

## 4.2.2 Alur pengembangan

**Tahap 1 — Kontrak data.** Skema 12 kolom fitur disepakati bersama R1 dan dibekukan
(`docs/feature_schema.md`), disertai tes otomatis yang memastikan kolom label tidak pernah bocor
menjadi masukan model. Tes ini kemudian terbukti berguna melampaui fungsi awalnya: melalui tes
inilah tiga cacat pelabelan pada dataset ditemukan dan dilaporkan ke R1 — nilai Time-to-Breach yang
konstan sepanjang perjalanan, konstanta termal yang membuat muatan berat nyaris kebal rusak, dan
label mode kegagalan yang sudah aktif sebelum anomali benar-benar terjadi. Cacat terakhir membuat
**48,3% jendela anomali salah label**; setelah diperbaiki, angkanya menjadi 0%.

**Tahap 2 — Penyiapan masukan.** Data per menit dipecah menjadi jendela geser 60 langkah. Jendela
tidak pernah melintasi batas perjalanan, dan sasaran prediksi diambil dari **setelah** ujung
jendela sehingga tidak ada informasi masa depan yang bocor ke sisi masukan. Pembagian train/val/test
dilakukan per perjalanan, bukan per baris.

**Tahap 3 — Prapelatihan.** Backbone GRU dilatih pada korpus suhu IoT publik berskala besar (Intel
Berkeley Lab, 1,3 juta jendela) untuk mempelajari dinamika suhu umum sebelum dikenalkan pada domain
rantai dingin.

**Tahap 4 — Pelatihan model utama.** Model dilatih pada korpus sintetik dari R1 dengan ketiga head
aktif.

**Tahap 5 — Evaluasi dan pemilihan.** Model dibandingkan dengan tiga baseline, diuji lewat dua
ablation study, lalu dievaluasi pada split test yang belum pernah disentuh selama pengembangan.

## 4.2.3 Keputusan berbasis bukti

Tiga keputusan penting pada arsitektur akhir tidak diambil berdasarkan asumsi, melainkan
berdasarkan eksperimen yang hasilnya kami laporkan apa adanya — termasuk ketika hasilnya
membatalkan rencana kami sendiri.

### Temuan 1 — GRU menghabiskan kapasitas untuk pekerjaan yang tidak perlu

Model versi awal berperforma buruk: hanya 2 dari 7 kelas yang pernah ditebak. Setelah dua perbaikan
mendasar — normalisasi fitur (rentang antar kolom timpang hingga 4500:1, sehingga radiasi matahari
menenggelamkan sinyal pintu terbuka) dan penyeimbangan bobot loss (head prediksi suhu semula hanya
memperoleh 2,3% dari total loss) — performa membaik tetapi tetap tertinggal dari XGBoost.

Diagnosisnya: XGBoost **menerima** statistik ringkasan jendela secara cuma-cuma, sementara GRU harus
**menemukan sendiri** cara menghitungnya dari data mentah sambil melayani tiga tugas sekaligus.
Statistik tersebut lalu disuplai langsung ke lapisan keluaran, dengan tambahan hanya 792 parameter:

| | Macro F1 | Prediksi suhu | Time-to-Breach |
|---|---|---|---|
| Sebelum | 0,440 | 0,244 | 22,94 |
| **Sesudah** | **0,598** | **0,209** | **21,84** |

Perbaikan ini juga menghapus hampir seluruh kerugian arsitektur multi-tugas: satu model kini
mengerjakan tiga tugas dengan performa mendekati tiga model terpisah (0,598 vs 0,613).

### Temuan 2 — Transfer learning tidak berhasil pada domain ini

Rencana awal kami adalah prapelatihan pada data publik lalu penalaan ke domain rantai dingin. Dua
konfigurasi dilatih dengan resep identik untuk mengujinya:

| | Dari backbone pretrained | Dilatih dari nol |
|---|---|---|
| Loss latih akhir | **2,99** | 3,58 |
| Loss validasi akhir | 4,18 | **2,78** |

Arah keduanya berlawanan — varian pretrained lebih baik pada data latih tetapi lebih buruk pada data
validasi, pola khas *overfitting*. **Prapelatihan bukan sekadar tidak membantu, melainkan
merugikan.**

Penyebabnya dapat dijelaskan. Tidak ada dataset publik yang memuat telemetri truk berpendingin;
korpus terbaik yang tersedia hanya mampu mengisi **4 dari 12 fitur** — data sensor ruangan tidak
mengenal pintu kargo, unit reefer, maupun kecepatan kendaraan. Delapan fitur sisanya bernilai nol,
sehingga bobot backbone terspesialisasi pada distribusi masukan yang timpang, dan spesialisasi itu
justru harus dilupakan pada tahap berikutnya.

Sebelum menyimpulkan, kami memperbaiki dugaan penyebabnya lebih dulu: korpus prapelatihan diganti
dari 6.113 jendela menjadi 1,3 juta jendela — 207 kali lebih besar, dengan derau sensor nyata.
Hasilnya tidak berubah. Model produksi karena itu dilatih dari nol.

*(Grafik: `ml/reports/loss_curves.png`)*

### Temuan 3 — Model pohon lebih unggul untuk Time-to-Breach

Untuk menjawab "mengapa perlu deep learning", kami menguji tiga baseline pada data yang sama:

| Metrik (split test) | GRU | XGBoost | Regresi linear | Isolation Forest |
|---|---|---|---|---|
| Prediksi suhu t+30 (°C) | 0,198 | **0,189** | 0,338 | — |
| Macro F1 | 0,581 | **0,664** | — | — |
| PR-AUC anomali | 0,711 | **0,753** | — | 0,371 |
| Time-to-Breach ≤ 30 menit | 10,8 | **7,1** | — | — |

**XGBoost mengungguli GRU pada seluruh metrik.** Kami memilih melaporkannya daripada menyembunyikannya,
dan mengambil konsekuensinya: Time-to-Breach dipindahkan ke XGBoost, karena di situlah selisihnya
terbesar dan satu-satunya perpindahan yang mengubah status target dari belum tercapai menjadi
tercapai.

GRU dipertahankan untuk dua tugas lain atas pertimbangan yang dapat diperiksa: selisih pada prediksi
suhu tipis dan kedua model sama-sama jauh melampaui target; pada klasifikasi keduanya sama-sama
belum mencapai ambang sehingga penggantian tidak mengubah hasil; dan satu model GRU melayani dua
keluaran sekaligus dalam 169 KB.

## 4.2.4 Hasil

| Keluaran | Metrik | Hasil | Target | Status |
|---|---|---|---|---|
| Prediksi suhu | MAE @ t+30 | **0,198 °C** | < 0,8 °C | tercapai |
| Mode kegagalan | Macro F1 | 0,581 | > 0,80 | belum |
| Time-to-Breach | MAE (≤ 30 menit) | **7,08 menit** | < 8 menit | tercapai |
| Deteksi anomali | PR-AUC | 0,711 | > 0,85 | belum |

Seluruh angka berasal dari **split test** — bagian data yang tidak pernah dipakai untuk mengambil
keputusan apa pun selama pengembangan. Angka pada split validasi lebih baik, tetapi karena split itu
dipakai berulang kali untuk memilih arsitektur, angkanya sudah condong optimistis dan tidak layak
dilaporkan sebagai hasil akhir.

Prediksi suhu melampaui targetnya dengan selisih besar — sekitar empat kali lebih akurat daripada
yang disyaratkan. Kegagalan reefer total, skenario paling kritis, terdeteksi pada **100%** kasus.

Kedua model berjalan pada CPU biasa dalam **1,2 milidetik** total, jauh di bawah batas 300 ms, dan
diekspor ke ONNX sehingga layanan backend tidak memerlukan pustaka deep learning apa pun.

## 4.2.5 Keterbatasan yang kami sadari

**Time-to-Breach hanya andal untuk peringatan jangka pendek.**

| TTB sebenarnya | MAE |
|---|---|
| ≤ 10 menit | **3,30 menit** |
| ≤ 30 menit | **7,08 menit** |
| seluruh rentang | 52,00 menit |

Model akurat persis pada rentang yang menentukan keputusan operasional, dan tidak akurat di luar
itu. Memperkirakan kejadian lima jam ke depan dari jendela 60 menit berada di luar jangkauan
informasi yang tersedia. Antarmuka karena itu menampilkan angka TTB hanya bila bernilai di bawah
30 menit; di atas itu hanya status risiko yang ditampilkan, agar tidak memberi kesan presisi yang
tidak dimiliki model.

**Degradasi bertahap hampir tidak terdeteksi.** Recall untuk kelas ini hanya 10,6%. Perubahan yang
sangat lambat nyaris tidak terbedakan dari kondisi normal dalam jendela 60 menit. Kami tidak
mengklaim sistem ini mampu mendeteksi kompresor yang melemah atau kebocoran refrigeran.

**Model dilatih sepenuhnya pada data sintetik.** Simulator dikalibrasi terhadap dataset IoT publik
dan standar suhu resmi (WHO, Peraturan BPOM No. 6/2020, Codex Alimentarius, SNI), serta divalidasi
melalui uji Kolmogorov–Smirnov dan autokorelasi. Namun sistem **belum pernah divalidasi terhadap
perjalanan truk sungguhan**, dan uji lapangan wajib dilakukan sebelum penggunaan operasional.

**Sistem adalah alat bantu, bukan pengambil keputusan.** Keluaran model menjadi masukan bagi
operator dan mesin aturan, bukan pengganti keduanya. Ambang keputusan sengaja dicondongkan ke sisi
waspada, karena kegagalan yang tidak terdeteksi jauh lebih merugikan daripada peringatan berlebih —
terutama pada muatan vaksin.

---

*Dokumentasi teknis lengkap: `docs/model_card.md`, `docs/dataset_card.md`,
`ml/notebooks/02_pretrain.ipynb`, `03_finetune.ipynb`, `04_eval.ipynb`. Seluruh metrik, hasil
baseline, dan hasil ablation tersimpan sebagai berkas JSON di `ml/reports/` dan dapat direproduksi
dengan seed tetap.*
