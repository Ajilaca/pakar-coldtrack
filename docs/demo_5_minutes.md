# Demo ColdTrack AI: alur 5 menit

Panduan untuk presenter: apa yang disiapkan, apa yang diklik, dan apa yang diucapkan. Aplikasi berjalan
lokal dengan Docker (lihat [demo.md](demo.md) untuk detail teknis). Semua data adalah **sintetis** dari
simulator; angka rupiah adalah **estimasi berbasis asumsi**.

## Ringkasan alur

| Menit | Bagian | Halaman | Tujuan |
|---|---|---|---|
| 0:00–0:30 | Pembuka | Ringkasan | Masalah dan gambaran armada |
| 0:30–1:30 | Satu truk bermasalah | Detail truk | Prediksi dini, diagnosis, faktor, tindakan |
| 1:30–2:15 | Dari peringatan ke tindakan | Notifikasi, Tindakan | Alur operator dan audit trail |
| 2:15–3:00 | Dampak uang | Kerugian | Nilai berisiko dan cara menghitungnya |
| 3:00–3:30 | Sensor dan lokasi | Sensor, Lokasi | Kesehatan perangkat, peta Jawa |
| 3:30–4:30 | Uji skenario langsung | Simulasi | Hasil yang pasti tampil: pintu terbuka → KRITIS |
| 4:30–5:00 | Penutup yang jujur | Ringkasan | Batasan dan langkah berikutnya |

Waktu ketat. Kalau telat, buang bagian 3:00–3:30 (Sensor dan Lokasi) lebih dulu.

---

## A. Persiapan (mulai 30 menit sebelum tampil)

**1. Nyalakan Docker Desktop** dan tunggu sampai mesinnya siap. Per 17 Okt 2026 mesin Docker belum jalan
(setelah laptop dimatikan), jadi ini tidak boleh dilewatkan. Pastikan tidak ada server lain di port 3000,
8000, 5432, 1883.

**2. Reset data lalu nyalakan stack.** Data menumpuk selama stack menyala (notifikasi, insiden, kerugian),
jadi reset supaya angkanya wajar. Jalankan dari folder repo:

```bash
docker compose --profile dev down -v
```

```bash
docker compose --profile dev up -d
```

Tambahkan `--build` hanya kalau kode berubah sejak build terakhir (build pertama butuh beberapa menit).

**3. Cek semua kontainer sehat.** Harus ada 7 kontainer: db, mqtt, api (namanya `coldtrack-backend`),
worker-ingest, worker-infer, frontend, virtual-trucks.

```bash
docker compose --profile dev ps
```

**4. Beri waktu data terkumpul, sebaiknya 15 menit atau lebih.** Dua menit pertama semua truk berstatus
MENUNGGU DATA karena model butuh 60 menit data trip simulasi (1 menit simulasi = 2 detik nyata). Setelah
itu status baru terisi, dan insiden serta notifikasi bertambah seiring waktu. Truk KRITIS tidak dijamin
ada pada saat kamu tampil karena trip yang diputar acak; itulah gunanya bagian Simulasi sebagai jaminan.

**5. Cek ringkasan armada.** Lihat bagian `per_status`: idealnya ada truk WASPADA atau KRITIS.

PowerShell (di PowerShell `curl` adalah alias `Invoke-WebRequest`, jadi pakai salah satu ini):

```powershell
(Invoke-RestMethod http://localhost:8000/api/v1/fleet/summary).per_status
```

Git Bash / WSL:

```bash
curl -s http://localhost:8000/api/v1/fleet/summary
```

**6. Siapkan browser.**
- Buka `http://localhost:3000`, mode layar penuh, zoom 100–110 %.
- Buka halaman **Tindakan**, isi **nama operator** (mis. nama kamu). Nama disimpan di browser, jadi saat
  demo tinggal klik. Tanpa nama, tombol tindakan menolak dan menulis "Isi nama operator dulu".
