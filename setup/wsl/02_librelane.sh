#!/usr/bin/env bash
# LibreLane di virtualenv .venv (root repo), cek Docker, lalu smoke test mode dockerized. Image Docker berisi
# Yosys, OpenROAD, Magic, KLayout, dan Netgen; PDK sky130 diunduh LibreLane sendiri (beberapa GB, sekali saja).
# Butuh Docker Desktop menyala dengan WSL Integration. Jalankan dari root repo.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install librelane==3.0.17

if ! docker info >/dev/null 2>&1; then
    echo "Docker tidak terjangkau dari WSL. Nyalakan Docker Desktop dan aktifkan"
    echo "Settings > Resources > WSL Integration > Ubuntu-24.04, lalu jalankan skrip ini lagi."
    exit 1
fi
docker run --rm hello-world >/dev/null && echo "Docker OK"

.venv/bin/python -m librelane --dockerized --smoke-test
