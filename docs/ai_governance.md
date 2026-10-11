# AI Governance — ColdTrack AI

## Scope

Model AI pada ColdTrack AI **tidak mengambil keputusan akhir**. Ia menghasilkan tiga keluaran
numerik, dan sebuah mesin aturan deterministik yang menerjemahkannya menjadi status dan tindakan.

| Dikerjakan model AI | Dikerjakan mesin aturan |
|---|---|
| Prediksi suhu t+15/30/60 menit | Penetapan status AMAN / WASPADA / KRITIS |
| Klasifikasi mode kegagalan (7 kelas) | Pemilihan tiga langkah tindakan |
| Estimasi Time-to-Breach | Penerapan ambang keselamatan |

Pemisahan ini disengaja. Ambang keselamatan berada di `config.yaml` dan dapat ditinjau siapa pun
tanpa membaca bobot model, sehingga keputusan yang menyangkut keselamatan pangan dan farmasi tetap
dapat diaudit manusia.

Sistem ini adalah **alat bantu keputusan bagi operator armada**, bukan sistem kendali otomatis.
Tidak ada aktuator yang dikendalikan langsung oleh keluaran model.

## Human Oversight

**Manusia selalu menjadi pelaksana tindakan.** Keluaran sistem berhenti pada rekomendasi; tidak ada
langkah yang dieksekusi otomatis. Operator dapat mengabaikan seluruh rekomendasi tanpa hambatan
teknis apa pun.

**Sistem menolak menyatakan aman ketika alat ukurnya tidak dapat dipercaya.** Bila model
mendiagnosis sensor bermasalah, status dikunci di WASPADA — tidak boleh AMAN, dan tidak boleh
KRITIS. Angka Time-to-Breach ikut disembunyikan.

Alasannya berlaku dua arah. Menyatakan AMAN dari sensor yang diketahui rusak berarti memberi rasa
aman palsu. Sebaliknya, menaikkan ke KRITIS berarti mengklaim kepastian dari alat ukur yang sama —
pada skenario sensor macet, 60 pembacaan terakhir bernilai identik, sehingga estimasi apa pun yang
diturunkan darinya adalah ekstrapolasi dari sinyal mati. Yang benar adalah menyerahkan verifikasi
kepada manusia: *"alat ukur tidak dapat dipercaya, ukur manual."*

**Angka yang di luar jangkauan keandalan tidak ditampilkan.** Time-to-Breach hanya ditampilkan
sebagai angka bila di bawah 30 menit. Di atas itu sistem hanya menyebut ada risiko, tanpa angka.
Batasnya diturunkan dari pengukuran: MAE 3,30 menit untuk TTB ≤ 10 menit dan 7,08 menit untuk
≤ 30 menit, tetapi melonjak ke 52,00 menit bila seluruh rentang dihitung. Menampilkan angka di luar
rentang andal akan memberi kesan presisi yang tidak dimiliki sistem.

## Risk & Failure Modes

**False negative jauh lebih berbahaya daripada false positive.** Muatan yang dinyatakan aman
padahal sedang rusak berarti kerugian penuh dan — untuk vaksin — risiko produk tidak berkhasiat
sampai ke pasien. Sebaliknya, peringatan yang ternyata keliru hanya menimbulkan pemeriksaan yang
tidak perlu. Aturan **eskalasi** kami karena itu dirancang asimetris mengikuti ketimpangan ini:
lantai Time-to-Breach hanya boleh **menaikkan** keparahan, tidak pernah menurunkan.

Satu aturan sengaja dikecualikan dari prinsip itu. Pada diagnosis sensor bermasalah, status
**dijepit dua arah** ke WASPADA — tidak boleh AMAN, tetapi juga tidak boleh KRITIS. Alasannya
berbeda dari asimetri di atas: ketika alat ukurnya sendiri tidak dapat dipercaya, sistem tidak
boleh mengklaim ketelitian ke arah mana pun. Rinciannya di `docs/PROPOSAL.md` §4.3.4.

**Contoh nyata dari pengembangan kami.** Pada pengujian ujung-ke-ujung ditemukan bahwa status
dihitung semata dari prediksi suhu, sementara Time-to-Breach dihasilkan kepala model yang terpisah.
Keduanya bisa tidak sepakat — dan memang tidak sepakat: empat dari lima skenario demo
mengembalikan AMAN, termasuk skenario dengan Time-to-Breach 19 menit. Antarmuka menampilkan lampu
hijau tepat di sebelah tulisan "19 menit lagi sebelum ambang terlampaui", dan rekomendasinya
berbunyi "lanjutkan pemantauan rutin".

