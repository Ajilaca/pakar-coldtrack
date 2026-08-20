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
tidak perlu. Seluruh aturan eskalasi kami dirancang asimetris mengikuti ketimpangan ini: aturan
hanya boleh **menaikkan** keparahan, tidak pernah menurunkan.

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
