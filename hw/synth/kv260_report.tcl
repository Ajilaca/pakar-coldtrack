# Laporan dari hasil implementasi block design (dipisah dari kv260_bd.tcl agar hemat RAM): timing, resource, daya, .xsa
set_param general.maxThreads 2
set hw  [file normalize [file join [file dirname [info script]] ..]]
set out [file join $hw build kv260_bd]
open_checkpoint $out/coldtrack_kv260.runs/impl_1/coldtrack_wrapper_routed.dcp
report_utilization -file $out/util.txt
report_utilization -hierarchical -hierarchical_depth 3 -file $out/util_hier.txt
report_timing_summary -max_paths 10 -file $out/timing.txt
report_power -file $out/power.txt
puts "SELESAI WNS=[get_property SLACK [get_timing_paths -max_paths 1 -setup]]"
