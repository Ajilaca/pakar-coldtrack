"""Smoke test B0: memastikan tiap jalur komputasi benar-benar jalan di device ini.

1. PyTorch: forward/backward/step ColdTrackGRU kecil; di cuda dicek arsitektur (sm_XXX ada di
   arch list build PyTorch) dan paritas forward terhadap CPU dengan bobot yang sama.
2. XGBoost: latih regresor kecil dengan device yang sesuai tag.
3. ONNX Runtime: muat model proposal (ml/reports/*.onnx) dan catat EP yang BENAR-BENAR aktif
   lewat session.get_providers(); di cuda, keluaran CUDA EP dibandingkan dengan CPU EP.

Hasil: bench/results/<tag>/smoke/run_0.json. Bukan angka benchmark -- hanya cek kelayakan.
"""

import time

import numpy as np

from bench.common import ROOT, git_info, now_iso, write_json

ONNX_MODELS = {
    "gru": ROOT / "ml" / "reports" / "coldtrack.onnx",
    "xgb_ttb": ROOT / "ml" / "reports" / "coldtrack_ttb.onnx",
}


def _sync(torch, dev):
    if dev.type == "cuda":
        torch.cuda.synchronize()


def cek_torch(kind):
    import torch
    from torch import nn

    from ml.model import ColdTrackGRU

    out = {"ok": False}
    dev = torch.device(kind)
    try:
        if kind == "cuda":
            cap = torch.cuda.get_device_capability(0)
            out["device_name"] = torch.cuda.get_device_name(0)
            out["capability"] = f"sm_{cap[0]}{cap[1]}"
            out["arch_list"] = torch.cuda.get_arch_list()
            out["arch_cocok"] = out["capability"] in out["arch_list"]
            torch.cuda.reset_peak_memory_stats()

        torch.manual_seed(0)
        model = ColdTrackGRU().to(dev)
        out["n_param"] = sum(p.numel() for p in model.parameters())
        opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
        g = torch.Generator().manual_seed(0)
        x = torch.randn(256, 60, 12, generator=g).to(dev)
        yf = torch.randn(256, 3, generator=g).to(dev)
        ym = torch.randint(0, 7, (256,), generator=g).to(dev)

        def step():
            f, c, t = model(x)
            loss = nn.functional.l1_loss(f, yf) + nn.functional.cross_entropy(c, ym) + t.pow(2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            return loss

        loss = step()                     # pemanasan (kompilasi kernel)
        _sync(torch, dev)
        n = 20
        t0 = time.perf_counter()
        for _ in range(n):
            loss = step()
        _sync(torch, dev)
        out["ms_per_step_b256"] = round((time.perf_counter() - t0) / n * 1000, 3)
        out["loss_akhir"] = float(loss.item())
        out["loss_finite"] = bool(torch.isfinite(loss).item())

        if kind == "cuda":
            model.eval()
            cpu_model = ColdTrackGRU()
            cpu_model.load_state_dict({k: v.cpu() for k, v in model.state_dict().items()})
            cpu_model.eval()
            with torch.no_grad():
                a = model(x)
                b = cpu_model(x.cpu())
            out["paritas_forward_maxabs_vs_cpu"] = max(float((p.cpu() - q).abs().max()) for p, q in zip(a, b))
            out["vram_puncak_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
        out["ok"] = out["loss_finite"] and out.get("arch_cocok", True)
    except Exception as e:  # noqa: BLE001 -- mis. "no kernel image is available" = build PyTorch terlalu lama
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def cek_xgboost(kind):
    import xgboost as xgb

    out = {"ok": False, "device": kind}
    try:
        rng = np.random.default_rng(0)
        X = rng.normal(size=(20000, 72)).astype(np.float32)
        y = X[:, :5].sum(1) + rng.normal(scale=0.1, size=len(X))
        params = {"n_estimators": 50, "max_depth": 6, "learning_rate": 0.1, "tree_method": "hist",
                  "random_state": 0}
        t0 = time.perf_counter()
        m = xgb.XGBRegressor(device=kind, **params).fit(X, y)
        out["detik_latih_50_pohon"] = round(time.perf_counter() - t0, 3)
        out["mae_latih"] = float(np.abs(m.predict(X) - y).mean())
        out["ok"] = bool(np.isfinite(out["mae_latih"]))
    except Exception as e:  # noqa: BLE001 -- cek kelayakan: semua kegagalan dicatat, bukan dilempar
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def cek_onnxruntime(kind):
    import onnxruntime as ort

    out = {"available_providers": ort.get_available_providers(), "models": {}}
    minta = ["CUDAExecutionProvider", "CPUExecutionProvider"] if kind == "cuda" else ["CPUExecutionProvider"]
    rng = np.random.default_rng(0)
    for nama, path in ONNX_MODELS.items():
        r = {"path": path.relative_to(ROOT).as_posix(), "diminta": minta}
        try:
            cpu = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
            inp = cpu.get_inputs()[0]
            x = rng.normal(size=(32, 60, 12)).astype(np.float32)
            ref = cpu.run(None, {inp.name: x})
            if kind == "cuda":
                sess = ort.InferenceSession(str(path), providers=minta)
                r["aktif"] = sess.get_providers()
                r["cuda_ep_aktif"] = r["aktif"][0] == "CUDAExecutionProvider"
                got = sess.run(None, {inp.name: x})
                r["paritas_maxabs_vs_cpu_ep"] = max(float(np.abs(np.asarray(p) - np.asarray(q)).max())
                                                    for p, q in zip(got, ref))
            else:
                r["aktif"] = cpu.get_providers()
            r["ok"] = True
        except Exception as e:  # noqa: BLE001 -- EP gagal dimuat adalah temuan, dicatat apa adanya
            r["ok"] = False
            r["error"] = f"{type(e).__name__}: {e}"
        out["models"][nama] = r
    return out


def run(ctx):
    hasil = {
        "workload": "smoke",
        "tag": ctx.tag,
        "device": ctx.device,
        "waktu_utc": now_iso(),
        "git": git_info(),
        "env": ctx.env_path,
        "kondisi_manual": ctx.profile.get("kondisi"),
        "torch": cek_torch(ctx.device),
        "xgboost": cek_xgboost(ctx.device),
        "onnxruntime": cek_onnxruntime(ctx.device),
    }
    for k in ["torch", "xgboost"]:
        print(f"  {k:12s} ok={hasil[k].get('ok')} {hasil[k].get('error', '')}")
    for nama, r in hasil["onnxruntime"]["models"].items():
        print(f"  ort/{nama:8s} aktif={r.get('aktif')} {r.get('error', '')}")
    return [write_json(ctx.out_root / "smoke" / "run_0.json", hasil)]
