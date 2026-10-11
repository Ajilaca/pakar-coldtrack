"""Daftar workload benchmark (bagian 6 CONTEXT_MODEL_BENCHMARK_RTX5070.md).

Tiap workload adalah modul dengan fungsi run(ctx) -> list[Path] (berkas JSON yang ditulis).
Workload yang belum diimplementasikan tetap terdaftar supaya CLI-nya stabil sejak B0.
"""

import importlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Workload:
    id: str
    judul: str
    tahap: str  # tahap rencana yang mengimplementasikan
    modul: str | None  # None = belum diimplementasikan

    def load(self):
        if self.modul is None:
            raise NotImplementedError(f"{self.id} belum diimplementasikan (dijadwalkan tahap {self.tahap})")
        return importlib.import_module(self.modul)


REGISTRY = {
    w.id: w
    for w in [
        Workload(
            "smoke",
            "Smoke test: forward/backward GRU, XGBoost, ONNX Runtime per device",
            "B0",
            "bench.workloads.smoke",
        ),
        Workload("W1", "Latih GRU (batch 256/1024/4096, fp32 vs AMP, pemuatan data)", "B2", "bench.workloads.w1_gru"),
        Workload("W2", "Latih XGBoost TTB 300 pohon (CPU hist vs cuda)", "B2", "bench.workloads.w2_xgb"),
        Workload(
            "W3",
            "Sweep hyperparameter Optuna (GRU 8 trial x 5 epoch; XGB 20 trial)",
            "B5",
            "bench.workloads.w3_sweep",
        ),
        Workload(
            "W4",
            "Ablation multi-seed (dengan/tanpa statistik, 5 seed x 10 epoch)",
            "B5",
            "bench.workloads.w4_ablation",
        ),
        Workload(
            "W5",
            "Skala data simulator (tidak dijalankan: simulator v4 tidak reproducible)",
            "B5",
            "bench.workloads.w5_skala",
        ),
        Workload("W6", "Sensor-health Berkeley: fitur + XGBoost CPU vs cuda", "B5", "bench.workloads.w6_berkeley"),
        Workload("W7", "Inferensi ONNX (CPU EP vs CUDA EP, batch 1/32/256/1024)", "B2", "bench.workloads.w7_onnx"),
        Workload(
            "W8", "Siklus inferensi end-to-end 24/100/500 truk (harness /analyze)", "B5", "bench.workloads.w8_siklus"
        ),
    ]
}
