"""
ColdTrack AI v2 - simulator fisika (4 skenario)
A0 sehat | A1 pintu terbuka | A2 kejut ambien ekstrem | A3 sensor rusak
Pelanggaran dinilai dari SUHU MUATAN terhadap rentang optimal produk.
Truk = Isuzu 18 CBM refrigerated box; tiap parameter diberi tag [SUMBER]/[ATP]/[ASUMSI]/[DESAIN] di TRUCK.
"""
import os, json
import numpy as np
import pandas as pd

# ------------------------------------------------------------------ 0. KONFIGURASI
# TODO: samakan string label dengan keluaran MVP lama
# Kejadian = bendera independen (bisa bersamaan). A1 pintu | A2 kejut ambien | A3 sensor rusak
CLASS_LABELS = {"A1": "pintu_terbuka_lama", "A2": "kejutan_ambien_ekstrem", "A3": "masalah_sensor"}
EVENTS = ["A1", "A2", "A3"]

CLIM_PATH = "/content/data/clean/climate_clean.csv"
SPEC_PATH = "/content/data/product_specs.csv"
SENSOR_PATH = "/content/drive/MyDrive/coldtrack_v2/data/sensor_fault_params.json"

# (t_lo, t_hi, t_set) derajat C. Batas = proposal. t_set beku -20 = rentang freezer Isuzu (-18..-20).
# Daging segar 0-4 = ASUMSI (chiller Isuzu 0..+5).
PROFILES = {
    ("ikan", "fresh"): (0, 5, 2.0),        ("ikan", "frozen"): (-25, -18, -20.0),
    ("daging", "fresh"): (0, 4, 2.0),      ("daging", "frozen"): (-25, -18, -20.0),
    ("sayur", "fresh"): (2, 4, 2.5),       ("buah", "fresh"): (2, 4, 2.5),
    ("susu_telur", "fresh"): (2, 4, 2.5),  ("susu_telur", "frozen"): (-25, -18, -20.0),
}

# ---------------- TRUK: Isuzu 18 CBM refrigerated box (isuzuvehicles.com) ----------------
# [SUMBER] dimensi dalam, payload.  [ATP] K.  [ASUMSI] tebal isolasi, luas pintu, margin Qmax, Cd.
TRUCK = dict(
    L=4.015, W=2.1, H=1.8,        # m, dimensi dalam box   [SUMBER Isuzu]
    payload_kg=4285.0,            # [SUMBER Isuzu]
    wall_m=0.08,                  # tebal isolasi PU        [makalah truk 67-97 mm; pemasok 75-100 mm; tidak ada di halaman Isuzu]
    K=0.40,                       # W/m2K, batas ATP isolasi diperkuat (0,70 = isolasi normal) [ATP]
    K_design=0.70,                # K terburuk untuk mengukur Qmax
    door_area=None,               # m2, dihitung = W*H (pintu belakang penuh)  [ASUMSI]
    Cd=0.65,                      # koef. lubang, pertukaran udara pintu   [Gosney-Olama/ASHRAE via calcengineer.com]
    Qmax_W=2575.0,                # kapasitas pendingin nominal (0 C dalam/30 C luar) [makalah truk: publications.cnr.it/.../188981]
    Qmargin=1.5,                  # HANYA untuk pemeriksaan silang Qmax turunan (tidak dipakai simulasi)
    T_design_out=36.0,            # diganti persentil-95 t_max data BMKG oleh set_truck_design()
    T_set_design=-20.0,           # titik setel freezer Isuzu               [SUMBER Isuzu]
    h_conv=8.0,                   # W/m2K konveksi udara-muatan             [makalah truk: 8 W/m2K, muatan karkas]
    rho_bulk=500.0,               # kg/m3 kerapatan curah muatan kemasan    [Cargo Handbook 400-595 (ikan beku kotak/karton)]
    band_k=1.0,                   # pita proporsional termostat (K)         [DESAIN]
)
def _truck_const():
    T = TRUCK
    V = T["L"] * T["W"] * T["H"]
    A_in = 2 * (T["L"] * T["W"] + T["L"] * T["H"] + T["W"] * T["H"])
    L2, W2, H2 = T["L"] + 2 * T["wall_m"], T["W"] + 2 * T["wall_m"], T["H"] + 2 * T["wall_m"]
    A_out = 2 * (L2 * W2 + L2 * H2 + W2 * H2)
    A_m = float(np.sqrt(A_in * A_out))               # luas rata-rata geometrik (Annex ATP, dari ingatan)
    UA = T["K"] * A_m
    UA_design = T["K_design"] * A_m
    Qmax = T["Qmax_W"]                                # sumber; turunan lama tersedia di Qmax_derived
    Qmax_derived = T["Qmargin"] * UA_design * (T["T_design_out"] - T["T_set_design"])
    return dict(V=V, A_in=A_in, A_out=A_out, A_m=A_m, UA=UA, UA_design=UA_design, Qmax=Qmax, Qmax_derived=Qmax_derived,
                C_air=1.2 * 1005.0 * V, door_area=T["door_area"] or T["W"] * T["H"])

