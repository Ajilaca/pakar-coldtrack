# ECO layout ColdTrack (OpenROAD Tcl, semua masukan lewat env). Dipakai sebelum GRT, atau sesudah DRT dengan POST_ROUTE=1.
#  (0)  DIODE_SPLIT: repeater buf_4 di titik tengah net panjang (daftar nama driver); maks 8 dioda lama tetap di net masukan
#  (0b) DIODE_REBAL: dioda di net keluaran buffer yang kelebihan beban dipindah ke net masukannya
#  (1)  pecah net dengan beban > MAX_FO (dioda ikut dihitung), dan net di FORCE_PINS bila beban > FORCE_FO
#  (2)  UPSIZE_PINS: perbesar driver pelanggar slew; dengan UPSIZE_AS_BUF, beri buf_4 di belakang driver
#  (2c) global: perbesar driver lemah dengan HPWL > WEAK_HPWL, buffer di belakang dlygate dengan HPWL > DLY_HPWL
#  (3)  MOVE_NEAR: pindahkan buffer ke dekat pin makro yang didorongnya
#  (4)  HOLD_LIST "inst pin jumlah": rantai sel tunda (HOLD_CELL, default dlygate4sd3_1) di depan pin
# Dioda antena tidak pernah dihapus (KEEP_DIODES): menghapusnya membuat repair_antennas OpenROAD crash.
read_db $::env(ODB_IN)
read_liberty $::env(SC_LIB)
read_liberty $::env(RAM_LIB)
set db [ord::get_db]
set block [ord::get_db_block]
set vpwr [$block findNet VPWR]
set vgnd [$block findNet VGND]
set tag $::env(ECO_TAG)
set bufm [$db findMaster sky130_fd_sc_hd__buf_4]
set dly [$db findMaster sky130_fd_sc_hd__dlygate4sd3_1]
# HOLD_CELL: sel tunda yang lebih pendek untuk menutup selisih hold kecil (mis. dlygate4sd1_1)
if {[info exists ::env(HOLD_CELL)]} { set dly [$db findMaster $::env(HOLD_CELL)] }

# POST_ROUTE: ECO pada layout yang sudah di-route. Sel lama dikunci (FIRM) supaya legalisasi hanya menggeser sel baru,
# dan kabel hanya dihapus pada net yang diubah; DRT berikutnya mempertahankan routing net lain.
set post [info exists ::env(POST_ROUTE)]
set touched [dict create]
proc touch {args} { global touched; foreach n $args { dict set touched [$n getName] $n } }
set locked {}
if {$post} {
  foreach inst [$block getInsts] {
    if {[$inst getPlacementStatus] eq "PLACED"} { $inst setPlacementStatus FIRM; lappend locked $inst }
  }
}

