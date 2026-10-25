# Vivado batch: sintesis + implementasi out-of-context untuk K26 (KV260), laporan timing/resource.
# Jalankan: cd hw && vivado -mode batch -source synth/kv260_vivado.tcl -tclargs [periode_ns] [model]
set periode [expr {[llength $argv] > 0 ? [lindex $argv 0] : 10.0}]
set model   [expr {[llength $argv] > 1 ? [lindex $argv 1] : "xgb_v5_context_duty"}]
set hw  [file normalize [file join [file dirname [info script]] ..]]
set out [file join $hw build vivado p$periode]
file mkdir $out
set_param general.maxThreads 2

read_verilog -sv [lsort [glob $hw/rtl/*.sv]]
set mem [file join $hw model $model]
set_property generic [list BERKAS_SIMPUL=\"$mem/nodes.mem\" BERKAS_POHON=\"$mem/trees.mem\" BERKAS_BASE=\"$mem/base.mem\"] [current_fileset]

file mkdir $out/xdc
set f [open $out/xdc/clk.xdc w]
puts $f "create_clock -name clk -period $periode \[get_ports clk\]"
close $f
read_xdc $out/xdc/clk.xdc

synth_design -top coldtrack_top -part xck26-sfvc784-2LV-c -mode out_of_context
write_checkpoint -force $out/sintesis.dcp
report_utilization -file $out/util_sintesis.txt
report_timing_summary -file $out/timing_sintesis.txt

opt_design
place_design
phys_opt_design
route_design
write_checkpoint -force $out/rute.dcp
report_utilization -file $out/util_routed.txt
report_timing_summary -max_paths 10 -file $out/timing_routed.txt
report_timing -max_paths 5 -sort_by slack -file $out/critical_paths.txt
report_clock_utilization -file $out/clock.txt
report_power -file $out/power.txt
puts "SELESAI WNS=[get_property SLACK [get_timing_paths -max_paths 1 -setup]]"