Perbaikannya menjadikan Time-to-Breach sebagai lantai status: bila di bawah 30 menit, status tidak
boleh AMAN. Kecocokan terhadap status yang diharapkan naik dari 1/5 menjadi 5/5.

Kami mencantumkan kejadian ini apa adanya karena inilah bentuk tata kelola yang bekerja —
ditemukan lewat pengujian, ditelusuri ke akarnya, diperbaiki dengan aturan yang dapat diaudit.

**Mode kegagalan yang kami sadari:**

| Risiko | Mitigasi saat ini |
|---|---|
| Sensor rusak menghasilkan pembacaan palsu | Status dikunci WASPADA, TTB disembunyikan |
| Keyakinan klasifikasi rendah pada kerusakan halus | Status tidak bergantung pada keyakinan; ditentukan TTB dan aturan |
| Model gagal dimuat | Sistem jatuh ke mesin aturan heuristik, versi model dilaporkan sebagai `coldtrack-rule-v1.0` |
| Data masukan terlalu pendek | Permintaan di bawah 60 bacaan ditolak, bukan dijawab dengan tebakan |

**Keterbatasan keyakinan model.** Dua dari tujuh kelas — degradasi bertahap dan masalah sensor —
memperoleh keyakinan jauh lebih rendah (35% dan 52%) dibanding kelas lain yang mencapai 100%.
Keduanya adalah kelas hasil penggabungan dua kelas asli, sehingga satu label harus menampung dua
pola berbeda. Keduanya juga memang sulit dibedakan dari kondisi normal: kenaikan 0,01 °C per menit
mirip fluktuasi wajar, dan pembacaan yang diam bisa berarti sensor rusak maupun pendingin yang
bekerja sangat baik. Kami melaporkannya apa adanya, dan tidak menjadikan keyakinan sebagai penentu
status.

**Batas label implisit (temuan latih ulang B3, Oktober 2026).** Label mode kegagalan bertahan dari
onset sampai akhir perjalanan, sedangkan pintu terbuka (A1) dan kejut ambien (A7) adalah peristiwa
sementara. Pengecekan data menunjukkan sebagian besar jendela berlabel A1/A7 jauh setelah onset
tidak memuat jejak peristiwanya (`bench/results/g16-gpu/B3/label_check.json`). Konsekuensinya bagi
pengguna: kelas mode kegagalan untuk peristiwa yang **sudah lewat** tidak dapat diandalkan, dan
skor klasifikasi agregat dibatasi oleh definisi label, bukan hanya oleh model. Mitigasi tetap sama:
status tidak ditentukan oleh keyakinan klasifikasi.

## Pembaruan Model dan Evaluasi

Penggantian model mengikuti gerbang yang dapat diaudit (`bench/README.md`, `bench/report/REPORT.md`):

1. **Reproduksi (G1)** model lama dengan 5 seed sebelum mencoba perbaikan.
2. **Paritas device (G2):** model yang dilatih di GPU harus setara kualitasnya dengan pelatihan di
   CPU; percepatan yang mengorbankan kualitas tidak dilaporkan sebagai percepatan.
3. **Seleksi di split validasi saja**, dengan objektif dan aturan adopsi yang didaftarkan sebelum
   pencarian hyperparameter dijalankan.
4. **Split test dipakai sekali per model** (G3), tercatat di `bench/results/test_access_log.json`
   beserta hash model; evaluasi ulang model yang sama ditolak oleh skrip.
5. Model baru diekspor ke jalur kandidat dulu; model produksi tidak ditimpa sebelum keputusan G3,
   dan peralihan backend dikerjakan terpisah dengan tes paritas ONNX.

Penggantian v2 → v3 (11 Oktober 2026) melalui seluruh langkah di atas
(`bench/results/keputusan/G1.json`, `G3.json`, `bench/results/G2.json`). G3 **disetujui dengan
catatan**; v3 menjadi diagnosis provider bawaan backend, menggantikan checkpoint-2.

