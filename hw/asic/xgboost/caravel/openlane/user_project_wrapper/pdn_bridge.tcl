# SPDX-FileCopyrightText: 2026 Faza Dzil
# SPDX-License-Identifier: Apache-2.0
#
# Sambung strap PDN wrapper ke pin daya makro coldtrack_asic (dijalankan sesudah OpenROAD.GeneratePDN).
# Grid strap vccd1/vssd1 berimpit dengan pin VPWR/VGND makro (met4 vertikal, met5 horizontal), tetapi pdngen
# menghentikan strap sedikit sebelum ujung pin makro (met4 ~0,6 um, met5 ~3,2 um), sehingga makro tidak tersambung
# (PSM-0039). Untuk tiap ujung strap yang segaris dengan pin makro bernet sama dan berjarak < 5 um, skrip ini
# menambah kotak di layer yang sama dari ujung strap sampai menumpang 0,5 um ke pin.
# Env: ODB_IN, ODB_OUT, INST (bawaan u_ct).

read_db $::env(ODB_IN)
set block [ord::get_db_block]
set dbu [$block getDbUnitsPerMicron]
set batas [expr {int(5.0 * $dbu)}]
set tumpang [expr {int(0.5 * $dbu)}]
set inst [$block findInst [expr {[info exists ::env(INST)] ? $::env(INST) : "u_ct"}]]
lassign [$inst getLocation] ox oy
if {[$inst getOrient] ne "R0"} { error "pdn_bridge.tcl hanya untuk orientasi N (R0)" }

set total 0
foreach it [$inst getITerms] {
    set sig [[$it getMTerm] getSigType]
    if {$sig ne "POWER" && $sig ne "GROUND"} { continue }
    set net [$it getNet]
    if {$net eq "NULL"} { continue }
    # pin makro (koordinat blok)
    set pins {}
    foreach mp [[$it getMTerm] getMPins] {
        foreach g [$mp getGeometry] {
            set ln [[$g getTechLayer] getName]
            lappend pins [list $ln [expr {[$g xMin] + $ox}] [expr {[$g yMin] + $oy}] [expr {[$g xMax] + $ox}] [expr {[$g yMax] + $oy}]]
        }
    }
    set n 0
    foreach sw [$net getSWires] {
        foreach w [$sw getWires] {
            if {[$w isVia]} { continue }
            set l [$w getTechLayer]
            set ln [$l getName]
            set x0 [$w xMin]; set y0 [$w yMin]; set x1 [$w xMax]; set y1 [$w yMax]
            foreach p $pins {
                lassign $p pl px0 py0 px1 py1
                if {$pl ne $ln} { continue }
                if {$ln eq "met4" && $px0 == $x0 && $px1 == $x1} {
                    if {$py0 > $y1 && $py0 - $y1 < $batas} {
                        odb::dbSBox_create $sw $l $x0 $y1 $x1 [expr {$py0 + $tumpang}] STRIPE; incr n
                    } elseif {$y0 > $py1 && $y0 - $py1 < $batas} {
                        odb::dbSBox_create $sw $l $x0 [expr {$py1 - $tumpang}] $x1 $y0 STRIPE; incr n
                    }
                }
                if {$ln eq "met5" && $py0 == $y0 && $py1 == $y1} {
                    if {$px0 > $x1 && $px0 - $x1 < $batas} {
                        odb::dbSBox_create $sw $l $x1 $y0 [expr {$px0 + $tumpang}] $y1 STRIPE; incr n
                    } elseif {$x0 > $px1 && $x0 - $px1 < $batas} {
                        odb::dbSBox_create $sw $l [expr {$px1 - $tumpang}] $y0 $x0 $y1 STRIPE; incr n
                    }
                }
            }
        }
    }
    puts "JEMBATAN [$net getName] ([[$it getMTerm] getName]): $n sambungan, pin [llength $pins] kotak"
    incr total $n
}
puts "JEMBATAN total $total"
write_db $::env(ODB_OUT)

# cek ulang konektivitas grid (metrik PSM dari GeneratePDN dihitung sebelum jembatan); hasil per net ke PSM_OUT
if {[info exists ::env(PSM_OUT)]} {
    set f [open $::env(PSM_OUT) w]
    foreach n {vccd1 vssd1} {
        set ok [expr {![catch {check_power_grid -net $n} r] && $r == 1}]
        puts "PSM $n tersambung=$ok"
        puts $f "$n $ok"
    }
    close $f
}
