# Disisipkan ke tiap corner STA LibreLane (STA_EXTRA_CORNER_TCL_FILE): untuk corner ff, tulis semua endpoint
# dengan slack hold < HOLD_MARGIN (default 0,05 ns), satu baris per endpoint: "endpoint slack startpoint".
if {[string match "*ff*" $corner_name]} {
  set margin 0.05
  if {[info exists ::env(HOLD_MARGIN)]} { set margin $::env(HOLD_MARGIN) }
  set out [file normalize [file join [file dirname [info script]] .. runs _hold]]
  file mkdir $out
  set f [open "$out/hold_${corner_name}.txt" w]
  foreach path [find_timing_paths -unique_paths_to_endpoint -path_delay min -sort_by_slack -group_path_count 200000 -slack_max $margin -corner $corner_name] {
    puts $f "[get_full_name [get_property $path endpoint]] [get_property $path slack] [get_full_name [get_property $path startpoint]]"
  }
  close $f
  puts "holdall: [file tail $out/hold_${corner_name}.txt] ditulis"
}