proc pwr {inst} {
  global vpwr vgnd
  foreach p {VPWR VPB} { set t [$inst findITerm $p]; if {$t ne "NULL"} { $t connect $vpwr } }
  foreach p {VGND VNB} { set t [$inst findITerm $p]; if {$t ne "NULL"} { $t connect $vgnd } }
}
proc readlist {path} {
  if {![file exists $path]} { return {} }
  set f [open $path]; set l [split [string trim [read $f]] "\n"]; close $f
  return $l
}
proc net_info {net} {
  set drv ""; set loads {}; set clocky 0
  foreach t [$net getITerms] {
    if {[$t isOutputSignal]} { set drv $t; continue }
    if {![$t isInputSignal]} continue
    if {[[$t getMTerm] getName] eq "CLK"} { set clocky 1 }
    lappend loads $t
  }
  return [list $drv $loads $clocky]
}
set nb 0
proc split_net {net drv loads max} {
  global block bufm tag nb
  set fo [llength $loads]
  set loads [lsort -command {apply {{a b} {
    set pa [$a getAvgXY]; set pb [$b getAvgXY]
    set d [expr {[lindex $pa 2] - [lindex $pb 2]}]
    if {$d == 0} { set d [expr {[lindex $pa 1] - [lindex $pb 1]}] }
    return [expr {$d < 0 ? -1 : ($d > 0 ? 1 : 0)}]
  }}} $loads]
  set ng [expr {($fo + $max - 1) / $max}]
  set per [expr {($fo + $ng - 1) / $ng}]
  for {set g 0} {$g < $ng} {incr g} {
    set grp [lrange $loads [expr {$g * $per}] [expr {($g + 1) * $per - 1}]]
    if {[llength $grp] == 0} continue
    set nn [odb::dbNet_create $block "${tag}_fo_net_$nb"]
    touch $net $nn
    set b [odb::dbInst_create $block $bufm "${tag}_fo_$nb"]
    [$b findITerm A] connect $net
    [$b findITerm X] connect $nn
    pwr $b
    set sx 0; set sy 0
    foreach t $grp { $t disconnect; $t connect $nn; set xy [$t getAvgXY]; incr sx [lindex $xy 1]; incr sy [lindex $xy 2] }
    set k [llength $grp]
    $b setLocation [expr {$sx / $k}] [expr {$sy / $k}]
    $b setPlacementStatus PLACED
    incr nb
  }
  puts "SPLIT [[$drv getInst] getName] fo=$fo -> $ng x <=$per"
}

set done [dict create]
set sp 0

# (0) net panjang yang di run sebelumnya menumpuk dioda: cabut dioda, belah dua secara geometris dengan buffer
set nd_rm 0
if {[info exists ::env(DIODE_SPLIT)]} {
  foreach dn [readlist $::env(DIODE_SPLIT)] {
    set dn [string trim $dn]; if {$dn eq ""} continue
    set inst [$block findInst $dn]; if {$inst eq "NULL"} { puts "SKIP dsplit $dn"; continue }
    set out ""; foreach t [$inst getITerms] { if {[$t isOutputSignal]} { set out $t } }
    if {$out eq ""} continue
    set net [$out getNet]
    if {[dict exists $done [$net getName]]} continue
    if {![info exists ::env(KEEP_DIODES)]} {
      foreach t [$net getITerms] {
        set ci [$t getInst]
        if {[string match "*diode*" [[$ci getMaster] getName]]} { odb::dbInst_destroy $ci; incr nd_rm }
      }
    }
    lassign [net_info $net] drv loads clocky
    if {$drv eq "" || $clocky || [llength $loads] == 0} continue
    dict set done [$net getName] 1
    # repeater di tengah antara driver dan pusat beban: tiap potongan kabel kira-kira setengahnya
    set dxy [$drv getAvgXY]; set sx 0; set sy 0
    foreach t $loads { set xy [$t getAvgXY]; incr sx [lindex $xy 1]; incr sy [lindex $xy 2] }
    set k [llength $loads]
    set mx [expr {([lindex $dxy 1] + $sx / $k) / 2}]; set my [expr {([lindex $dxy 2] + $sy / $k) / 2}]
    set nn [odb::dbNet_create $block "${tag}_rp_net_$nb"]
    touch $net $nn
    set b [odb::dbInst_create $block $bufm "${tag}_rp_$nb"]
    # dioda antena lama ikut dihitung sebagai beban: sebagian (maks 8) tetap di net masukan repeater
    # supaya kedua potongan net tidak melebihi batas fanout
    set nkeep 0
    foreach t $loads {
      if {[string match "*diode*" [[[$t getInst] getMaster] getName]] && $nkeep < 8} { incr nkeep; continue }
      $t disconnect; $t connect $nn
    }
    [$b findITerm A] connect $net; [$b findITerm X] connect $nn
    pwr $b
    $b setLocation $mx $my; $b setPlacementStatus PLACED
    incr nb; incr sp
    puts "REPEAT [[$drv getInst] getName] fo=$k"
  }
}
puts "ECOW: dioda dicabut $nd_rm"

