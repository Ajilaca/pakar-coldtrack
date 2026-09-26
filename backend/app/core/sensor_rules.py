"""
Lapisan aturan sensor (kausal, per menit). Ambang berasal dari data Intel Berkeley Lab (lihat komentar).
Keluaran per menit: status 0=ok, 1=curiga, 2=rusak (pasti).
"""
import numpy as np

SENSOR_MAX, SENSOR_MIN = 60.0, -40.0   # Intel: 17,4% pembacaan berada di luar rentang ini (91% tepat 122,15 C)
JUMP_C = 5.0                           # Intel: lompatan >5 C antar pembacaan hanya 0,008% pada sensor sehat
FLAT_SURE_MIN = 60                     # Intel: rangkaian datar sehat p99 ~34 menit; >=60 menit hanya 5 rangkaian di 2 mote
FLAT_SUSPECT_MIN = 15                  # curiga bila datar >=15 menit DAN ada konteks yang seharusnya mengubah suhu
CTX_AMB_RISE = 3.0                     # kenaikan T_amb 30 menit terakhir (C)


def sensor_status(t_sensor, door_open, t_amb, moving=None, battery_v=None):
    n = len(t_sensor); st = np.zeros(n, dtype=np.int8)
    ts = np.asarray(t_sensor, float)
    bad = (ts > SENSOR_MAX) | (ts < SENSOR_MIN)
    st[bad] = 2
    last_ok = None; flat = 0; prev = None
    for i in range(n):
        if bad[i]: flat = 0; prev = None; continue
        if prev is not None and ts[i] == prev: flat += 1
        else: flat = 0
        prev = ts[i]
        if last_ok is not None and abs(ts[i] - last_ok) > JUMP_C and i > 0:
            # lompatan sah bila pintu baru dibuka/ditutup atau truk baru berhenti/jalan (pendingin ikut berubah)
            lo = max(0, i - 10)
            legit = door_open[lo:i + 1].any() or (moving is not None and (np.asarray(moving)[lo:i + 1] != np.asarray(moving)[i]).any())
            if not legit: st[i] = max(st[i], 1)
        last_ok = ts[i]
        if flat >= FLAT_SURE_MIN: st[i] = 2
        elif flat >= FLAT_SUSPECT_MIN:
            ctx = door_open[max(0, i - flat):i + 1].any() or (t_amb[i] - t_amb[max(0, i - 30)]) >= CTX_AMB_RISE
            if ctx: st[i] = max(st[i], 1)
    if battery_v is not None:                            # Intel: nilai ekstrem hanya muncul saat tegangan < 2,4 V
        st[(np.asarray(battery_v) < 2.4) & (st == 0)] = 1
    return st
