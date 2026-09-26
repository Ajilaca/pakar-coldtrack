"""
Jalankan latihan lokal:  python run_train.py --data dataset_v1.parquet --epochs 25
Butuh: prep_windows.py dan train_gru.py di folder yang sama.
"""
import argparse, json, time, numpy as np, pandas as pd, torch
import prep_windows as pw, train_gru as tg

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="dataset_v1.parquet")
ap.add_argument("--epochs", type=int, default=25)
ap.add_argument("--out", default="gru_v1.pt")
a = ap.parse_args()

device = "cuda" if torch.cuda.is_available() else "cpu"
print("device:", device, "| torch", torch.__version__)
t0 = time.time()
ds = pd.read_parquet(a.data)
sp = pw.split_trips(ds)
out = {k: pw.make_windows(ds, v) for k, v in sp.items()}
print({k: v[0].shape for k, v in out.items()}, f"| siap {time.time() - t0:.0f}s")

sc = tg.fit_scalers(out["train"][0], out["train"][1], out["train"][2])
tr = tg.to_tensors(*out["train"][:3], sc, device)
va = tg.to_tensors(*out["val"][:3], sc, device)
te = tg.to_tensors(*out["test"][:3], sc, device)

model = tg.train(tr, va, epochs=a.epochs, device=device)
tg.report(model, te, out["test"][2], sc, name="uji")

torch.save(model.state_dict(), a.out)
json.dump({k: (v.tolist() if hasattr(v, "tolist") else v) for k, v in sc.items()}, open("scalers_v1.json", "w"))
print("tersimpan:", a.out, "dan scalers_v1.json | total", f"{time.time() - t0:.0f}s")
