# 5. Business Value

> **PERINGATAN — bagian ini belum boleh dikirim apa adanya.**
>
> Setiap angka berlabel `[ISI: ...]` di bawah ini **belum diisi dan tidak boleh dikarang.** Struktur
> dan penalarannya sudah disiapkan; yang dibutuhkan tinggal angka dari sumber yang dapat
> ditelusuri. Mengisi dengan tebakan adalah risiko terbesar bagian ini — juri di sesi tanya jawab
> hampir selalu menanyakan asal angka bisnis, dan angka yang tidak bisa dipertanggungjawabkan
> merusak kredibilitas seluruh proposal.
>
> Bila sebuah angka benar-benar tidak dapat ditemukan, **tulis sebagai asumsi secara eksplisit**
> ("kami mengasumsikan X, karena Y") — itu jauh lebih aman daripada menyajikannya seolah fakta.
>
> Pemilik bagian: R4 + R1.

## 5.1 Masalah yang bernilai uang

Kerugian rantai dingin bersifat **biner dan total**. Muatan yang melewati ambang suhu tidak menjadi
"agak rusak" — untuk vaksin, seluruh batch kehilangan jaminan potensi; untuk pangan, seluruh
muatan turun kelas atau dimusnahkan. Tidak ada nilai sisa yang sebanding.

Inilah yang membuat peringatan dini bernilai tinggi meski hanya datang beberapa puluh menit lebih
awal: selisih antara "muatan rusak" dan "muatan selamat" nyaris selalu ditentukan oleh apakah ada
seseorang yang sempat bertindak.

## 5.2 Perhitungan nilai — kerangka

| Komponen | Nilai | Sumber |
|---|---|---|
| Nilai rata-rata satu muatan berpendingin | `[ISI: Rp ...]` | `[sumber: ...]` |
| Frekuensi insiden eksursi suhu per armada per tahun | `[ISI: ... insiden]` | `[sumber: ...]` |
| Proporsi insiden yang dapat dicegah bila peringatan datang ≥ 20 menit lebih awal | `[ISI: ...%]` | `[asumsi + dasar]` |
| **Nilai kerugian yang dapat dihindari per tahun** | `[hitung]` | — |
| Biaya langganan ColdTrack AI per kendaraan per tahun | `[ISI: Rp ...]` | `[penetapan sendiri]` |
| **Titik impas** | `[hitung]` | — |

**Argumen inti yang ingin dibuktikan tabel ini:** satu insiden yang dicegah sudah menutup biaya
langganan untuk periode tertentu. Bila angka yang terisi nanti mendukung, kalimat ini menjadi
tulang punggung bagian Business Value — dan juga penutup Video Promosi.

Ketiga baris pertama harus punya sumber. Baris ketiga boleh berupa asumsi, tetapi **wajib
dinyatakan sebagai asumsi** beserta alasannya — misalnya dikaitkan dengan Time-to-Breach median
yang dihasilkan model kami pada skenario uji.

## 5.3 Kepada siapa nilai ini diberikan

| Segmen | Kebutuhan | Kenapa ColdTrack relevan |
|---|---|---|
| Distributor farmasi | Kepatuhan CDOB, keselamatan pasien | Nilai per muatan tinggi, konsekuensi kegagalan tidak hanya finansial |
| Logistik pangan segar | Marjin tipis, volume besar | Susut kecil pun berdampak besar pada marjin |
| Penyedia jasa logistik pihak ketiga | Ganti rugi ke pemilik barang | Bukti tindakan proaktif dapat memengaruhi posisi klaim |

Segmen mana yang dijadikan fokus utama perlu ditetapkan `[ISI: pilih satu]`. Menyasar ketiganya
sekaligus akan melemahkan argumen.

## 5.4 Mengapa pendekatan ini dapat dipertahankan

Tiga hal yang tidak dimiliki pemantauan suhu konvensional:

1. **Keluarannya waktu, bukan status.** "23 menit lagi" dapat langsung diterjemahkan menjadi
   keputusan; "suhu 9 °C" masih memerlukan penafsiran.
2. **Mengenali jenis kerusakan, bukan sekadar mendeteksi.** Tindakan untuk pintu yang terbuka
   berbeda dari kompresor yang melemah. Sistem yang hanya berbunyi "anomali" menyerahkan seluruh
   diagnosis kepada operator.
3. **Berjalan pada perangkat keras biasa.** Model puluhan ribu parameter memungkinkan penerapan
   tanpa GPU maupun langganan API model besar — komponen biaya yang biasanya menghambat adopsi di
   armada menengah.

## 5.5 Jalur menuju penerapan nyata

Kami tidak mengklaim sistem ini siap dipakai hari ini. Urutan yang realistis:

| Tahap | Isi | Prasyarat |
|---|---|---|
| 1 | Uji lapangan terbatas pada armada mitra | Perangkat telemetri terpasang, izin pemilik armada |
| 2 | Pelatihan ulang dengan telemetri nyata | Data lapangan terkumpul cukup |
| 3 | Integrasi ke sistem manajemen armada yang sudah dipakai | Kontrak API stabil |
| 4 | Pemantauan pergeseran data dan pelatihan ulang berkala | Basis data & pencatatan riwayat |

Tahap 2 adalah yang paling menentukan, karena di situlah kesenjangan sim-to-real yang kami akui di
Bagian 4.1 diuji terhadap kenyataan.

## 5.6 Yang belum dapat kami klaim

- **Belum ada validasi pada telemetri truk sungguhan.** Seluruh angka performa berasal dari data
  sintetik.
- **Belum ada uji coba dengan operator sebenarnya**, sehingga kami belum dapat mengklaim tindakan
  yang direkomendasikan benar-benar dapat dijalankan di lapangan dalam waktu yang tersedia.
- **Belum ada perhitungan biaya operasional penerapan** (perangkat, konektivitas, pemeliharaan)
  `[ISI bila memungkinkan]`.

Menyatakan ketiganya lebih dulu jauh lebih kuat daripada menunggu ditanya.