# (0b) DIODE_REBAL: buffer di daftar yang net keluarannya kelebihan beban karena dioda;
#      dioda dipindah ke net masukan buffer sampai keluaran <= 8 beban dan masukan <= 9 beban
if {[info exists ::env(DIODE_REBAL)]} {
  foreach name [readlist $::env(DIODE_REBAL)] {
    set name [string trim $name]; if {$name eq ""} continue
    set inst [$block findInst $name]; if {$inst eq "NULL"} { puts "SKIP rebal $name"; continue }
    set a [$inst findITerm A]; set x [$inst findITerm X]
    if {$a eq "NULL" || $x eq "NULL"} { puts "SKIP rebal $name (bukan buffer)"; continue }
    set in [$a getNet]; set out [$x getNet]
    lassign [net_info $in] d1 lin c1; lassign [net_info $out] d2 lout c2
    set nin [llength $lin]; set nout [llength $lout]; set mv 0
    foreach t $lout {
      if {$nout <= 8 || $nin >= 9} break
      if {![string match "*diode*" [[[$t getInst] getMaster] getName]]} continue
      $t disconnect; $t connect $in; incr nout -1; incr nin; incr mv
    }
    if {$mv} { touch $in $out }
    puts "REBAL $name: $mv dioda dipindah, masukan $nin, keluaran $nout"
  }
}

# (1a) net yang dipaksa (pelanggar fanout pasca-DRT: DRT menambah dioda sesudah state ini)
foreach s [readlist $::env(FORCE_PINS)] {
  set s [string trim $s]; if {$s eq ""} continue
  set i [string last "/" $s]
  set inst [$block findInst [string range $s 0 [expr {$i-1}]]]
  if {$inst eq "NULL"} { puts "SKIP force $s"; continue }
  set net [[$inst findITerm [string range $s [expr {$i+1}] end]] getNet]
  lassign [net_info $net] drv loads clocky
  if {$drv eq "" || $clocky} continue
  dict set done [$net getName] 1
  if {[llength $loads] > $::env(FORCE_FO)} { split_net $net $drv $loads $::env(FORCE_FO); incr sp }
}
# (1b) semua net dengan beban > MAX_FO
foreach net [$block getNets] {
  if {[$net isSpecial] || [dict exists $done [$net getName]]} continue
  set st [$net getSigType]
  if {$st eq "POWER" || $st eq "GROUND" || $st eq "CLOCK"} continue
  if {[string match "*clk*" [$net getName]] || [llength [$net getBTerms]] > 0} continue
  lassign [net_info $net] drv loads clocky
  if {$drv eq "" || $clocky} continue
  if {[string match "*clk*" [[[$drv getInst] getMaster] getName]]} continue
  if {[llength $loads] > $::env(MAX_FO)} { split_net $net $drv $loads $::env(MAX_FO); incr sp }
}
puts "ECOW: split $sp net, $nb buffer"

