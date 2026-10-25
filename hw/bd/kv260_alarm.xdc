# Alarm sopir ke PMOD J2 KV260 (pin 1-3, bank HDIO 3,3 V). Cocokkan dengan UG1089 (KV260 carrier) sebelum
# menyambung LED/buzzer; pin PMOD lain: C11 B10 E12 D11 B11.
set_property PACKAGE_PIN H12 [get_ports alarm_waspada]
set_property PACKAGE_PIN E10 [get_ports alarm_kritis]
set_property PACKAGE_PIN D10 [get_ports alarm_sensor]
set_property IOSTANDARD LVCMOS33 [get_ports {alarm_waspada alarm_kritis alarm_sensor}]
set_property DRIVE 8 [get_ports {alarm_waspada alarm_kritis alarm_sensor}]
