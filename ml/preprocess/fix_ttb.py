import pandas as pd

DATA_PATH = "data/processed/v1_seed1000_700trips.parquet"
OUT_PATH = "data/processed/v1_seed1000_700trips_ttbfix.parquet"

# Batas aman tiap muatan, sesuai nilai TERVERIFIKASI di dataset_card.md
CARGO_THRESHOLDS = {
    'vaksin_2_8C': (2.0, 8.0),
    'daging_beku': (-25.0, -18.0),
    'ikan_segar': (0.0, 5.0),
    'sayur_buah': (2.0, 4.0),
    'produk_susu': (2.0, 4.0),
}

# Mode di mana temp_c (bacaan sensor) TIDAK bisa dipercaya buat hitung TTB
UNRELIABLE_MODES = {'A5', 'A6'}


def recompute_ttb_for_trip(temp_c, low, high):
    n = len(temp_c)
    ttb = [999] * n
    last_breach_idx = None   # index breach terdekat, dilihat dari kanan

    for i in range(n - 1, -1, -1):   # mundur: n-1, n-2, ..., 0
        is_breach = temp_c[i] < low or temp_c[i] > high
        if is_breach:
            last_breach_idx = i

        if last_breach_idx is None:
            ttb[i] = 999
        else:
            ttb[i] = last_breach_idx - i

    return ttb

def fix_one_trip(group):
    """group = potongan dataframe, isinya cuma baris-baris SATU trip_id."""
    cargo_type = group['cargo_type'].iloc[0]
    low, high = CARGO_THRESHOLDS[cargo_type]

    ttb_baru = recompute_ttb_for_trip(group['temp_c'].values, low, high)

    group = group.copy()
    group['time_to_breach'] = ttb_baru

    failure_mode = group['failure_mode'].iloc[0]
    group['ttb_reliable'] = failure_mode not in UNRELIABLE_MODES

    return group


if __name__ == "__main__":
    df = pd.read_parquet(DATA_PATH)
    df = df.sort_values(['trip_id', 'minute'])   # WAJIB urut per menit sebelum diproses

    fixed = df.groupby('trip_id', group_keys=False).apply(fix_one_trip)

    fixed.to_parquet(OUT_PATH, index=False)
    print(f"Tersimpan: {OUT_PATH}")
    print(f"Trip dengan ttb_reliable=False: {fixed.groupby('trip_id')['ttb_reliable'].first().eq(False).sum()}")