# (2) upsize driver pelanggar slew
set sizes {1 2 4 6 8 12 16}
set up 0; set seen [dict create]
foreach s [readlist $::env(UPSIZE_PINS)] {
  set s [string trim $s]; if {$s eq ""} continue
  set i [string last "/" $s]
  set inst [$block findInst [string range $s 0 [expr {$i-1}]]]; if {$inst eq "NULL"} continue
  set it [$inst findITerm [string range $s [expr {$i+1}] end]]; if {$it eq "NULL"} continue
  set d $it
  if {![$it isOutputSignal]} { set d "NULL"; foreach t [[$it getNet] getITerms] { if {[$t isOutputSignal]} { set d $t } } }
  if {$d eq "NULL"} continue
  set dinst [$d getInst]; set dname [$dinst getName]
  if {[dict exists $seen $dname]} continue
  dict set seen $dname 1
  set m [[$dinst getMaster] getName]
  # UPSIZE_AS_BUF: semua driver di daftar diberi buffer di belakangnya, tidak diperbesar
  # (memperbesar mempercepat jalur dan bisa merusak hold; buffer menambah tunda, setup masih longgar)
  if {[string match "*dlygate*" $m] || ([info exists ::env(UPSIZE_AS_BUF)] && ![string match "*clk*" $dname])} {
    # driver lemah: buffer tepat di belakangnya, dlygate hanya mendorong buffer itu
    set net [$d getNet]
    set nn [odb::dbNet_create $block "${tag}_db_net_$up"]
    touch $net $nn
    set b [odb::dbInst_create $block $bufm "${tag}_db_$up"]
    foreach t [$net getITerms] { if {$t ne $d && [$t isInputSignal]} { $t disconnect; $t connect $nn } }
    [$b findITerm A] connect $net; [$b findITerm X] connect $nn
    pwr $b
    set loc [$dinst getLocation]; $b setLocation [lindex $loc 0] [lindex $loc 1]; $b setPlacementStatus PLACED
    puts "DRVBUF $dname $m -> ${tag}_db_$up"; incr up; continue
  }
  if {![regexp {^(sky130_fd_sc_hd__.+)_([0-9]+)$} $m -> base n] || [string match "*clk*" $m]} { puts "SKIP upsize $dname $m"; continue }
  set target ""
  foreach z $sizes { if {$z > $n} { set cand [$db findMaster "${base}_$z"]; if {$cand ne "NULL"} { set target $cand; if {$z >= 4*$n} break } } }
  if {$target eq ""} { puts "SKIP upsize $dname $m (terbesar)"; continue }
  $dinst swapMaster $target
  puts "UPSIZE $dname $m -> [$target getName]"; incr up
}

# (2c) global: driver ukuran <= 2 dengan HPWL net > WEAK_HPWL diperbesar ke >= 4;
#      driver dlygate dengan HPWL > DLY_HPWL diberi buffer di belakangnya
set gu 0; set gb 0
if {[info exists ::env(WEAK_HPWL)]} {
  set dbu [$block getDbUnitsPerMicron]
  set weak_l [expr {$::env(WEAK_HPWL) * $dbu}]
  set dly_l [expr {$::env(DLY_HPWL) * $dbu}]
  set todo {}
  foreach net [$block getNets] {
    if {[$net isSpecial]} continue
    set st [$net getSigType]
    if {$st eq "POWER" || $st eq "GROUND" || $st eq "CLOCK" || [llength [$net getBTerms]] > 0} continue
    lassign [net_info $net] drv loads clocky
    if {$drv eq "" || $clocky || [llength $loads] == 0} continue
    set xs {}; set ys {}
    foreach t [concat [list $drv] $loads] { set xy [$t getAvgXY]; lappend xs [lindex $xy 1]; lappend ys [lindex $xy 2] }
    set hp [expr {([tcl::mathfunc::max {*}$xs] - [tcl::mathfunc::min {*}$xs]) + ([tcl::mathfunc::max {*}$ys] - [tcl::mathfunc::min {*}$ys])}]
    lappend todo [list $drv $hp]
  }
  foreach item $todo {
    lassign $item d hp
    set dinst [$d getInst]; set dname [$dinst getName]
    if {[dict exists $seen $dname]} continue
    set m [[$dinst getMaster] getName]
    if {[string match "*clk*" $m] || [string match "*clk*" $dname]} continue
    if {[string match "*dlygate*" $m]} {
      if {$hp <= $dly_l} continue
      dict set seen $dname 1
      set net [$d getNet]
      set nn [odb::dbNet_create $block "${tag}_gdb_net_$gb"]
      set b [odb::dbInst_create $block $bufm "${tag}_gdb_$gb"]
      foreach t [$net getITerms] { if {$t ne $d && [$t isInputSignal]} { $t disconnect; $t connect $nn } }
      [$b findITerm A] connect $net; [$b findITerm X] connect $nn
      pwr $b
      set loc [$dinst getLocation]; $b setLocation [lindex $loc 0] [lindex $loc 1]; $b setPlacementStatus PLACED
      incr gb; continue
    }
    if {$hp <= $weak_l} continue
    if {![regexp {^(sky130_fd_sc_hd__.+)_([0-9]+)$} $m -> base n] || $n > 2} continue
    set target ""
    foreach z {4 6 8} { set cand [$db findMaster "${base}_$z"]; if {$cand ne "NULL"} { set target $cand; break } }
    if {$target eq ""} continue
    dict set seen $dname 1
    $dinst swapMaster $target
    incr gu
  }
}
puts "ECOW: global upsize $gu, global dlygate-buffer $gb"

