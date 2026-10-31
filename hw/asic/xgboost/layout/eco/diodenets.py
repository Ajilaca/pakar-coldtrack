# Net top-level pasca-route: jumlah dioda dan beban per net, untuk daftar repeater ECO.
import os
import odb
db = odb.dbDatabase.create()
odb.read_db(db, os.environ["ODB"])
block = db.getChip().getBlock()
dbu = block.getDbUnitsPerMicron()
hist = {}
out = open(os.environ["OUT"], "w")
for net in block.getNets():
    if net.isSpecial() or net.getSigType() in ("POWER", "GROUND", "CLOCK"):
        continue
    its = list(net.getITerms())
    drv = [t for t in its if t.isOutputSignal()]
    loads = [t for t in its if t.isInputSignal()]
    if len(drv) != 1 or not loads:
        continue
    nd = sum(1 for t in loads if "diode" in t.getInst().getMaster().getName())
    hist[nd] = hist.get(nd, 0) + 1
    if len(loads) >= 7 and nd >= 3:
        pts = [t.getAvgXY()[1:] for t in its]
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        hpwl = ((max(xs)-min(xs)) + (max(ys)-min(ys))) / dbu
        d = drv[0]
        out.write(f"{d.getInst().getName()} {d.getMTerm().getName()} {len(loads)} {nd} {hpwl:.0f} {d.getInst().getMaster().getName().replace('sky130_fd_sc_hd__','')} {int(bool(net.getBTerms()))}\n")
print("histogram dioda per net:", sorted(hist.items()))
