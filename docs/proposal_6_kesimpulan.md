# 6. Kesimpulan

## 6.1 Apa yang kami bangun

ColdTrack AI mengubah telemetri rantai dingin yang selama ini hanya dicatat menjadi keputusan yang
dapat ditindaklanjuti. Dari satu masukan berupa deret pembacaan sensor, sistem menghasilkan empat
hal sekaligus: prediksi suhu, diagnosis jenis kerusakan, jumlah menit tersisa sebelum ambang
terlampaui, dan tiga langkah tindakan yang sesuai dengan penyebabnya.

Seluruhnya berjalan sinkron pada CPU biasa, dengan model berukuran puluhan ribu parameter.

## 6.2 Apa yang berhasil

| Sasaran | Hasil | Target | Status |
|---|---|---|---|
| Prediksi suhu, MAE t+30 | **0,198 °C** | < 0,8 °C | tercapai |
| Time-to-Breach, MAE (≤ 30 menit) | **7,60 menit** | < 8 menit | tercapai |
| Klasifikasi mode kegagalan, Macro F1 | 0,581 | > 0,80 | belum |
| Deteksi anomali, PR-AUC | 0,711 | > 0,85 | belum |

Dua dari empat sasaran tercapai. Pada kelima skenario demonstrasi, diagnosis model tepat seluruhnya
dan status yang dihasilkan sesuai dengan yang diharapkan.

## 6.3 Apa yang kami pelajari — termasuk yang tidak sesuai rencana

Tiga temuan mengubah arah pengembangan, dan kami melaporkannya apa adanya.

**Prapelatihan justru merugikan.** Rencana awal kami adalah melatih backbone pada korpus suhu IoT
publik lalu menalanya ke domain rantai dingin. Hasil pengujian menunjukkan varian yang diprapelatih
lebih baik pada data latih tetapi lebih buruk pada data validasi — pola khas *overfitting*. Model
final dilatih dari nol.

**Model pohon mengungguli jaringan saraf pada tugas Time-to-Breach.** Kepala TTB milik GRU
tertinggal jauh di rentang yang justru menentukan keputusan (MAE 17,9 menit dibanding 7,6 menit
untuk TTB ≤ 30 menit). Tugas itu kami pindahkan ke XGBoost. Sistem final memakai dua model, bukan
satu.

**Kesalahan yang paling berbahaya ditemukan justru di tahap integrasi, bukan di tahap pemodelan.**
Status keselamatan sempat dihitung hanya dari prediksi suhu, sehingga bertentangan dengan
Time-to-Breach yang dihasilkan model terpisah — empat dari lima skenario menampilkan status AMAN
padahal muatan akan melewati ambang dalam waktu di bawah 25 menit. Ini menegaskan bahwa metrik
model yang baik belum menjamin sistem yang benar.

## 6.4 Keterbatasan yang kami akui

**Belum pernah diuji pada telemetri truk sungguhan.** Seluruh data pelatihan berasal dari simulator
fisika kami sendiri, karena label kebenaran untuk kegagalan rantai dingin tidak tersedia publik.
Validasi sim-to-real menunjukkan data kami secara kuantitatif lebih stabil daripada data nyata,
yang sebagian dapat dijelaskan secara fisika dan sebagian kami duga berasal dari parameter derau
simulator yang terlalu kecil.

**Dua sasaran metrik belum tercapai.** Kami memilih melaporkannya apa adanya. Menurunkan target
setelah melihat hasil akan terbaca sebagai menyesuaikan ukuran pada hasil yang sudah didapat.

**Keyakinan model rendah pada dua kelas kerusakan** — degradasi bertahap dan masalah sensor.
Keduanya kelas hasil penggabungan, dan keduanya memang sulit dibedakan dari kondisi normal. Sistem
karena itu tidak menjadikan keyakinan sebagai penentu status.

**Atribusi fitur masih bersifat heuristik**, dihitung dari data masukan dan bukan dari pembongkaran
bobot model. Metode atribusi formal seperti SHAP masuk rencana pengembangan.

## 6.5 Langkah berikutnya

| Prioritas | Langkah | Alasan |
|---|---|---|
| 1 | Uji lapangan pada armada mitra | Satu-satunya cara menutup kesenjangan sim-to-real |
| 2 | Pelatihan ulang dengan telemetri nyata | Metrik saat ini belum teruji di luar simulasi |
| 3 | Menaikkan derau simulator | Data sintetik terbukti terlalu bersih |
| 4 | Memisahkan kembali kelas yang digabung | Kemungkinan penyebab keyakinan rendah |
| 5 | Atribusi fitur formal (SHAP) | Memperkuat dasar penjelasan yang ditampilkan |
| 6 | Pemantauan pergeseran data & umpan balik operator | Prasyarat penggunaan berkelanjutan |

## 6.6 Penutup

Nilai sebuah sistem peringatan dini tidak terletak pada ketepatan angkanya semata, melainkan pada
apakah ia memberi manusia cukup waktu untuk bertindak. Selisih antara "muatan sudah rusak" dan
"muatan aman 23 menit lagi" adalah selisih antara mencatat kerugian dan mencegahnya.

Kami membangun sistem ini dengan menjaga setiap angka yang tampil di layar dapat dijelaskan
asal-usulnya, dan setiap keterbatasan dinyatakan lebih dulu sebelum ditanyakan. Itu pula yang kami
anggap sebagai syarat sebuah sistem AI layak dipercaya untuk keputusan yang menyangkut keselamatan
pangan dan farmasi.
