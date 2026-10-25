# Ekspor gambar block design KV260 (butuh build/kv260_bd dari kv260_bd.tcl) ke hw/docs/.
# write_bd_layout hanya jalan di mode GUI: vivado -mode gui -source synth/kv260_bd_image.tcl
set_param general.maxThreads 2
set hw  [file normalize [file join [file dirname [info script]] ..]]
open_project $hw/build/kv260_bd/coldtrack_kv260.xpr
open_bd_design [get_files coldtrack.bd]
write_bd_layout -force -format pdf -orientation landscape $hw/docs/vivado_block_design.pdf
write_bd_layout -force -format svg $hw/docs/vivado_block_design.svg
puts "SELESAI"
exit
