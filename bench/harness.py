"""Kerangka protokol benchmark (bagian 5): pemanasan dibuang, >= 5 ulangan, jeda pendinginan,
telemetri per run, satu JSON per run.

  bench/results/<tag>/<workload>/<config>/run_<n>.json     n=0 pemanasan, 1..R terukur

Ulangan ke-i memakai seed SEEDS[i-1], sehingga ulangan sekaligus menjadi distribusi kualitas
antar-seed (gerbang G2). Konfigurasi yang sudah lengkap dilewati (resume), kecuali --overwrite.
"""

import time

from bench.common import git_info, now_iso, write_json
from bench.telemetry import Telemetri


def header(ctx, workload, config_id, config, n, seed, pemanasan):
    return {
        "workload": workload, "config_id": config_id, "konfigurasi": config,
        "tag": ctx.tag, "device": ctx.device, "run": n, "pemanasan": pemanasan, "seed": seed,
        "waktu_utc": now_iso(), "git": git_info(), "env": ctx.env_path,
        "kondisi_manual": ctx.profile.get("kondisi"),
        "protokol": {"repeats": getattr(ctx, "rep_eff", ctx.repeats), "warmup": getattr(ctx, "wu_eff", ctx.warmup),
                     "cooldown_s": ctx.cooldown_eff},
    }


def tidak_berlaku(ctx, workload, config_id, config, alasan):
    """Catat varian yang tidak bermakna di device ini (mis. AMP di CPU) -- bukan dikosongkan diam-diam."""
    path = ctx.out_root / workload / config_id / "tidak_berlaku.json"
    write_json(path, {"workload": workload, "config_id": config_id, "konfigurasi": config, "tag": ctx.tag,
                      "status": "tidak berlaku", "alasan": alasan, "waktu_utc": now_iso()})
    print(f"  {config_id}: tidak berlaku ({alasan})")
    return [path]


def run_config(ctx, workload, config_id, config, fn, cooldown=None, repeats=None, warmup=None):
    """fn(seed, pemanasan) -> dict hasil (waktu, metrik, ...). Kembalikan daftar berkas JSON.

    repeats/warmup menimpa protokol bawaan untuk workload yang satu run-nya sudah berisi banyak
    pelatihan (W3 sweep, W4 ablation): variasinya tercatat di dalam run (per trial / per seed).
    """
    ctx.cooldown_eff = ctx.cooldown if cooldown is None else cooldown
    d = ctx.out_root / workload / config_id
    rep = ctx.repeats if repeats is None else repeats
    wu = ctx.warmup if warmup is None else warmup
    ctx.rep_eff, ctx.wu_eff = rep, wu
    n_total = wu + rep
    if not getattr(ctx, "overwrite", False) and all((d / f"run_{n}.json").exists() for n in range(n_total)):
        print(f"  {config_id}: sudah lengkap, dilewati (pakai --overwrite untuk mengulang)")
        return []

    files = []
    for n in range(n_total):
        pemanasan = n < wu
        seed = ctx.seeds[0] if pemanasan else ctx.seeds[(n - wu) % len(ctx.seeds)]
        if n > 0 and ctx.cooldown_eff:
            time.sleep(ctx.cooldown_eff)
        label = "pemanasan" if pemanasan else f"ulangan {n - wu + 1}/{rep}"
        print(f"  {config_id} [{label}, seed {seed}]", flush=True)
        with Telemetri(ctx.tag, f"{workload}_{config_id}_run{n}") as tel:
            t0 = time.perf_counter()
            hasil = fn(seed=seed, pemanasan=pemanasan)
            dinding = time.perf_counter() - t0
        out = header(ctx, workload, config_id, config, n, seed, pemanasan) | hasil
        out["waktu"] = out.get("waktu", {}) | {"dinding_total_s": dinding}
        out["telemetri"] = tel.ringkas
        files.append(write_json(d / f"run_{n}.json", out))
        ringkas = {k: round(v, 2) for k, v in out["waktu"].items() if isinstance(v, (int, float))}
        print(f"    waktu: {ringkas}", flush=True)
    return files