# (3) pindahkan buffer ke dekat pin makro yang didorongnya
set mv 0
foreach name [readlist $::env(MOVE_NEAR)] {
  set name [string trim $name]; if {$name eq ""} continue
  set inst [$block findInst $name]; if {$inst eq "NULL"} { puts "SKIP move $name"; continue }
  set out ""; foreach t [$inst getITerms] { if {[$t isOutputSignal]} { set out $t } }
  set target ""
  foreach t [[$out getNet] getITerms] { if {[[[$t getInst] getMaster] getType] eq "BLOCK"} { set target $t } }
  if {$target eq ""} { puts "SKIP move $name (tidak mendorong makro)"; continue }
  set xy [$target getAvgXY]
  set old [$inst getLocation]
  $inst setLocation [lindex $xy 1] [lindex $xy 2]
  $inst setPlacementStatus PLACED
  puts "MOVE $name [lindex $old 0],[lindex $old 1] -> pin [[$target getInst] getName]/[[$target getMTerm] getName] [lindex $xy 1],[lindex $xy 2]"
  incr mv
}

# (4) hold
set n 0
foreach line [readlist $::env(HOLD_LIST)] {
  set parts [regexp -all -inline {\S+} $line]
  lassign $parts iname pin cnt
  if {$iname eq ""} continue
  if {$cnt eq ""} { set cnt 1 }
  set inst [$block findInst $iname]; if {$inst eq "NULL"} { puts "SKIP hold $iname"; continue }
  set it [$inst findITerm $pin]; set net [$it getNet]; if {$net eq "NULL"} continue
  set loc [$inst getLocation]
  set src $net
  touch $net
  for {set c 0} {$c < $cnt} {incr c} {
    set nn [odb::dbNet_create $block "${tag}_hold_net_$n"]
    touch $nn
    set buf [odb::dbInst_create $block $dly "${tag}_hold_$n"]
    [$buf findITerm A] connect $src
    [$buf findITerm X] connect $nn
    pwr $buf
    $buf setLocation [lindex $loc 0] [lindex $loc 1]; $buf setPlacementStatus PLACED
    set src $nn
    incr n
  }
  $it disconnect; $it connect $src
  puts "HOLD $iname/$pin x$cnt"
}
puts "ECOW: upsized $up, moved $mv, hold cells $n"
if {$post} {
  set nw 0
  dict for {name nt} $touched { set w [$nt getWire]; if {$w ne "NULL"} { odb::dbWire_destroy $w; incr nw } }
  puts "ECOW: kabel dihapus pada $nw dari [dict size $touched] net yang diubah"
}
detailed_placement -max_displacement {300 60}
check_placement -verbose
if {$post} { foreach inst $locked { $inst setPlacementStatus PLACED } }
foreach name [readlist $::env(MOVE_NEAR)] {
  set inst [$block findInst [string trim $name]]
  if {$inst ne "NULL"} { set l [$inst getLocation]; puts "MOVED-FINAL [$inst getName] [lindex $l 0],[lindex $l 1]" }
}
write_db $::env(ODB_OUT)
puts "ECOW: wrote $::env(ODB_OUT)"
