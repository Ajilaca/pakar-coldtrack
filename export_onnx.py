"""
Ekspor ONNX + cek paritas.
  python export_onnx.py --data dataset_v3.parquet

Hasil:
  coldtrack_gru.onnx  masukan: x [B,60,8] mentah (T_sensor_clean, T_amb, RH_amb, door_open, moving, hsin, hcos, sensor_bad)
                               s [B,4]    mentah (log_mass, c_kj_kgc, t_lo, t_hi)
                      keluaran: event_prob [B,3] (pintu lama, kejut ambien, sensor rusak), temp_c [B,3] (suhu muatan +15/30/60 menit, C)
                      normalisasi ada DI DALAM graf, jadi masukan tidak perlu dinormalkan lagi.
  coldtrack_ttb.onnx  masukan: features [B,37] (urutan sesuai xgb_features.txt), keluaran: TTB menit (potong 0..240 di kode pemanggil)
"""
import argparse, json, os, numpy as np, torch, torch.nn as nn
import onnxruntime as ort

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="dataset_v3.parquet")
ap.add_argument("--gru", default="gru_v1.pt")
ap.add_argument("--scalers", default="scalers_v1.json")
ap.add_argument("--xgb", default="xgb_ttb.json")
ap.add_argument("--n_check", type=int, default=512)
a = ap.parse_args()

import train_gru as tg, prep_windows as pw

# ------------------------------------------------------------------ data uji untuk cek paritas
import pandas as pd
ds = pd.read_parquet(a.data)
sp = pw.split_trips(ds)
Xte, Ste, Yte, _ = pw.make_windows(ds, sp["test"])
Xte, Ste = Xte[:a.n_check], Ste[:a.n_check]

# ------------------------------------------------------------------ GRU
sc = json.load(open(a.scalers))
model = tg.ColdGRU(12)
model.load_state_dict(torch.load(a.gru, map_location="cpu"))
model.eval()


class Deploy(nn.Module):
    """Normalisasi + GRU dalam satu graf. Kolom kontinu = 3 kolom pertama (tg.CONT_IDX = [0,1,2])."""
    def __init__(self, m, sc):
        super().__init__()
        self.m = m
        f = lambda v: torch.tensor(np.array(v, dtype=np.float32))
        self.register_buffer("x_mu", f(sc["x_mu"])); self.register_buffer("x_sd", f(sc["x_sd"]))
        self.register_buffer("s_mu", f(sc["s_mu"])); self.register_buffer("s_sd", f(sc["s_sd"]))
        self.t_mu = float(sc["t_mu"]); self.t_sd = float(sc["t_sd"])

    def forward(self, x, s):
        cont = (x[:, :, :3] - self.x_mu) / self.x_sd
        x2 = torch.cat([cont, x[:, :, 3:]], dim=2)
        sn = ((s - self.s_mu) / self.s_sd).unsqueeze(1).expand(-1, x.shape[1], -1)
        e, t, _ = self.m(torch.cat([x2, sn], dim=2))
        return torch.sigmoid(e), t * self.t_sd + self.t_mu


dep = Deploy(model, sc).eval()
xd = torch.tensor(Xte); sd = torch.tensor(Ste)
kw = dict(input_names=["x", "s"], output_names=["event_prob", "temp_c"], opset_version=17,
          dynamic_axes={"x": {0: "batch"}, "s": {0: "batch"}, "event_prob": {0: "batch"}, "temp_c": {0: "batch"}})
try:
    torch.onnx.export(dep, (xd[:2], sd[:2]), "coldtrack_gru.onnx", dynamo=False, **kw)
except TypeError:
    torch.onnx.export(dep, (xd[:2], sd[:2]), "coldtrack_gru.onnx", **kw)

with torch.no_grad():
    pe, pt = dep(xd, sd)
sess = ort.InferenceSession("coldtrack_gru.onnx", providers=["CPUExecutionProvider"])
oe, ot = sess.run(None, {"x": Xte.astype(np.float32), "s": Ste.astype(np.float32)})
d1, d2 = np.abs(oe - pe.numpy()).max(), np.abs(ot - pt.numpy()).max()
print(f"GRU  : {os.path.getsize('coldtrack_gru.onnx') / 1024:.0f} KB | selisih maks event {d1:.2e} | suhu {d2:.2e} C",
      "-> PARITAS OK" if max(d1, d2) < 1e-3 else "-> PERIKSA (selisih besar)")

# ------------------------------------------------------------------ XGBoost
try:
    import xgboost as xgb
    from onnxmltools.convert import convert_xgboost
    from onnxmltools.convert.common.data_types import FloatTensorType
    import ttb_features as tf, observer as ob
    m = xgb.XGBRegressor(); m.load_model(a.xgb)
    n = m.n_features_in_
    onx = convert_xgboost(m, initial_types=[("features", FloatTensorType([None, n]))], target_opset=15)
    with open("coldtrack_ttb.onnx", "wb") as f: f.write(onx.SerializeToString())
    # fitur uji (pembagian trip sama dengan latihan)
    a1, _ = tf.build(*[out for out in (Xte, Ste)])
    ids = sorted(sp["test"])
    e2, _ = ob.windows_extra(ds, sp["test"]); p2, _ = ob.projection_features(ds, sp["test"])
    Ft = np.hstack([tf.build(*pw.make_windows(ds, sp["test"])[:2])[0], e2, p2])[:a.n_check].astype(np.float32)
    s2 = ort.InferenceSession("coldtrack_ttb.onnx", providers=["CPUExecutionProvider"])
    po = s2.run(None, {"features": Ft})[0].ravel()
    px = m.predict(Ft)
    d3 = np.abs(po - px).max()
    print(f"XGB  : {os.path.getsize('coldtrack_ttb.onnx') / 1024:.0f} KB | selisih maks TTB {d3:.2e} menit",
          "-> PARITAS OK" if d3 < 1e-2 else "-> PERIKSA (selisih besar)")
except Exception as ex:
    print("XGB ekspor gagal:", type(ex).__name__, ex)
    print("Coba:  python -m pip install \"xgboost<2.1\"  lalu latih ulang (run_train_xgb.py) dan jalankan skrip ini lagi.")
