#!/usr/bin/env bash
# Paket sistem Ubuntu 24.04 (WSL) untuk LibreLane mode dockerized.
set -euo pipefail

sudo apt-get update
sudo apt-get install -y git curl ca-certificates python3 python3-venv python3-pip python3-tk

python3 --version
git --version
