"""B3 -- latih kandidat terbaik (hasil b3_confirm) dan ekspor ONNX ke jalur KANDIDAT.

  python -m bench.b3_export --tag g16-gpu

- Model final dilatih dengan seed 1000 (ditetapkan sebelum melihat hasil per seed, supaya tidak
  memilih seed terbaik). Metrik yang dilaporkan untuk kandidat tetap mean 5 seed dari b3_confirm.
- Kontrak input/output IDENTIK dengan ml/reports/coldtrack.onnx (ColdTrackDeploy: normalisasi dan
  satuan asli dibungkus di grafik), jadi backend bisa memuatnya tanpa perubahan kode.
- Tidak menimpa coldtrack.onnx / coldtrack_ttb.onnx mana pun (aturan G3).

Keluaran: backend/models/candidates/coldtrack_gru_b3.onnx + coldtrack_gru_b3.json (kartu ringkas)
"""

import argparse
import json

import numpy as np
import torch

from bench.common import RESULTS_DIR, ROOT, git_info, now_iso, rel, write_json

SEED_FINAL = 1000
OUT_DIR = ROOT / "backend" / "models" / "candidates"
TOLERANSI = 1e-4


def main(argv=None):
    from bench.run import apply_device_env, check_cuda_or_die, resolve_tag

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", default="g16-gpu")
    a = ap.parse_args(argv)
    _, kind = resolve_tag(a.tag)
    apply_device_env(kind)
    check_cuda_or_die(kind)

    import onnxruntime as ort

    from bench import b3_lib as b3
    from bench import train_lib as tl
    from ml.model import ColdTrackDeploy, ColdTrackGRU
    from ml.preprocess.build_windows import FAILURE_CLASSES, HORIZONS, WINDOW_SIZE
    from ml.tests.test_data_contract import FEATURE_COLUMNS

    kep = json.loads((RESULTS_DIR / a.tag / "B3" / "keputusan_kandidat.json").read_text(encoding="utf-8"))
    nama = kep["kandidat_terbaik"]["gru"]
    if nama is None:
        print("Tidak ada kandidat GRU yang lolos aturan adopsi -- tidak ada yang diekspor.")
        return 1
    varian = nama.split("/", 1)[1]
    ringkas = kep["gru"][varian]
    cfg = b3.GruCfg(**ringkas["params"])

    tl.ensure_windows()
    data, _ = tl.prepare_gru_data()
    model, info = b3.train(data, cfg, SEED_FINAL, kind)
    (f, c, t), d = b3.predict(model, data, kind)
    metrik_final = b3.metrik_lengkap(f, c, t, d, data["mean"], data["std"])

    core = ColdTrackGRU(hidden_size=cfg.hidden_size, num_layers=cfg.num_layers, dropout=cfg.dropout)
    core.load_state_dict({k: v.cpu() for k, v in model.state_dict().items()})
    deploy = ColdTrackDeploy(core.eval(), data["mean"], data["std"]).eval()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    onnx_path = OUT_DIR / "coldtrack_gru_b3.onnx"
    torch.onnx.export(deploy, torch.randn(1, WINDOW_SIZE, len(FEATURE_COLUMNS)), str(onnx_path),
                      input_names=["window"], output_names=["forecast_c", "failure_prob", "time_to_breach_min"],
                      dynamic_axes={n: {0: "batch"} for n in ["window", "forecast_c", "failure_prob",
                                                               "time_to_breach_min"]},
                      opset_version=17, dynamo=False)

    # paritas ONNX (CPU EP) vs PyTorch CPU pada jendela val asli, pola ml/export_onnx.verify_parity
    raw = d["X"][:256].astype(np.float32)
    with torch.no_grad():
        ref = [x.numpy() for x in deploy(torch.tensor(raw))]
    got = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"]).run(None, {"window": raw})
    paritas = {}
    for n, p, q in zip(["forecast_c", "failure_prob", "time_to_breach_min"], ref, got):
        ab = float(np.abs(p - q).max())
        rl = ab / max(float(np.abs(p).max()), 1e-9)
        paritas[n] = {"maxabs": ab, "rel": rl, "ok": ab < TOLERANSI or rl < TOLERANSI}
    ok = all(v["ok"] for v in paritas.values())

    kartu = {
        "status": "KANDIDAT -- belum menggantikan model produksi (menunggu gerbang G3 + uji split test sekali)",
        "dibuat_utc": now_iso(), "git": git_info(), "device_latih": a.tag, "seed_final": SEED_FINAL,
        "varian": varian, "konfigurasi": cfg.as_dict(),
        "parameter": sum(p.numel() for p in core.parameters()),
        "kontrak": {"input": {"name": "window", "shape": ["batch", WINDOW_SIZE, len(FEATURE_COLUMNS)],
                              "features": FEATURE_COLUMNS, "catatan": "identik dengan ml/reports/coldtrack.onnx"},
                    "outputs": {"forecast_c": {"horizons_menit": HORIZONS},
                                "failure_prob": {"classes": FAILURE_CLASSES},
                                "time_to_breach_min": {"catatan": "head GRU; TTB produksi tetap XGBoost"}}},
        "metrik_val_mean_5_seed": {k: v for k, v in ringkas.items() if k.endswith("_mean")},
        "metrik_val_model_final_seed1000": {k: v for k, v in metrik_final.items() if k not in ("confusion",)},
        "paritas_onnx_vs_pytorch": paritas, "paritas_ok": ok,
        "sumber_keputusan": rel(RESULTS_DIR / a.tag / "B3" / "keputusan_kandidat.json"),
        "latih": info,
    }
    write_json(OUT_DIR / "coldtrack_gru_b3.json", kartu)
    write_json(RESULTS_DIR / a.tag / "B3" / "export_kandidat.json", kartu | {"onnx": rel(onnx_path)})
    print(f"Tersimpan: {rel(onnx_path)} | paritas {'OK' if ok else 'GAGAL'} | "
          f"val seed1000 F1 {metrik_final['macro_f1']:.4f} PR-AUC {metrik_final['anomali_pr_auc']:.4f}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