- Matikan notifikasi sistem (Windows: Fokus / jangan ganggu), tutup tab lain.
- Catat nama/plat **satu truk KRITIS atau WASPADA** dari tabel "Armada diurutkan menurut risiko" di
  Ringkasan. Status truk bisa berubah, jadi pilih ulang saat tampil bila perlu.

**7. Gladi satu kali.** Buka **Simulasi**, pilih "Pintu Kargo Terbuka Terlalu Lama", klik "Analisis
perjalanan". Pada uji API 16 Okt 2026 hasilnya KRITIS, time-to-breach 21,1 menit, diagnosis
`pintu_terbuka_lama` (keyakinan 0,957). Pastikan tampilan hari ini sama; angka yang kamu ucapkan harus
angka yang tampil di layar, bukan dari catatan ini.

**8. Rencana cadangan.** Rekam layar satu kali jalan penuh sebagai video cadangan. GIF demo singkat juga
ada di `docs/images/demo.gif`. Kalau Docker bermasalah dan hanya Simulasi yang bisa jalan (backend dan
frontend tanpa database), lakukan bagian 3:30–4:30 saja dan ceritakan sisanya dengan tangkapan layar.

---

## B. Skrip demo

Teks miring adalah yang diucapkan. "Klik" adalah aksi di layar.

### 0:00–0:30 · Pembuka (Ringkasan)

Buka **Ringkasan**.

> *"Rantai dingin gagal diam-diam: pintu terbuka terlalu lama, kompresor melemah, dan baru ketahuan
> setelah muatan rusak. ColdTrack AI memantau armada dan memberi tahu truk mana yang akan melewati batas
> suhu, kapan, dan kenapa. Ini 24 truk virtual yang sedang berjalan. Datanya sintetis dari simulator,
> bukan logger truk nyata."*

Tunjuk: kartu KPI (kritis, waspada, kerugian berisiko), "Truk per diagnosis", peta mini.

### 0:30–1:30 · Satu truk bermasalah (Detail truk)

Klik truk **KRITIS** (atau WASPADA bila tidak ada) di tabel risiko, lalu **Detail truk →**.

> *"Setiap truk punya status AMAN, WASPADA, atau KRITIS. Yang menentukan status adalah mesin aturan fisika
> yang bisa dijelaskan, bukan kotak hitam. Model GRU bertugas mendiagnosis jenis masalahnya: di sini
> [sebutkan diagnosis di layar] dengan keyakinan [angka di layar]."*

> *"Grafik ini suhu aktual dan prediksi 15, 30, 60 menit ke depan. Time-to-breach [angka di layar]
> artinya perkiraan waktu sebelum suhu muatan melewati batas. Di bawahnya ada faktor pendorong dan tiga
> langkah tindakan yang disarankan."*

### 1:30–2:15 · Dari peringatan ke tindakan (Notifikasi, Tindakan)

Klik lonceng notifikasi (tunjuk kotak masuk; toast kanan bawah muncul sendiri bila ada truk yang
memburuk). Lalu buka **Tindakan**: pada satu insiden klik **Tugaskan → Mulai tangani → Tandai selesai**.

> *"Peringatan tidak berhenti di layar. Operator menugaskan, menangani, lalu menandai selesai, dan setiap
> langkah tercatat di audit trail dengan nama pelakunya."*

### 2:15–3:00 · Dampak uang (Kerugian)

Buka **Kerugian**. Tunjuk "Nilai berisiko", "Kerugian terjadi", "Berhasil diatasi", lalu kartu "Cara
menghitung".

> *"Ini estimasi, bukan kerugian tercatat. Nilai berisiko adalah nilai muatan dikali risk index untuk
> insiden yang masih terbuka. Harga per kilogram kami tandai sebagai asumsi."*

### 3:00–3:30 · Sensor dan Lokasi (opsional, buang bila telat)

Buka **Sensor**, lalu **Lokasi**.

> *"Kesehatan sensor dinilai per truk dengan bobot desain yang belum dikalibrasi. Di peta, truk dan depo
> diwarnai sesuai status."*

