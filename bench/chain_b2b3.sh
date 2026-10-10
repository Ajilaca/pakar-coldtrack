#!/usr/bin/env bash
# Rantai otomatis malam 2026-10-10/11: tambahan W1 b256_fp32_resident -> G2 final -> B3 sampai
# konfirmasi kandidat. Berhenti di langkah pertama yang gagal. Log: /tmp/chain_<langkah>.log
set -uo pipefail
cd "$(dirname "$0")/.."
R="bash bench/wsl_run.sh python -m"
langkah() {
    local nama="$1"; shift
    echo "=== MULAI $nama $(date +%H:%M:%S)"
    if "$@" > "/tmp/chain_${nama}.log" 2>&1; then
        echo "=== SELESAI $nama $(date +%H:%M:%S)"
    else
        echo "=== GAGAL $nama $(date +%H:%M:%S) (lihat /tmp/chain_${nama}.log)"; exit 1
    fi
}
langkah w1res_gpu $R bench.run --tag g16-gpu --workloads W1 --configs b256_fp32_resident
sleep 60
langkah w1res_cpu $R bench.run --tag g16-cpu --workloads W1 --configs b256_fp32_resident
langkah g2 $R bench.g2_check --cpu-tag g16-cpu --gpu-tag g16-gpu
langkah b3_diagnosis $R bench.b3_diagnosis --tag g16-gpu
langkah b3_sweep_gru $R bench.b3_sweep --tag g16-gpu --model gru --trials 60
langkah b3_sweep_xgb $R bench.b3_sweep --tag g16-gpu --model xgb --trials 60
langkah b3_confirm $R bench.b3_confirm --tag g16-gpu
echo "=== RANTAI SELESAI $(date +%H:%M:%S)"
