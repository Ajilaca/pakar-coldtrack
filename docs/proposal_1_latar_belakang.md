# 1. Judul, Latar Belakang, Tujuan & Manfaat

> **Catatan untuk R4 sebagai pemilik bagian ini:** angka pada Latar Belakang diambil dari dokumen
> konteks tim. Sebelum dikirim, setiap angka perlu dilengkapi sitasi sumber primer (BPS, Kemenhub,
> Bappenas, FAO) — panitia lomba umumnya menilai ketertelusuran data. Tempat sitasi sudah ditandai
> dengan `[sumber: ...]`.

## Judul

**ColdTrack AI — Peringatan Dini Kegagalan Rantai Dingin Berbasis Telemetri**

## 1.1 Latar Belakang

Biaya logistik Indonesia setara **14,29% dari Produk Domestik Bruto** `[sumber: ...]`. Pemerintah
menargetkan angka itu turun ke **8% pada 2045** `[sumber: ...]`. Selisih enam poin persen tersebut
bukan sekadar angka statistik — ia mewakili biaya yang pada akhirnya ditanggung konsumen melalui
harga barang.

Sebagian dari biaya itu hilang sebagai barang yang rusak sebelum sampai. Indonesia kehilangan
**23–48 juta ton pangan per tahun** melalui *food loss and waste* `[sumber: ...]`, dan rantai
dingin yang buruk adalah salah satu penyumbangnya. Kerugiannya tidak berhenti pada pangan: vaksin
yang keluar dari rentang 2–8 °C kehilangan potensi dan tidak lagi memberi perlindungan kepada
pasien yang menerimanya.

**Akar masalahnya bukan ketiadaan sensor, melainkan sifat pemantauannya yang pasif.** Banyak
kendaraan berpendingin sudah memasang sensor suhu. Tetapi data itu umumnya hanya dicatat, lalu
dibaca ketika muatan sudah sampai — atau ketika alarm berbunyi karena ambang sudah terlampaui.
Pada titik itu keputusan yang tersisa tinggal satu: menerima kerugian.

Yang hilang adalah **waktu untuk bertindak**. Kompresor yang melemah secara bertahap tidak memicu
alarm apa pun sampai suhu benar-benar melewati batas, padahal kenaikannya sudah terbaca sejak
puluhan menit sebelumnya — terlalu halus untuk disadari manusia yang membaca angka, tetapi cukup
jelas bagi model yang mempelajari polanya.

Pergeseran yang kami tawarkan sederhana namun menentukan:

| Pemantauan pasif hari ini | ColdTrack AI |
|---|---|
| "Suhu muatan 9 °C" | "Muatan aman 23 menit lagi" |
| "Ambang terlampaui" | "Kompresor melemah, keyakinan 87%" |
| — | "Tiga hal yang harus dilakukan sekarang" |

## 1.2 Tujuan

1. **Mengubah telemetri pasif menjadi keputusan yang dapat ditindaklanjuti**, dengan keluaran
   utama berupa Time-to-Breach — jumlah menit tersisa sebelum muatan melewati ambang suhunya.
2. **Mengenali jenis kerusakan, bukan sekadar mendeteksi anomali**, sehingga tindakan yang
   disarankan sesuai penyebabnya: pintu yang terbuka ditangani berbeda dari kompresor yang melemah.
3. **Menjelaskan dasar setiap kesimpulan**, agar operator dapat menilai sendiri apakah peringatan
   itu masuk akal, bukan sekadar mempercayainya.
4. **Berjalan pada perangkat keras biasa.** Model dirancang ringan — puluhan ribu parameter, bukan
   jutaan — sehingga inferensi berjalan cepat tanpa GPU.

## 1.3 Manfaat

**Bagi operator armada.** Satu insiden yang dicegah menyelamatkan nilai satu muatan penuh.
Peringatan yang datang puluhan menit lebih awal mengubah pilihan yang tersedia: dari sekadar
mencatat kerugian, menjadi menepi ke tempat teduh, memeriksa kondensor, atau menyiapkan pemindahan
muatan.

**Bagi penerima dan konsumen akhir.** Vaksin yang sampai dalam kondisi berkhasiat, dan pangan yang
sampai dalam kondisi layak. Untuk produk farmasi, ini menyangkut keselamatan pasien, bukan sekadar
nilai barang.

**Bagi ekosistem logistik nasional.** Susut yang lebih rendah berarti biaya logistik yang lebih
rendah — kontribusi langsung, meski kecil, terhadap target 8% pada 2045.

**Bagi pengembangan berikutnya.** Seluruh pipeline data, model, dan antarmuka dibangun modular
dengan kontrak API yang terdokumentasi, sehingga dapat dikembangkan menjadi sistem produksi tanpa
membangun ulang dari awal.

## 1.4 Batasan yang kami tetapkan sejak awal

Kami menetapkan batasan lingkup di awal pengembangan dan mempertahankannya sampai akhir:

| Aspek | Batasan |
|---|---|
| Antarmuka | Satu alur interaksi inti — satu masukan, satu keluaran AI. Tanpa dasbor analitik lintas armada, tanpa otentikasi |
| Backend | Pemrosesan sinkron. Tanpa basis data, tanpa antrean latar belakang |
| Model | Wajib ditala pada domain rantai dingin, parameter statis saat demonstrasi |
| Data | Sintetik dari simulator fisika, karena label kebenaran kegagalan rantai dingin tidak tersedia publik |

Batasan ini bukan kekurangan yang disembunyikan, melainkan keputusan sadar agar satu alur bernilai
dapat diselesaikan dengan baik dalam waktu yang tersedia — dan agar setiap angka yang tampil di
layar dapat dijelaskan asal-usulnya.