### 3:30–4:30 · Uji skenario langsung (Simulasi)

Buka **Simulasi**, pilih **Pintu Kargo Terbuka Terlalu Lama**, klik **Analisis perjalanan**.

> *"Halaman ini menguji skenario tanpa mengubah data armada. Skenario ini: pintu kargo terbuka terlalu
> lama saat bongkar muat, muatan daging beku. Hasilnya KRITIS, time-to-breach [angka di layar],
> diagnosis pintu terbuka lama dengan keyakinan [angka di layar], dan tindakan pertamanya adalah
> menutup dan mengunci pintu."*

Opsional kalau waktu tersisa: pilih "Kompresor Melemah Bertahap" lalu analisis ulang. Status yang
diharapkan skenario itu KRITIS, tetapi **belum diperiksa lewat UI**; cek saat gladi sebelum dipakai di
depan penonton.

### 4:30–5:00 · Penutup yang jujur

Kembali ke **Ringkasan**.

> *"Tiga hal yang perlu jujur kami sampaikan. Pertama, data masih sintetis; belum ada uji lapangan.
> Kedua, alarm pada truk normal cukup sering, sekitar 20 % menit perjalanan normal, terutama muatan
> 2–4 °C. Ketiga, target akurasi PRD baru tercapai setelah definisi label pintu dan kejut ambien
> diperbaiki: pada test, Macro F1 0,820 dan PR-AUC 0,855; dengan label lama 0,756 dan 0,812. Degradasi
> bertahap masih lemah. Langkah berikutnya: uji dengan data logger nyata dari pilot."*

---

## C. Siap-siap pertanyaan

| Pertanyaan | Jawaban singkat (bersumber dari berkas di repo) |
|---|---|
| Seakurat apa modelnya? | GRU v5, test: Macro F1 0,820, PR-AUC 0,855 (label v5); 0,756 dan 0,812 dengan label lama (v3: 0,668 dan 0,786). `bench/results/test/b8_gru_v5_context.json`, `docs/model_card.md`. |
| Kenapa label diubah? | Di v3, 58,4 % jendela pintu terbuka dan 50,5 % lonjakan ambien tidak memuat jejak kejadian karena label bertahan sampai akhir trip. Label v5 menganggap keduanya kejadian sementara, lalu model dilatih ulang dengan konteks trip. Kedua angka tetap kami laporkan. |
| Apakah data nyata? | Tidak. Sintetis dari simulator; model Berkeley (data sensor nyata) tidak lolos evaluasi (G4). |
| Latensi? | Model v3, CPU, batch 1: p50 1,474 ms per panggilan, jauh di bawah anggaran PRD 300 ms. (`docs/model_card.md` masih menulis 1,38 ms; angka terukur ada di `candidate_latency.json`.) |
| Perlu GPU? | Untuk inferensi per truk di CPU tidak perlu: GPU batch 1 justru lebih lambat (0,04×). GPU membantu untuk pelatihan dan batch besar. Detail: bagian 4 `BAHAN_PPT_TEKNIS.md`. |
| Bisa pakai di truk nyata? | Belum. Butuh pilot dengan logger sungguhan untuk kalibrasi ambang, bobot sensor, dan harga per kg. |

## D. Hal yang jangan dilakukan di panggung

- Jangan menyebut target PRD "tercapai".
- Jangan menyebut rupiah sebagai kerugian nyata.
- Jangan membuka log Docker atau terminal di depan penonton.
- Jangan menyebut angka di layar tanpa melihat layarnya; truk dan angka berubah tiap detik.
- Kalau sidebar menulis "Memuat ulang tiap 30 detik", koneksi SSE putus (dasbor jatuh ke polling): cek
  `docker compose --profile dev logs api` setelah demo, bukan saat tampil.

## E. Setelah demo

```bash
docker compose --profile dev stop
```

(`stop` menyimpan data; `down -v` menghapus semuanya. Lakukan `down -v` lagi sebelum demo berikutnya.)
