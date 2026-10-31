# Daftar ECO dari ODB pasca-route (env ODB) dan folder kerja E (berisi slew_pins.txt dan fo_drv.txt):
#  slew (pin pelanggar max_ss + max_tt top-level) -> driver ukuran <=2/dlygate/clkbuf: buffer di belakang (UPSIZE_AS_BUF);
#                                                   driver ukuran >=4: repeater tengah (DIODE_SPLIT)
#  fanout (beban >= 8, dioda ikut)                 -> beban asli <= 5: repeater tengah; > 5: dipecah (FORCE_PINS)
import os, re
import odb
db = odb.dbDatabase.create()
odb.read_db(db, os.environ["ODB"])
block = db.getChip().getBlock()
E = os.environ["E"]

def net_of(s):
    i = s.rfind("/")
    inst = block.findInst(s[:i].replace("\\", ""))
    if inst is None:
        return None
    it = inst.findITerm(s[i+1:])
    return None if it is None else it.getNet()

def drv_of(net):
    d = [t for t in net.getITerms() if t.isOutputSignal()]
    return d[0] if len(d) == 1 else None

behind, split, force = set(), set(), set()
for line in open(f"{E}/fo_drv.txt"):
    name, pin, loads, nd = line.split()[:4]
    inst = block.findInst(name)
    if inst is None or inst.getMaster().getType() == "BLOCK" or "clk" in name:
        continue
    real = int(loads) - int(nd)
    (force if real > 5 else split).add(f"{name}/{pin}" if real > 5 else name)
nets = set()
for s in open(f"{E}/slew_pins.txt"):
    net = net_of(s.split()[0])
    if net is None or net.getName() in nets:
        continue
    nets.add(net.getName())
    d = drv_of(net)
    if d is None or d.getInst().getMaster().getType() == "BLOCK":
        continue
    name = d.getInst().getName(); m = d.getInst().getMaster().getName()
    if "clk" in name or name in split or any(f.startswith(name + "/") for f in force):
        continue
    z = re.search(r"_(\d+)$", m)
    if "dlygate" in m or (z and int(z.group(1)) <= 2):
        behind.add(f"{name}/{d.getMTerm().getName()}")
    else:
        split.add(name)
open(f"{E}/upsize.txt", "w").write("\n".join(sorted(behind)) + "\n")
open(f"{E}/dsplit.txt", "w").write("\n".join(sorted(split)) + "\n")
open(f"{E}/force.txt", "w").write("\n".join(sorted(force)) + "\n")
print(f"net slew {len(nets)}; buffer-belakang {len(behind)}, repeater {len(split)}, pecah {len(force)}")
print("pecah:", sorted(force))
