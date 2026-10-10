"""Catat lingkungan device secara otomatis -- spesifikasi TIDAK boleh ditulis dari ingatan.

Yang dicatat: model CPU + core, RAM (total & tersedia saat run), GPU (nama, VRAM, driver, CUDA)
dari nvidia-smi, versi Python/torch/xgboost/onnxruntime, OS/WSL (+ isi .wslconfig), skema daya
dan status charger, hash commit git, hash berkas data.

Yang tidak bisa dibaca program (mode Armoury Crate, cooling pad) diambil dari bagian `kondisi`
di bench/devices/<device>.yaml dan ditandai sebagai isian manual.

Menjalankan: python -m bench.env_capture --tag g16-gpu
"""

import argparse
import os
import platform
import re
import sys

from bench.common import (
    RESULTS_DIR,
    data_info,
    git_info,
    is_wsl,
    now_iso,
    powershell,
    run_cmd,
    write_json,
)


def _nvidia_smi_exe():
    for cand in ["nvidia-smi", "/usr/lib/wsl/lib/nvidia-smi"]:
        if run_cmd([cand, "-L"]) is not None:
            return cand
    return None


def cpu_info():
    import psutil

    name = None
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/cpuinfo", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("model name"):
                        name = line.split(":", 1)[1].strip()
                        break
        except OSError:
            pass
    elif sys.platform == "win32":
        name = powershell("(Get-CimInstance Win32_Processor).Name")
    elif sys.platform == "darwin":
        name = run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"])

    freq = psutil.cpu_freq()
    return {
        "model": name or platform.processor() or None,
        "logical_cores": psutil.cpu_count(logical=True),
        "physical_cores": psutil.cpu_count(logical=False),
        # Di Windows psutil melaporkan clock dasar, bukan boost -- jangan dibaca sebagai clock puncak
        "freq_max_dilaporkan_os_mhz": round(freq.max) if freq and freq.max else None,
    }


def memory_info():
    import psutil

    vm = psutil.virtual_memory()
    if vm.available < 4 * 2**30:
        print(f"PERINGATAN: RAM tersedia hanya {vm.available / 2**30:.1f} GB -- tutup aplikasi berat sebelum benchmark")
    out = {
        # Di WSL2 ini adalah batas memori VM (bukan RAM fisik laptop) -- itu yang relevan untuk run
        "total_gb": round(vm.total / 2**30, 2),
        "available_gb_saat_capture": round(vm.available / 2**30, 2),
    }
    if sys.platform == "win32" or is_wsl():
        host = powershell("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory")
        out["host_physical_gb"] = round(int(host) / 2**30, 2) if host and host.isdigit() else None
    return out


def gpu_info():
    exe = _nvidia_smi_exe()
    if exe is None:
        return {"nvidia_smi": False}

    # enforced.power.limit berubah mengikuti mode daya (Armoury Crate) -- kondisi penting untuk run
    fields = ["name", "memory.total", "driver_version", "enforced.power.limit", "power.max_limit",
              "clocks.max.sm", "clocks.max.mem", "pcie.link.gen.max", "pcie.link.width.max"]
    raw = run_cmd([exe, f"--query-gpu={','.join(fields)}", "--format=csv,noheader,nounits"])
    gpus = []
    for line in (raw or "").splitlines():
        vals = [v.strip() for v in line.split(",")]
        gpus.append(dict(zip(fields, vals)))

    header = run_cmd([exe]) or ""
    m = re.search(r"CUDA Version:\s*([\d.]+)", header)
    return {"nvidia_smi": True, "driver_cuda_version": m.group(1) if m else None, "gpus": gpus}


