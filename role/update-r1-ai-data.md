# Update Tugas R1 — AI Data Engineer

**Per 13 Agustus 2026** · Deadline internal tim: **24 Agustus** — sisa **11 hari**
Disusun R2 berdasarkan audit repositori terhadap `role/context-r1-ai-data.md`.

---

## Yang sudah selesai

| Artefak | Status |
|---|---|
| `ml/simulator/` — simulator termal, 9 mode anomali A0–A8 | selesai |
| `data/processed/` — dataset v1 sampai v4 | selesai |
| `docs/dataset_card.md` — 255 baris, 7 dataset publik + verifikasi standar | selesai |
| `docs/feature_schema.md` — kontrak 12 kolom | selesai |
| `ml/tests/test_data_contract.py` — 7 tes, semua lolos | selesai |
| Perbaikan 3 bug pelabelan (v2 → v4) | selesai |

Kualitas kerjanya baik. Verifikasi `cargo_profiles` terhadap standar resmi (WHO, BPOM No. 6/2020,
Codex Alimentarius, SNI) melampaui yang diminta, dan pengakuan jujur bahwa `massa_kg` serta
`toleransi_menit` bukan kutipan standar adalah nilai tambah untuk penilaian.

---

## Mendesak — permintaan baru dari hasil uji integrasi

### Skenario demo perlu minimal 60 bacaan

Backend kini menolak permintaan berisi kurang dari 60 bacaan, karena model menghitung statistik
ringkasan (simpangan baku, tren) di dalam dirinya — jendela yang di-*pad* menghasilkan nilai yang
salah, dan model tidak pernah dilatih pada bentuk seperti itu.

Kondisi saat ini, kelima skenario demo **tidak memenuhi syarat**:

| Sumber | Jumlah bacaan | Syarat |
|---|---|---|
| `backend/data/scenarios/*.json` | 3–5 | ≥ 60 |
| Skenario di frontend (`N = 31`) | 31 | ≥ 60 |

Artinya **demo akan gagal total** begitu frontend dialihkan dari data tiruan ke API sungguhan.

Kamu pemilik simulator, jadi paling tepat menyediakan penggantinya. Yang dibutuhkan: **5 berkas
skenario, masing-masing minimal 60 bacaan berturut-turut per menit**, sesuai lima skenario di
`context-r4` baris 87–91:

1. Sehat — perjalanan normal
2. Pintu terbuka terlalu lama (A1)
3. Kompresor melemah (A2) — **paling penting**, ini demo utama
4. Sensor macet (A5)
5. Kejut suhu ambien saat macet (A7)

Formatnya harus mengikuti skema backend (`backend/app/schemas.py`, kelas `TelemetryReading`):

```json
{
  "ts": "2026-08-20T07:00:00+07:00",
  "temp_c": 4.2, "humidity": 71.5, "ambient_c": 31.4,
  "door_open": false, "reefer_on": true,
  "lat": -6.2118, "lon": 106.8456,
  "speed_kmh": 24.0, "harsh_events": 0, "solar_radiation": 350.0
}
```

Datanya sudah ada di `data/processed/v4_seed1000_700trips.parquet` — tinggal memilih trip dengan
mode anomali yang sesuai, mengambil 60–150 menit berturut-turut, dan mengekspornya ke JSON.

**Saran khusus skenario 3:** pilih potongan di mana `time_to_breach` bernilai **di bawah 30 menit**
pada menit terakhir jendela. Di rentang itu model paling akurat (MAE 7,6 menit; di bawah 10 menit
bahkan 3,5 menit), sehingga angka Time-to-Breach yang tampil di demo dapat dipertanggungjawabkan.

---

## Yang masih kurang

### 1. Proposal §4.1 Alur Dataset — belum ditulis (paling mendesak)

Tenggat menurut jadwal R4 adalah **14 Agustus — besok**.

Bahannya **sudah lengkap** di `dataset_card.md` dan `ml/simulator/README.md`; tinggal disusun ulang
menjadi narasi. Kerangka yang disarankan:

1. **Mengapa data sintetik** — tidak ada dataset publik berisi telemetri truk berpendingin Indonesia
   dengan label mode kegagalan, terutama label Time-to-Breach yang bersifat kontrafaktual
2. **Sumber data publik** — 7 dataset, peran masing-masing, lisensinya
3. **Simulator termal** — persamaan pendinginan Newton, kalibrasi, katalog 9 mode anomali
4. **Verifikasi terhadap standar resmi** — koreksi tiga nilai `cargo_profiles`, dan pengakuan jujur
   soal `massa_kg` dan `toleransi_menit`
5. **Validasi sim-to-real** — hasil uji KS dan ACF, termasuk pengakuan bahwa data sintetik lebih
   stabil daripada data nyata beserta penjelasannya
6. **Keterbatasan** — belum divalidasi terhadap perjalanan truk sungguhan

Contoh format dapat dilihat pada `docs/proposal_4_2_alur_pengembangan_model.md`.

### 2. Grafik validasi sim-to-real — belum ada

Angkanya sudah ada di `dataset_card.md` (KS statistic 1,0000; ACF lag 1/10/30/60), tetapi
**Gambar 4.1** yang disebut di timeline Sprint 1 belum pernah dibuat.

Yang perlu digambar:

- Perbandingan kurva ACF data sintetik vs data IoT publik, lag 1–60
- Perbandingan distribusi suhu dan laju perubahan suhu

Simpan sebagai `ml/reports/sim_to_real_acf.png` dan `ml/reports/sim_to_real_distribusi.png`.
Dipakai di §4.1 dan video PoW segmen "Pabrik data" (menit 1:20–2:30).

### 3. `docs/ai_governance.md` — masih kerangka kosong

16 baris, isinya hanya komentar HTML. Tanggung jawab bersama R4 (`context-r1` baris 32).

Sebagian bahan sudah tersedia di `docs/model_card.md` bagian "Limitations & Ethical
Considerations" — silakan dirujuk atau disalin seperlunya, khususnya soal risiko false negative
yang lebih berat daripada false positive.

### 4. Notebook `01_eda.ipynb` — belum ada

Artefak wajib di `context-r1` baris 151. Temuan EDA sudah tertulis rapi di `dataset_card.md`,
tetapi notebooknya sendiri tidak ada.

---

## Catatan teknis kecil

**Berkas `.pyc` ikut ter-commit.** `ml/tests/test_data_contract.cpython-312-pytest-9.1.1.pyc` ada di
`main`. Hapus dengan `git rm --cached`.

**Split test tidak seimbang untuk TTB.** Split `test` hanya memuat 10,6% jendela breach, `val`
memuat 22,6%, dengan median TTB 63 vs 10 menit. Sudah distratifikasi per `failure_mode`, tetapi
tidak per kejadian breach. **Tidak mendesak** — R2 sudah menyesuaikan pelaporannya. Cukup dicatat
sebagai keterbatasan bila tidak sempat diperbaiki.

---

## Urutan prioritas

1. **Skenario demo ≥ 60 bacaan** — memblokir demo end-to-end seluruh tim
2. **Proposal §4.1** — tenggat besok, bahannya sudah siap
3. **Grafik sim-to-real** — dibutuhkan §4.1 dan video PoW
4. **`ai_governance.md`** bersama R4
5. `01_eda.ipynb` dan hapus berkas `.pyc`
