"""W5 -- skala data simulator. TIDAK DIJALANKAN (dicatat, bukan dikosongkan diam-diam).

Rencana mensyaratkan regenerasi data dengan simulator yang dapat direproduksi dan label v4 yang sama.
Simulator v4 berada di notebook ml/simulator/02_simulator_fixed_v4.ipynb (v1/v3 lalu perbaikan
label -> v4) dan membutuhkan data/raw/iot_temp/IOT-temp.csv dari Kaggle yang tidak ada di repo;
ml/coldtrack_sim.py adalah simulator garis checkpoint-2 (kejadian A1-A3), bukan v4. Menjalankan W5
dengan simulator lain akan mengubah label, yang dilarang rencana.
"""

from bench.harness import tidak_berlaku

ALASAN = (
    "simulator v4 tidak dapat direproduksi dari repo: notebook ml/simulator/02_simulator_fixed_v4.ipynb "
    "butuh IOT-temp.csv (Kaggle) yang tidak ada; ml/coldtrack_sim.py adalah garis checkpoint-2 dengan label "
    "berbeda. Butuh keputusan user (sediakan data + porting generator) sebelum dijalankan."
)


def run(ctx):
    return tidak_berlaku(ctx, "W5", "skala_3000_trip", {"target_trip": 3000, "label": "v4"}, ALASAN)