def os_info():
    out = {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "wsl": is_wsl(),
    }
    if sys.platform.startswith("linux"):
        try:
            with open("/etc/os-release", encoding="utf-8") as f:
                kv = dict(line.rstrip().split("=", 1) for line in f if "=" in line)
            out["distro"] = kv.get("PRETTY_NAME", "").strip('"')
        except OSError:
            pass
    if sys.platform == "win32" or is_wsl():
        out["windows"] = powershell(
            "$o = Get-CimInstance Win32_OperatingSystem; \"$($o.Caption) build $($o.BuildNumber)\"")
        out["machine"] = powershell(
            "$c = Get-CimInstance Win32_ComputerSystem; \"$($c.Manufacturer) $($c.Model)\"")
    if is_wsl():
        # None berarti .wslconfig tidak ada -> WSL memakai batas memori bawaan
        out["wslconfig"] = powershell("Get-Content -Raw $env:USERPROFILE\\.wslconfig")
    return out


def power_info():
    out = {"skema_daya_windows": None, "charger_terpasang": None}
    if sys.platform == "win32" or is_wsl():
        out["skema_daya_windows"] = powershell("powercfg /getactivescheme")
        ac = powershell("(Get-CimInstance -Namespace root/wmi -ClassName BatteryStatus).PowerOnline")
        if ac:
            out["charger_terpasang"] = ac.splitlines()[0].strip().lower() == "true"
    elif sys.platform.startswith("linux"):
        import glob

        for p in glob.glob("/sys/class/power_supply/*"):
            try:
                with open(f"{p}/type") as f:
                    if f.read().strip() != "Mains":
                        continue
                with open(f"{p}/online") as f:
                    out["charger_terpasang"] = f.read().strip() == "1"
            except OSError:
                continue
    return out


def frameworks_info():
    out = {"python": platform.python_version()}
    for mod in ["numpy", "pandas", "sklearn", "torch", "xgboost", "onnxruntime", "onnx", "optuna"]:
        try:
            out[mod] = __import__(mod).__version__
        except ImportError:
            out[mod] = None

    try:
        import torch

        t = {
            "cuda_available": torch.cuda.is_available(),
            "torch_cuda": torch.version.cuda,
            "cudnn": torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None,
            "num_threads": torch.get_num_threads(),
            "arch_list": torch.cuda.get_arch_list() if torch.version.cuda else [],
        }
        if t["cuda_available"]:
            cap = torch.cuda.get_device_capability(0)
            t["device_name"] = torch.cuda.get_device_name(0)
            t["capability"] = f"sm_{cap[0]}{cap[1]}"
            t["arch_cocok"] = t["capability"] in t["arch_list"]
            t["vram_total_gb"] = round(torch.cuda.get_device_properties(0).total_memory / 2**30, 2)
        out["torch_detail"] = t
    except ImportError:
        pass

    try:
        import onnxruntime as ort

        out["onnxruntime_providers"] = ort.get_available_providers()
    except ImportError:
        pass

    try:
        import xgboost as xgb

        out["xgboost_use_cuda"] = bool(xgb.build_info().get("USE_CUDA"))
    except (ImportError, AttributeError):
        pass
    return out


def capture(tag, profile=None):
    env_vars = ["CUDA_VISIBLE_DEVICES", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "CUBLAS_WORKSPACE_CONFIG"]
    return {
        "tag": tag,
        "waktu_utc": now_iso(),
        "git": git_info(),
        "data": data_info(),
        "os": os_info(),
        "cpu": cpu_info(),
        "memori": memory_info(),
        "gpu": gpu_info(),
        "daya": power_info(),
        "framework": frameworks_info(),
        "env_vars": {k: os.environ.get(k) for k in env_vars},
        # isian manual dari bench/devices/<device>.yaml (tidak bisa dibaca program)
        "kondisi_manual": (profile or {}).get("kondisi"),
        "lingkungan_dipilih": (profile or {}).get("lingkungan"),
    }


def main(argv=None):
    from bench.run import apply_device_env, resolve_tag

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tag", required=True)
    a = ap.parse_args(argv)

    profile, kind = resolve_tag(a.tag)
    apply_device_env(kind)
    env = capture(a.tag, profile)
    path = write_json(RESULTS_DIR / a.tag / "env.json", env)

    import json

    print(json.dumps(env, indent=2, ensure_ascii=False, default=str))
    print(f"\nTersimpan: {path}")


if __name__ == "__main__":
    main()