PARAM = dict(horizon_min=240)     # batas TTB (keputusan desain)
SENSOR_DEFAULT = dict(noise_std=0.073, sat_value=122.15, n_switch_median=6)

def load_sensor_params(path=SENSOR_PATH):
    p = dict(SENSOR_DEFAULT)
    try:
        j = json.load(open(path))
        p.update(noise_std=j.get("noise_sehat_std_c", p["noise_std"]),
                 sat_value=j.get("nilai_macet_ekstrem", p["sat_value"]),
                 n_switch_median=j.get("peralihan_median_kali", p["n_switch_median"]))
    except Exception:
        pass
    return p

def load_data(clim_path=CLIM_PATH, spec_path=SPEC_PATH):
    clim = pd.read_csv(clim_path)[["t_min", "t_avg", "t_max", "rh_avg"]].reset_index(drop=True)
    specs = pd.read_csv(spec_path)
    set_truck_design(clim)
    return clim, specs

def set_truck_design(clim):
    """Suhu luar desain Qmax = persentil-95 t_max data BMKG (bukan angka karangan)."""
    TRUCK["T_design_out"] = float(np.percentile(clim["t_max"], 95))

# ------------------------------------------------------------------ 1. PRODUK
def get_product(specs, category, name=None, state="fresh", custom=None, rng=None):
    """custom (kategori 'lainnya') = dict(c_above, c_below, t_lo, t_hi, [t_set], [name])"""
    if category == "lainnya":
        c = custom["c_above"] if state == "fresh" else custom["c_below"]
        lo, hi = custom["t_lo"], custom["t_hi"]
        return dict(category="lainnya", name=custom.get("name", "custom"), state=state, c=float(c),
                    t_lo=lo, t_hi=hi, t_set=custom.get("t_set", lo + 0.4 * (hi - lo)))
    sub = specs[specs.category == category]
    if name:
        row = sub[sub.name_id == name].iloc[0]
    else:
        row = sub.iloc[(rng or np.random.default_rng()).integers(len(sub))]
    c = row.c_above_kj_kgc if state == "fresh" else row.c_below_kj_kgc
    lo, hi, st = PROFILES[(category, state)]
    return dict(category=category, name=row.name_id, state=state, c=float(c), t_lo=lo, t_hi=hi, t_set=st)

