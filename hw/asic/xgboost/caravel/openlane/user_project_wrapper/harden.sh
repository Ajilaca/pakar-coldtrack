#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Faza Dzil
# SPDX-License-Identifier: Apache-2.0
#
# Harden user_project_wrapper ColdTrack dengan LibreLane (dockerized) dalam dua tahap:
#   1. sampai OpenROAD.GeneratePDN (PDN dari pdn_ct.tcl, grid berimpit dengan grid daya makro);
#   2. pdn_bridge.tcl menutup celah strap ke pin daya makro, lalu flow dilanjutkan dari Odb.RemovePDNObstructions.
# Pemakaian: harden.sh <run_tag>   (LIBRELANE = perintah python librelane, bawaan python3 -m librelane)
# LibreLane 3.0.17 + PDK sky130A yang sama dengan layout makro (pakar-coldtrack hw/asic/xgboost/layout).
set -euo pipefail
cd "$(dirname "$0")"
TAG=${1:?run tag}
LL=${LIBRELANE:-python3 -m librelane}
IMG=${LIBRELANE_IMAGE:-ghcr.io/librelane/librelane:3.0.17}

$LL --docker-no-tty --dockerized --run-tag "$TAG" --overwrite --to OpenROAD.GeneratePDN config.json
R=runs/$TAG
D=$(ls -d "$R"/*-openroad-generatepdn | tail -1)
B=$R/_bridge
mkdir -p "$B"
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:$PWD" -w "$PWD" \
    -e ODB_IN="$PWD/$D/user_project_wrapper.odb" -e ODB_OUT="$PWD/$B/user_project_wrapper.odb" \
    -e PSM_OUT="$PWD/$B/psm.txt" "$IMG" openroad -exit -no_splash "$PWD/pdn_bridge.tcl"
# state baru: ODB berjembatan, metrik pelanggaran grid net yang kini tersambung di-nolkan
python3 - "$D/state_out.json" "$PWD/$B/user_project_wrapper.odb" "$B/state_in.json" "$B/psm.txt" <<'EOF'
import json, sys
s = json.load(open(sys.argv[1]))
s["odb"] = sys.argv[2]
m = s["metrics"]
for baris in open(sys.argv[4]):
    net, ok = baris.split()
    if ok == "1":
        m[f"design__power_grid_violation__count__net:{net}"] = 0
m["design__power_grid_violation__count"] = sum(v for k, v in m.items()
                                               if k.startswith("design__power_grid_violation__count__net:"))
json.dump(s, open(sys.argv[3], "w"), indent=2)
EOF
$LL --docker-no-tty --dockerized --run-tag "${TAG}_full" --overwrite --with-initial-state "$B/state_in.json" \
    --from Odb.RemovePDNObstructions ${HARDEN_TO:+--to "$HARDEN_TO"} config.json
