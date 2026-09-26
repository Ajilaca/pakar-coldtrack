"""
Latih XGBoost untuk TTB (fitur ringkasan jendela + fitur fisika).
Jalankan:  python run_train_xgb.py --data dataset_v3.parquet
Butuh: prep_windows.py, ttb_features.py, observer.py, coldtrack_sim.py di folder yang sama.
"""
import argparse, time, numpy as np, pandas as pd, xgboost as xgb
import prep_windows as pw, ttb_features as tf, observer as ob

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="dataset_v3.parquet")
ap.add_argument("--out", default="xgb_ttb.json")
a = ap.parse_args()

t0 = time.time()
ds = pd.read_parquet(a.data)
sp = pw.split_trips(ds)                       # pembagian SAMA dengan GRU (seed 0)
out = {k: pw.make_windows(ds, v) for k, v in sp.items()}
F, names = {}, None
for k in out:
    a1, n1 = tf.build(out[k][0], out[k][1])
    a2, n2 = ob.windows_extra(ds, sp[k])
    a3, n3 = ob.projection_features(ds, sp[k])
    F[k] = np.hstack([a1, a2, a3]); names = n1 + n2 + n3
Y = {k: out[k][2][:, 3] for k in out}
print(f"fitur: {len(names)} | jendela latih {len(Y['train'])} | siap {time.time() - t0:.0f}s")

m = xgb.XGBRegressor(n_estimators=800, learning_rate=0.05, max_depth=6, subsample=0.8, colsample_bytree=0.8,
                     min_child_weight=5, early_stopping_rounds=40, n_jobs=-1, random_state=0)
m.fit(F["train"], Y["train"], eval_set=[(F["val"], Y["val"])], verbose=False)
print("pohon terpakai:", m.best_iteration + 1)

y = Y["test"]; p = np.clip(m.predict(F["test"]), 0, 240)
phys = F["test"][:, names.index("ttb_proj")]
near = y < 120; le30 = y <= 30
def line(nm, q):
    print(f"{nm:34s} MAE semua {np.abs(q - y).mean():5.1f} | TTB<=30 {np.abs(q[le30] - y[le30]).mean():5.1f} | "
          f"TTB<120 {np.abs(q[near] - y[near]).mean():5.1f} | TTB=0 {np.abs(q[y == 0] - y[y == 0]).mean():5.1f}")
print("\n=== uji (data yang tidak dipakai untuk latih atau validasi) ===")
print(f"tebak rata-rata                    MAE semua {np.abs(y - Y['train'].mean()).mean():5.1f}")
line("fisika murni", phys)
line("XGBoost + fitur fisika", p)
imp = sorted(zip(m.feature_importances_, names), reverse=True)[:6]
print("fitur terpenting:", [(n, round(float(v), 3)) for v, n in imp])

m.save_model(a.out)
with open("xgb_features.txt", "w") as f: f.write("\n".join(names))
print(f"\ntersimpan: {a.out} dan xgb_features.txt | total {time.time() - t0:.0f}s")