# ------------------------------------------------------------------ 2. UDARA LUAR PER MENIT
def ambient_curve(row, n, start_hour, rng, noise=0.05):
    """min ~06.00, max ~14.00; bentuk diatur agar rata-rata harian = t_avg."""
    hh = np.linspace(0, 24, 1441)
    up = (hh >= 6) & (hh < 14)
    base = np.where(up, 0.5 - 0.5 * np.cos(np.pi * (hh - 6) / 8),
                    0.5 + 0.5 * np.cos(np.pi * (((hh - 14) % 24) / 16)))
    target = np.clip((row.t_avg - row.t_min) / max(row.t_max - row.t_min, 1e-6), 0.05, 0.95)
    lo, hi = 0.2, 6.0
    for _ in range(40):
        p = (lo + hi) / 2
        if np.mean(np.clip(base, 0, 1) ** p) > target: lo = p
        else: hi = p
    h = (start_hour + np.arange(n) / 60.0) % 24
    T = row.t_min + (row.t_max - row.t_min) * np.clip(np.interp(h, hh, base), 0, 1) ** p
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = 0.98 * e[i - 1] + rng.normal(0, noise)
    T = T + e
    # Magnus: titik embun dianggap konstan sepanjang hari, RH mengikuti suhu
    b_, c_ = 17.62, 243.12
    g = np.log(np.clip(row.rh_avg, 1, 100) / 100.0) + b_ * row.t_avg / (c_ + row.t_avg)
    Td = c_ * g / (b_ - g)
    RH = np.clip(100 * np.exp(b_ * Td / (c_ + Td) - b_ * T / (c_ + T)), 5, 100)
    return T, RH

# ------------------------------------------------------------------ 3. TRUK
def truck(mass_kg):
    P = _truck_const()
    A_cargo = 6.0 * (mass_kg / TRUCK["rho_bulk"]) ** (2 / 3)   # luas permukaan muatan (kubus setara)
    P["UA_ac"] = TRUCK["h_conv"] * A_cargo                      # kopling udara-muatan = h * A
    return P

