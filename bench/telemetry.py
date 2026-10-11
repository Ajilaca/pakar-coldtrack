"""Perekam telemetri GPU selama run: nvidia-smi tiap 1 detik ke CSV, lalu ringkasan.

  with Telemetri(ctx.tag, "W1_b256_fp32_run1") as tel:
      ...latih...
  ringkas = tel.ringkas      # energi Wh, daya/suhu/clock puncak & median, VRAM puncak

CSV mentah disimpan di bench/results/telemetry/ (tidak dikomit); JSON hasil menyimpan path-nya
dan ringkasannya. Di device tanpa nvidia-smi (d0-old) perekam menjadi no-op dan ringkasan
bertanda "tidak berlaku".
"""

import csv
import subprocess
import time

from bench.common import RESULTS_DIR, rel, stamp

FIELDS = ["timestamp", "power.draw", "temperature.gpu", "clocks.sm", "utilization.gpu", "memory.used",
          "clocks_throttle_reasons.active"]


def _exe():
    from bench.env_capture import _nvidia_smi_exe

    return _nvidia_smi_exe()


class Telemetri:
    def __init__(self, tag, nama, interval_ms=1000):
        self.exe = _exe()
        self.path = RESULTS_DIR / "telemetry" / tag / f"{nama}_{stamp()}.csv"
        self.interval_ms = interval_ms
        self.proc = None
        self.ringkas = {"tersedia": False}

    def __enter__(self):
        if self.exe is None:
            return self
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._f = open(self.path, "w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [self.exe, f"--query-gpu={','.join(FIELDS)}", "--format=csv,noheader,nounits",
             f"-lms={self.interval_ms}"],
            stdout=self._f, stderr=subprocess.DEVNULL)
        self.t0 = time.time()
        return self

    def __exit__(self, *exc):
        if self.proc is None:
            return False
        time.sleep(self.interval_ms / 1000 * 1.5)       # pastikan sampel terakhir tertangkap
        self.proc.terminate()
        self.proc.wait(timeout=10)
        self._f.close()
        self.ringkas = ringkas_csv(self.path, self.interval_ms / 1000)
        self.ringkas["csv"] = rel(self.path)
        return False


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def ringkas_csv(path, dt):
    import numpy as np

    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.reader(f):
            if len(r) == len(FIELDS):
                rows.append(dict(zip(FIELDS, (v.strip() for v in r))))
    if not rows:
        return {"tersedia": False, "catatan": "tidak ada sampel"}

    def col(k):
        v = np.array([x for x in (_num(r[k]) for r in rows) if x is not None])
        return v if len(v) else np.array([np.nan])

    p, t, c, u, m = (col(k) for k in ["power.draw", "temperature.gpu", "clocks.sm", "utilization.gpu",
                                      "memory.used"])
    throttle = sorted({r["clocks_throttle_reasons.active"] for r in rows})
    return {
        "tersedia": True,
        "n_sampel": len(rows),
        "energi_wh": float(np.nansum(p) * dt / 3600),       # integral daya, sampel tiap dt detik
        "daya_w": {"median": float(np.nanmedian(p)), "maks": float(np.nanmax(p))},
        "suhu_c": {"median": float(np.nanmedian(t)), "maks": float(np.nanmax(t))},
        "clock_sm_mhz": {"median": float(np.nanmedian(c)), "min": float(np.nanmin(c)),
                         "p5": float(np.nanpercentile(c, 5))},
        "utilisasi_pct_median": float(np.nanmedian(u)),
        "vram_terpakai_mb_maks": float(np.nanmax(m)),
        "throttle_reasons_hex": throttle,
    }
