# Vivado batch: block design KV260 = Zynq UltraScale+ PS (preset board) + coldtrack_axil di M_AXI_HPM0_FPD,
# clock PL 100 MHz, lalu bitstream dan .xsa untuk PetaLinux / driver ARM.
# Jalankan: cd hw && vivado -mode batch -source synth/kv260_bd.tcl -tclargs [model]
set model [expr {[llength $argv] > 0 ? [lindex $argv 0] : "xgb_v5_context_duty"}]
set hw  [file normalize [file join [file dirname [info script]] ..]]
set out [file join $hw build kv260_bd]
set mem [file join $hw model $model]
# hemat RAM (laptop 7,5 GB): satu run, IP block design disintesis global (tanpa run OOC paralel), maks 2 thread
set_param general.maxThreads 2

create_project -force coldtrack_kv260 $out -part xck26-sfvc784-2LV-c
set_property board_part [lindex [lsort [get_board_parts xilinx.com:kv260_som:part0:*]] end] [current_project]
add_files [lsort [glob $hw/rtl/*.sv]]
add_files $hw/bd/coldtrack_axil.v
add_files -fileset constrs_1 $hw/bd/kv260_alarm.xdc
update_compile_order -fileset sources_1

create_bd_design coldtrack
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e zynq_ps]
apply_bd_automation -rule xilinx.com:bd_rule:zynq_ultra_ps_e -config {apply_board_preset "1"} $ps
set_property -dict [list \
    CONFIG.PSU__USE__M_AXI_GP0 {1} CONFIG.PSU__USE__M_AXI_GP1 {0} CONFIG.PSU__USE__M_AXI_GP2 {0} \
    CONFIG.PSU__MAXIGP0__DATA_WIDTH {32} \
    CONFIG.PSU__FPGA_PL0_ENABLE {1} CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ {100}] $ps

set ct [create_bd_cell -type module -reference coldtrack_axil coldtrack]
set_property -dict [list \
    CONFIG.BERKAS_SIMPUL "\"$mem/nodes.mem\"" \
    CONFIG.BERKAS_POHON  "\"$mem/trees.mem\"" \
    CONFIG.BERKAS_BASE   "\"$mem/base.mem\""] $ct

# clock PL dari PS langsung (tanpa clocking wizard); automation lalu memakai domain ini
connect_bd_net [get_bd_pins zynq_ps/pl_clk0] [get_bd_pins coldtrack/aclk] [get_bd_pins zynq_ps/maxihpm0_fpd_aclk]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list \
    Clk_master {Auto} Clk_slave {Auto} Clk_xbar {Auto} \
    Master {/zynq_ps/M_AXI_HPM0_FPD} Slave {/coldtrack/s_axi} intc_ip {New AXI SmartConnect} \
    master_apm {0}] [get_bd_intf_pins coldtrack/s_axi]
foreach a {alarm_waspada alarm_kritis alarm_sensor} {
    make_bd_pins_external [get_bd_pins coldtrack/$a]
    set_property name $a [get_bd_ports ${a}_0]
}
# 4 KB di alamat dasar HPM0 (0xA000_0000)
set seg [get_bd_addr_segs -of_objects [get_bd_addr_spaces zynq_ps/Data] -filter {NAME =~ *coldtrack*}]
set_property offset 0xA0000000 $seg
set_property range 4K $seg

validate_bd_design
save_bd_design
set bd [get_files coldtrack.bd]
set_property synth_checkpoint_mode None $bd
generate_target all $bd
make_wrapper -files $bd -top
add_files -norecurse [file join $out coldtrack_kv260.gen sources_1 bd coldtrack hdl coldtrack_wrapper.v]
set_property top coldtrack_wrapper [current_fileset]
update_compile_order -fileset sources_1

# run anak (synth_1, impl_1) adalah proses Vivado terpisah: batas thread lewat skrip pre-hook
set kait [file join $out batas_thread.tcl]
set f [open $kait w]; puts $f "set_param general.maxThreads 2"; close $f
set_property STEPS.SYNTH_DESIGN.TCL.PRE $kait [get_runs synth_1]
foreach langkah {OPT_DESIGN PLACE_DESIGN ROUTE_DESIGN} { set_property STEPS.$langkah.TCL.PRE $kait [get_runs impl_1] }
launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1
open_run impl_1
report_utilization -file $out/util.txt
report_utilization -hierarchical -hierarchical_depth 3 -file $out/util_hier.txt
report_timing_summary -max_paths 10 -file $out/timing.txt
report_power -file $out/power.txt
write_hw_platform -fixed -include_bit -force $out/coldtrack_kv260.xsa
puts "SELESAI WNS=[get_property SLACK [get_timing_paths -max_paths 1 -setup]] STATUS=[get_property STATUS [get_runs impl_1]]"
