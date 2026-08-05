"""
Tes kontrak data — ColdTrack AI
Memastikan kolom label tidak pernah bocor jadi fitur input model, dan skema
kolom sesuai feature_schema.md. Jalankan dengan: pytest test_data_contract.py
"""
import pandas as pd
import pytest

DATA_PATH = "data/processed/v4_seed1000_700trips.parquet"

# Sesuai feature_schema.md — HANYA 12 kolom ini yang boleh dipakai sebagai X (input model)
ALLOWED_FEATURE_COLUMNS = [
    "temp_c", "delta_temp", "ambient_c", "delta_ambient", "solar_radiation",
    "humidity", "door_open", "reefer_on", "reefer_duration_min",
    "speed_kmh", "harsh_events", "hour_of_day",
]

# Alias supaya modul R2 (build_windows, build_pretrain_windows, export_onnx) tetap jalan.
# Urutan list di atas WAJIB dipertahankan — model membaca fitur berdasarkan posisi kolom,
# bukan nama, jadi mengacaknya akan merusak prediksi tanpa memunculkan error apa pun.
FEATURE_COLUMNS = ALLOWED_FEATURE_COLUMNS

# Kolom yang TIDAK BOLEH pernah dipakai sebagai fitur input, apapun alasannya:
# - tiga label target
# - temp_true_c: ground truth yang di dunia nyata tidak pernah tersedia
#   (yang tersedia cuma bacaan sensor / temp_c)
FORBIDDEN_AS_FEATURE = [
    "is_anomaly", "failure_mode", "time_to_breach", "temp_true_c",
]


def get_feature_columns(df: pd.DataFrame) -> list:
    """
    Fungsi acuan tunggal untuk memilih kolom fitur X.
    Pipeline training WAJIB memanggil fungsi ini, bukan menulis
    df.drop(columns=[...]) sendiri — whitelist lebih aman daripada blacklist,
    karena kolom baru yang lupa didaftarkan otomatis tidak ikut terpilih.

    Urutan mengikuti ALLOWED_FEATURE_COLUMNS (skema), bukan urutan kolom di
    parquet — supaya urutan fitur tidak berubah diam-diam kalau suatu saat
    urutan penyimpanan kolom di simulator berubah.
    """
    return [c for c in ALLOWED_FEATURE_COLUMNS if c in df.columns]


@pytest.fixture(scope="module")
def df():
    return pd.read_parquet(DATA_PATH)


def test_forbidden_columns_exist_in_raw_data(df):
    """Sanity check: label memang ada di data mentah (bukan salah baca file)."""
    for col in ["is_anomaly", "failure_mode", "time_to_breach"]:
        assert col in df.columns, f"Kolom label {col} tidak ditemukan di data"


def test_feature_columns_exclude_all_labels(df):
    """Tes inti: fungsi get_feature_columns tidak pernah meloloskan label."""
    features = get_feature_columns(df)
    leaked = set(features) & set(FORBIDDEN_AS_FEATURE)
    assert not leaked, f"KEBOCORAN TARGET: kolom terlarang lolos sebagai fitur: {leaked}"


def test_feature_columns_match_schema_exactly(df):
    """Pastikan tepat 12 kolom sesuai feature_schema.md, tidak kurang tidak lebih."""
    features = get_feature_columns(df)
    assert len(features) == 12, f"Jumlah fitur {len(features)}, seharusnya 12"
    assert features == ALLOWED_FEATURE_COLUMNS, (
        f"Urutan fitur menyimpang dari skema.\nSkema : {ALLOWED_FEATURE_COLUMNS}\nHasil : {features}"
    )


def test_time_to_breach_varies_within_trip(df):
    """
    Regresi untuk Bug 1 (laporan R2): time_to_breach harus berubah per menit
    dalam satu trip yang breach, bukan nilai konstan di semua baris.
    """
    breached_trips = df[df["time_to_breach"] < 999]["trip_id"].unique()
    assert len(breached_trips) > 0, "Tidak ada trip yang breach sama sekali — cek data"

    for trip_id in breached_trips[:20]:  # sampel 20 trip biar cepat
        ttb_values = df[df["trip_id"] == trip_id]["time_to_breach"]
        assert ttb_values.nunique() > 1, (
            f"trip_id={trip_id}: time_to_breach konstan di semua baris — "
            f"regresi Bug 1 (lihat laporan bug R2)"
        )


def test_labels_match_onset_minute(df):
    """
    Regresi untuk Bug 3 (laporan R2): failure_mode dan is_anomaly harus A0/0
    sebelum onset_minute, dan berubah ke kode anomalinya persis di onset_minute.
    Trip A8 dikecualikan karena anomalinya memang ada sejak menit 0.
    """
    anomaly_trips = df[df["failure_mode"] != "A0"]["trip_id"].unique()
    checked = 0
    for trip_id in anomaly_trips[:30]:  # sampel 30 trip biar cepat
        trip = df[df["trip_id"] == trip_id].sort_values("minute")
        mode = trip["failure_mode"].iloc[-1]
        if mode == "A8":
            continue
        onset = trip["onset_minute"].iloc[0]
        assert not pd.isna(onset), f"trip_id={trip_id}: onset_minute kosong padahal anomali"

        before = trip[trip["minute"] < onset]
        after = trip[trip["minute"] >= onset]
        if len(before) > 0:
            assert (before["failure_mode"] == "A0").all(), (
                f"trip_id={trip_id}: masih ada label anomali sebelum onset_minute — regresi Bug 3"
            )
            assert (before["is_anomaly"] == 0).all(), (
                f"trip_id={trip_id}: is_anomaly=1 sebelum onset_minute — regresi Bug 3"
            )
        assert (after["failure_mode"] == mode).all(), (
            f"trip_id={trip_id}: label tidak konsisten setelah onset_minute"
        )
        checked += 1
    assert checked > 0, "Tidak ada trip anomali (selain A8) yang berhasil dicek"


def test_split_is_by_trip(df):
    """Satu trip_id tidak boleh tersebar di dua split — mencegah kebocoran train/test."""
    n_split_per_trip = df.groupby("trip_id")["split"].nunique()
    bocor = n_split_per_trip[n_split_per_trip > 1]
    assert bocor.empty, f"trip_id berikut tersebar di >1 split: {list(bocor.index)}"


def test_feature_dtypes(df):
    """door_open & reefer_on harus biner; hour_of_day harus 0-23."""
    for col in ["door_open", "reefer_on"]:
        nilai = set(df[col].unique())
        assert nilai <= {0, 1}, f"{col} punya nilai di luar {{0,1}}: {nilai}"

    jam_min, jam_max = df["hour_of_day"].min(), df["hour_of_day"].max()
    assert 0 <= jam_min and jam_max <= 23, (
        f"hour_of_day di luar rentang 0-23: min={jam_min}, max={jam_max}"
    )
