# Suite evaluasi ColdTrack AI

Menilai sistem **sebagaimana di-deploy** (`backend/app/inference.py`: mesin fisika dan aturan,
`coldtrack_gru.onnx`, `coldtrack_ttb.onnx`, dan API HTTP) pada split test dataset v4 yang disisihkan (dibagi per
`trip_id`). Trip dan jendelanya sama dengan yang dipakai untuk menilai baseline.

```bash
pip install -r backend/requirements.txt
python -m eval.run_eval --tag iter1              # ~4 menit -> eval/results/iter1_results.json
pytest eval/test_baseline.py -q                  # 19 cek penerimaan (yang gagal = kelemahan yang terdokumentasi)
python -m eval.make_artifact --tag iter1         # -> eval/results/Evaluation_Artifact_Iteration.pdf (sebelum/sesudah)
```

Iterasi 2 (perubahan aturan mesin) menambah set test kedua, yaitu trip test dari simulator baru
(`ml/dataset_v3.parquet`, tidak ada di git), dan sapuan margin peringatan mendekati batas:

```bash
python -m eval.run_eval --tag iter2                  # hasil v4
python -m eval.run_eval --tag iter2 --margin-sweep   # -> results/margin_sweep_iter2.json
python -m eval.sim_check --tag iter2                 # -> results/sim_v3_iter2.json (split test dataset_v3)
python -m eval.make_artifact --iteration 2           # -> results/Evaluation_Artifact_Iteration_2.pdf
```

`sim_v3_iter1.json` dibuat dengan cara yang sama, memakai mesin pada commit `ff9aacd`.

Kontrak `hybrid-v3` (yang berlaku): 3 kejadian independen (pintu terbuka lama, kejut ambien, gangguan sensor),
forecast suhu muatan, serta status dan TTB dari mesin. Mode kegagalan v4 dipetakan ke kejadian sebagai berikut:
A1 → pintu, A7 → kejut, A5/A6 → sensor. A2/A3/A4/A8 tidak punya kejadian, jadi dinilai lewat status dan TTB saja.
v4 tidak memuat massa muatan, sehingga dipakai `mass_kg_default` dari profil muatan, sama seperti di produksi.

Model dilatih dengan simulator fisikanya sendiri, bukan dengan v4. Bagi model ini v4 adalah test di luar
distribusi (baseline dilatih dengan v4).

`baseline` (kontrak 7 kelas lama) tidak bisa dijalankan ulang karena modelnya sudah dihapus. Hasil dan status
ceknya diarsipkan di `results/baseline_results.json` dan `results/Evaluation_Artifact_baseline.pdf`.

| Berkas | Fungsi |
|---|---|
| `common.py` | Memuat trip test, menyusun bacaan, menilai per trip lewat `inference_engine.analyze_trip` |
| `run_eval.py` | G1 forecast · G2 kejadian · G3 breach yang segera terjadi · G4 ketahanan · G5 API ujung ke ujung (plus kesamaan dengan G1–G3) |
| `test_baseline.py` | Ambang penerimaan (memakai ambang baseline bila metriknya masih berlaku), satu kondisi gagal per cek |
| `sim_check.py` | Cek regresi per trip pada trip test simulator baru (mencegah penyetelan yang hanya cocok untuk v4) |
| `make_artifact.py` | Membuat `Evaluation_Artifact_Iteration.pdf` (`--tag iter1`) dan `Evaluation_Artifact_Iteration_2.pdf` (`--iteration 2`) |
| `results/` | Hasil JSON, gambar, PDF |

## Cek yang sama pada data simulator baru (dalam distribusi)

`run_eval --data` menjalankan 19 cek yang sama, dengan ambang yang sama, pada parquet simulator baru
(`ml/dataset_v3.parquet`, tidak ada di git, ~80 MB). Split test-nya `prep_windows.split_trips` seed 0, yaitu trip
yang sama dengan yang dipakai `eval/sim_check.py`. Pemetaan dan pengecualian ada di `eval/new_sim_data.py`.

```bash
python -m eval.run_eval --data ml/dataset_v3.parquet --tag sim_iter2   # ~2-4 menit
EVAL_TAG=sim_iter2 pytest eval/test_baseline.py -q
```

Laporkan hasilnya berdampingan dengan run v4. Bagi model baru, v4 berada di luar distribusi (model dilatih dengan
simulatornya sendiri), sedangkan run simulator baru berada di dalam distribusi. Dua hal di data ini sudah pasti
dari cara datanya dibuat: tidak ada trip vaksin (cek "setiap profil muatan" gagal), dan trip daging segar (0–4 °C)
dikecualikan karena backend tidak punya profilnya.
