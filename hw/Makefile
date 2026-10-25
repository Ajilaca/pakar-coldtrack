# ColdTrack RTL. Alat dari OSS CAD Suite (~/FPGA/tools/oss-cad-suite), Python dari .venv repo.
OSS    ?= $(HOME)/FPGA/tools/oss-cad-suite
PY     ?= $(abspath ../.venv/bin/python)
SIM    ?= verilator
TOP    ?= segel
export PATH := $(OSS)/bin:$(PATH)

RTL := $(wildcard rtl/*.sv)

.PHONY: lint test synth clean

lint:
	verilator --lint-only -Wall -Wno-DECLFILENAME --top-module $(TOP) $(RTL)

test:
	cd tb && SIM=$(SIM) $(PY) -m pytest -q

synth:
	mkdir -p build
	yosys -q -l build/synth_$(TOP).log -p "read_verilog -sv $(RTL); synth_xilinx -family xcup -top $(TOP); tee -o build/util_$(TOP).txt stat"
	@tail -n 40 build/util_$(TOP).txt

clean:
	rm -rf build tb/__pycache__ tb/results.xml