**Pernyataan jujur tentang target.** v3 **tidak** mencapai target PRD klasifikasi: Macro F1 test
0,668 (target > 0,80), PR-AUC test 0,786 (target > 0,85). Batas utamanya terukur pada definisi label:
58 % jendela A1 dan 51 % jendela A7 tidak memuat jejak kejadiannya. Definisi metrik dan target tidak
diubah; peninjauan definisi label diserahkan ke tim data/PRD.

**Rollback.** Satu flag `model.diagnosis_provider` di `backend/config.yaml` (`v3` | `checkpoint2`);
checkpoint-2 tidak dihapus dan tetap diuji di CI. Setiap respons memuat `diagnosis_provider` dan
`model_version` sehingga perilaku dapat dilacak dari log.

**Keterbatasan perbandingan v3 vs checkpoint-2.** Diuji di data v4 yang asing bagi checkpoint-2; v3
dituning di split val yang sama; definisi label pintu checkpoint-2 berbeda (>= 20 menit); uji di
`ml/dataset_v3.parquet` belum dapat dijalankan karena berkas tidak ada di repo
(`docs/model_card.md`, bagian v3 di backend).

**Latensi.** v3 0,21 → 1,38 ms per panggilan (CPU, batch 1), jauh di bawah anggaran 300 ms.

**Data tidak lengkap.** Diagnosis model pada jendela dengan bacaan hilang berada di luar distribusi
latih. Sistem menandainya (`data_lengkap: false`, keyakinan dibatasi 0,5) dan antarmuka menampilkan
"Diagnosis kurang andal (data tidak lengkap)"; status dari mesin fisika tidak terpengaruh.

## Monitoring

**Yang dipantau saat ini** sebatas yang dapat dilakukan tanpa basis data, sesuai batasan MVP:
setiap respons menyertakan versi model, waktu inferensi, dan indeks risiko, sehingga penyimpangan
perilaku dapat dilacak dari log permintaan.

**Yang belum ada dan kami akui.** Tidak ada pemantauan pergeseran distribusi data (*data drift*),
tidak ada mekanisme umpan balik dari operator untuk mengoreksi diagnosis yang salah, dan tidak ada
pencatatan riwayat prediksi. Ketiganya memerlukan basis data, yang sengaja tidak dipakai pada
tahap ini.

**Rencana bila dilanjutkan ke tahap berikutnya:** pencatatan setiap prediksi beserta hasil
sebenarnya, peninjauan berkala terhadap kasus berkeyakinan rendah, pemantauan pergeseran
distribusi fitur masukan, dan pelatihan ulang berkala menggunakan data lapangan.

## Compliance & Fairness Notes

**Rujukan standar.** Ambang suhu tiap profil kargo mengacu pada standar yang dapat ditelusuri —
BPOM No. 6/2020 tentang CDOB dan pedoman WHO untuk vaksin, Codex Alimentarius serta FAO/USDA untuk
daging beku, SNI 01-2696.3-2006 untuk ikan segar, dan pedoman HACCP untuk produk susu serta sayur
dan buah. Rinciannya ada pada Bagian 4.1.

**Batas yang kami tetapkan sendiri, bukan dari regulasi.** Durasi toleransi eksursi suhu tidak
diatur sebagai angka tunggal dalam regulasi mana pun; nilainya bergantung pada produk, formulasi,
dan riwayat suhu sebelumnya. Nilai yang kami pakai adalah asumsi desain simulasi yang konservatif,
semata untuk menghasilkan label pelatihan — bukan pernyataan ambang resmi suatu produk.

**Sistem ini bukan alat pemenuhan regulasi.** ColdTrack AI tidak menerbitkan sertifikat kepatuhan,
tidak menggantikan pencatatan suhu resmi yang diwajibkan CDOB, dan tidak dapat dijadikan dasar
tunggal untuk menyatakan suatu muatan layak atau tidak layak edar. Keputusan tersebut tetap berada
pada penanggung jawab mutu.

**Fairness.** Sistem ini menilai kondisi kargo dan kendaraan, bukan orang. Tidak ada data pribadi
pengemudi yang diproses, dan tidak ada keluaran yang menilai kinerja individu. Data perilaku
mengemudi dari UAH-DriveSet dipakai hanya sebagai referensi statistik agregat saat merancang
simulator, tidak masuk ke sistem yang berjalan.

**Kesenjangan sim-to-real.** Model dilatih pada data sintetik dan belum pernah diuji pada telemetri
truk yang sebenarnya. Uji lapangan sebelum penggunaan nyata adalah prasyarat, bukan pilihan.
