"""Tes kontrak data — gerbang pertama sebelum data masuk pipeline model R2.

Menjalankan: python ml/tests/test_data_contract.py
Atau:        python -m pytest ml/tests/test_data_contract.py -v
"""

import pandas as pd

DATA_PATH = "data/processed/v1_seed1000_700trips_ttbfix.parquet"

# 12 kolom fitur sesuai docs/feature_schema.md baris 15-26, urut sesuai nomor
FEATURE_COLUMNS = [
    'temp_c', 'delta_temp', 'ambient_c', 'delta_ambient', 'solar_radiation',
    'humidity', 'door_open', 'reefer_on', 'reefer_duration_min', 'speed_kmh',
    'harsh_events', 'hour_of_day',
]

# Kolom terlarang sesuai docs/feature_schema.md baris 45-47.
# Catatan: schema juga melarang "nilai suhu masa depan dalam bentuk apa pun" (baris 48) —
# ini bukan nama kolom tetap, jadi tidak masuk list ini, tapi wajib diingat saat nanti
# membuat sliding window untuk head-1 (forecast): jangan sampai t+15/t+30/t+60 ikut jadi fitur X.
FORBIDDEN_COLUMNS = ['is_anomaly', 'failure_mode', 'time_to_breach']


def test_all_feature_columns_exist(df):
    """12 kolom fitur di kontrak harus benar-benar ada di dataframe."""
    missing = set(FEATURE_COLUMNS) - set(df.columns)
    assert not missing, f"kolom fitur hilang dari dataframe: {missing}"


def test_no_target_leakage(df):
    """Kolom label tidak boleh nyelip jadi fitur input."""
    leaked = set(FEATURE_COLUMNS) & set(FORBIDDEN_COLUMNS)
    assert not leaked, f"kolom terlarang ikut jadi fitur input: {leaked}"


def test_split_is_by_trip(df):
    """Satu trip_id tidak boleh tersebar di dua split (train/val/test)."""
    n_split_per_trip = df.groupby('trip_id')['split'].nunique()
    bocor = n_split_per_trip[n_split_per_trip > 1]
    assert bocor.empty, f"trip_id berikut tersebar di >1 split: {list(bocor.index)}"


def test_ttb_is_per_row(df):
    """time_to_breach harus menghitung mundur, bukan satu angka per trip."""
    breached_trip_ids = df.loc[df['time_to_breach'] != 999, 'trip_id'].unique()
    subset = df[df['trip_id'].isin(breached_trip_ids)]
    n_unique_ttb = subset.groupby('trip_id')['time_to_breach'].nunique()
    flat = n_unique_ttb[n_unique_ttb <= 1]
    assert flat.empty, (
        f"{len(flat)} dari {len(n_unique_ttb)} trip breach punya TTB konstan "
        f"(bukan hitung mundur per menit), contoh trip_id: {list(flat.index[:5])}"
    )


def test_feature_dtypes(df):
    """door_open & reefer_on harus biner; hour_of_day harus 0-23."""
    for col in ['door_open', 'reefer_on']:
        nilai = set(df[col].unique())
        assert nilai <= {0, 1}, f"{col} punya nilai di luar {{0,1}}: {nilai}"

    jam_min, jam_max = df['hour_of_day'].min(), df['hour_of_day'].max()
    assert 0 <= jam_min and jam_max <= 23, (
        f"hour_of_day di luar rentang 0-23: min={jam_min}, max={jam_max}"
    )


if __name__ == "__main__":
    df = pd.read_parquet(DATA_PATH)
    print(f"Dimuat: {len(df):,} baris, {df['trip_id'].nunique()} trip\n")

    checks = [
        test_all_feature_columns_exist,
        test_no_target_leakage,
        test_split_is_by_trip,
        test_ttb_is_per_row,
        test_feature_dtypes,
    ]

    lolos = 0
    for check in checks:
        try:
            check(df)
            print(f"  LOLOS  {check.__name__}")
            lolos += 1
        except AssertionError as e:
            print(f"  GAGAL  {check.__name__}\n         -> {e}")

    print(f"\nHasil: {lolos}/{len(checks)} lolos")