# ------------------------------------------------------------------ 4. SIMULASI SATU PERJALANAN
def simulate(prod, mass_kg, clim_row, events=(), duration_h=8.0, start_hour=8.0, T_init=None,
             door_start_min=None, door_min=20, door_frac=1.0, n_open=1,
             shock_start_min=None, shock_min=90,
             fault_type=None, fault_start_min=None, reefer_off_when_shock=True,
             sensor=None, seed=None, trip_id=0):
    """events: subset dari {"A1","A2","A3"} (boleh bersamaan). Kosong = trip sehat."""
    events = set(events)
    rng = np.random.default_rng(seed)
    sensor = sensor or load_sensor_params()
    n = int(round(duration_h * 60))
    Tamb, RHamb = ambient_curve(clim_row, n, start_hour, rng)
    P = truck(mass_kg)
    C_c = mass_kg * prod["c"] * 1000.0
    Tset, thi, tlo = prod["t_set"], prod["t_hi"], prod["t_lo"]
    T_init = Tset if T_init is None else float(T_init)

    door = np.zeros(n); dfrac = np.zeros(n)          # dfrac = bagian bukaan pintu (0..1)
    moving = np.ones(n); reefer_off = np.zeros(n)
    ev_door = np.zeros(n); ev_shock = np.zeros(n); ev_sensor = np.zeros(n)
    shock = np.zeros(n); peak = None
    if "A1" in events:                               # A0 tidak punya pintu terbuka sama sekali
        t = door_start_min if door_start_min is not None else int(rng.integers(30, max(31, n // 2)))
        for k in range(int(n_open)):                 # 1..n kali dibuka, tiap bukaan selama door_min
            s = int(t); e = min(n, s + int(door_min))
            if s >= n: break
            door[s:e] = 1; dfrac[s:e] = door_frac; ev_door[s:e] = 1
            moving[max(0, s - 3):min(n, e + 3)] = 0
            t = e + int(rng.integers(10, 60))        # jeda sebelum bukaan berikutnya
    if "A2" in events:
        s = shock_start_min if shock_start_min is not None else int(rng.integers(30, max(31, n // 2)))
        e = min(n, s + int(shock_min)); w = np.zeros(n); w[s:e] = 1
        shock = np.clip(np.convolve(w, np.ones(6) / 6, mode="same"), 0, 1); moving[s:e] = 0
        if reefer_off_when_shock: reefer_off[s:e] = 1
        ev_shock[s:e] = 1
        peak = float(clim_row.t_max)                 # puncak = t_max data BMKG (tanpa tambahan)
    onset = None
    if "A3" in events:
        onset = fault_start_min if fault_start_min is not None else int(rng.integers(30, max(31, n - 30)))
        fault_type = fault_type or rng.choice(["extreme_stuck", "flat_stuck", "intermittent"])
        ev_sensor[onset:] = 1

    g, rho_cp, band = 9.81, 1.2 * 1005.0, TRUCK["band_k"]
    dt, sub = 5.0, 12
    Ta = Tc = T_init
    Tair = np.zeros(n); Tcar = np.zeros(n); duty = np.zeros(n); Tout_arr = np.zeros(n)
    for i in range(n):
        Tout = Tamb[i] + shock[i] * max(peak - Tamb[i], 0.0) if peak is not None else Tamb[i]
        reefer_on = not (door[i] or reefer_off[i])
        for _ in range(sub):
            # pertukaran udara pintu (buoyancy, orifice): Vdot = (Cd/3) A sqrt(g H |dT|/Tmean)
            dT = Tout - Ta
            Vdot = (TRUCK["Cd"] / 3) * P["door_area"] * dfrac[i] * np.sqrt(g * TRUCK["H"] * abs(dT) / (273.15 + 0.5 * (Tout + Ta)))
            UAd = rho_cp * Vdot
            q = float(np.clip(P["Qmax"] * (Ta - Tset) / band, 0, P["Qmax"])) if reefer_on else 0.0
            Ta += ((P["UA"] + UAd) * dT + P["UA_ac"] * (Tc - Ta) - q) / P["C_air"] * dt
            Tc += P["UA_ac"] * (Ta - Tc) / C_c * dt
        Tair[i], Tcar[i], duty[i], Tout_arr[i] = Ta, Tc, q / P["Qmax"], Tout

    # ---- sensor (dibaca IoT) ----
    Ts = Tair + rng.normal(0, sensor["noise_std"], n)
    sensor_ok = np.ones(n)
    if "A3" in events:
        seg = slice(onset, n)
        if fault_type == "extreme_stuck":
            Ts[seg] = sensor["sat_value"]; sensor_ok[seg] = 0
        elif fault_type == "flat_stuck":
            Ts[seg] = Ts[onset]; sensor_ok[seg] = 0
        else:  # intermittent: berpindah normal <-> ekstrem
            k = max(2, int(rng.poisson(sensor["n_switch_median"])))
            cuts = np.sort(rng.integers(onset, n, k)); bad = False; prev = onset
            for c_ in list(cuts) + [n]:
                if bad: Ts[prev:c_] = sensor["sat_value"]; sensor_ok[prev:c_] = 0
                bad = not bad; prev = c_
    Ts = np.round(Ts, 2)

    # ---- label ----
    breach = (Tcar > thi) | (Tcar < tlo)
    H = PARAM["horizon_min"]; ttb = np.full(n, float(H)); nxt = np.inf
    for i in range(n - 1, -1, -1):
        if breach[i]: nxt = i
        ttb[i] = min(nxt - i, H) if np.isfinite(nxt) else H
    lab = np.array(["+".join(k for k, f in (("A1", ev_door[i]), ("A2", ev_shock[i]), ("A3", ev_sensor[i])) if f) or "A0"
                    for i in range(n)], dtype=object)
    lab_txt = [("normal_sehat" if x == "A0" else "+".join(CLASS_LABELS[k] for k in x.split("+"))) for x in lab]

    df = pd.DataFrame(dict(
        trip_id=trip_id, minute=np.arange(n), hour_of_day=(start_hour + np.arange(n) / 60) % 24,
        T_amb=Tout_arr, RH_amb=RHamb, T_sensor=Ts, T_air=Tair, T_cargo=Tcar,
        reefer_duty=duty, door_open=door, moving=moving, sensor_ok=sensor_ok,
        category=prod["category"], product=prod["name"], state=prod["state"],
        mass_kg=mass_kg, c_kj_kgc=prod["c"], thermal_mass_kj_k=mass_kg * prod["c"], t_lo=tlo, t_hi=thi,
        ev_A1=ev_door, ev_A2=ev_shock, ev_A3=ev_sensor,
        scenario="+".join(sorted(events)) or "A0", failure_mode=lab, label=lab_txt,
        is_breach=breach.astype(int), ttb_min=ttb))
    for h in (15, 30, 60):                              # target prediksi suhu
        df[f"y_Tcargo_{h}"] = df["T_cargo"].shift(-h)
        df[f"y_Tair_{h}"] = df["T_air"].shift(-h)
    return df

# ------------------------------------------------------------------ 5. UNTUK FRONTEND / API
def simulate_from_inputs(inp, clim, specs, seed=None):
    """inp: dict dari form frontend -> dict siap dikirim sebagai JSON."""
    prod = get_product(specs, inp["category"], inp.get("name"), inp.get("state", "fresh"), inp.get("custom"))
    row = clim.iloc[int(inp.get("day_index", 0)) % len(clim)]
    keys = ["events", "duration_h", "start_hour", "T_init", "door_start_min", "door_min", "door_frac", "n_open",
            "shock_start_min", "shock_min", "fault_type", "fault_start_min", "reefer_off_when_shock"]
    kw = {k: inp[k] for k in keys if k in inp and inp[k] is not None}
    df = simulate(prod, float(inp["mass_kg"]), row, seed=seed, **kw)
    return df

# ------------------------------------------------------------------ 6. GENERATOR DATASET LATIH
def generate_dataset(clim, specs, n_trips=800, seed=0, p_events=(0.45, 0.35, 0.35)):
    """Kejadian independen per trip (p tiap A1/A2/A3) -> kombinasi terbentuk alami."""
    rng = np.random.default_rng(seed); parts = []
    sensor = load_sensor_params()
    for k in range(n_trips):
        cat = rng.choice(["ikan", "daging", "sayur", "buah", "susu_telur"], p=[.25, .2, .2, .2, .15])
        state = "frozen" if (cat in ("ikan", "daging", "susu_telur") and rng.random() < 0.35) else "fresh"
        prod = get_product(specs, cat, None, state, rng=rng)
        mass = float(np.exp(rng.uniform(np.log(100), np.log(TRUCK["payload_kg"]))))
        row = clim.iloc[int(rng.integers(len(clim)))]
        ev = [e for e, p in zip(EVENTS, p_events) if rng.random() < p]
        kw = {}
        if "A1" in ev: kw.update(door_min=int(rng.integers(1, 61)), door_frac=rng.uniform(0.2, 1.0), n_open=int(rng.integers(1, 3)))
        if "A2" in ev: kw.update(shock_min=int(rng.integers(60, 300)))
        parts.append(simulate(prod, mass, row, ev, duration_h=rng.uniform(6, 14), start_hour=rng.uniform(0, 24),
                              T_init=prod["t_set"], sensor=sensor, seed=int(rng.integers(1e9)), trip_id=k, **kw))
    return pd.concat(parts, ignore_index=True)

def summarize(ds):
    g = ds.groupby("trip_id").agg(scenario=("scenario", "first"), mass=("mass_kg", "first"),
                                  breach=("is_breach", "max"))
    g["massa"] = pd.cut(g.mass, [0, 300, 800, 2000, 5000], labels=["<300", "300-800", "800-2000", ">2000"])
    print("peluang melanggar per kombinasi kejadian:\n", g.groupby("scenario").breach.agg(["size", "mean"]).round(2))
    print("\nper kombinasi x massa (kg):\n", g.pivot_table(index="scenario", columns="massa", values="breach", aggfunc="mean", observed=True).round(2))
