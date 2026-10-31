"""Golden model bit-exact untuk hw/asic/GRU/rtl/gru_engine.sv, kuantisasi model ke image flash, dan pembuat LUT RTL.

Model: GRU L lapis (hidden H, gaya PyTorch/ONNX: urutan gerbang z,r,n, linear_before_reset = 1) atas jendela T x NI,
ditambah 6 statistik per fitur jendela (rata-rata, simpangan baku n-1, min, maks, terakhir, terakhir - pertama) dan NC
fitur konteks, lalu NO keluaran linear. coldtrack_v5.onnx: L=3, H=128, NI=12, NC=6, T=60, NO=11 (3 forecast
ternormalisasi, 7 logit kelas, 1 ttb mentah).

Aritmetika (semua integer; rq(x, M, S) = (x*M + 2^(S-1)) >> S, geser kanan aritmetika = floor):
  masukan mentah  int32 Q15.16, dinormalisasi per fitur: xn = sat16(rq(x - off, M, S)), hasil Q5.10
  bobot           int8 per baris, skala per baris (M u16, S u8); bias int16 Q5.10
  gerbang         gx = rq(W.x) + bW, gh = rq(R.h) + bR (int32, tanpa saturasi)
                  z = sig(gx_z + gh_z), r = sig(gx_r + gh_r), n = tanh(gx_n + ((r*gh_n + 2^(FA-1)) >> FA))
                  h' = n + ((z*(h - n) + 2^(FA-1)) >> FA)
  sig, tanh       LUT 257 titik + interpolasi linear: sig di [-8, 8), tanh di [-4, 4), di luar itu dijepit
  statistik       S1 = sum xn, S2 = sum xn^2; mean = sat16(rq(S1, RN, SN)); var = rq(T*S2 - S1^2, RV, SV);
                  std = min(isqrt(var), 32767); selisih = sat16(last - first)
  keluaran        out = rq(Wh.z) + bh (int32 Q5.10)
Urutan hitung: waktu dulu (untuk tiap t: lapis 0..L-1), identik secara matematis dengan lapis dulu.

Layout image (little endian):
  [0..1] 'G' 'R'  [2] versi 1  [3] L  [4..5] H  [6] NI  [7] NC  [8] T  [9] NO  [10..12] WBASE  [13..15] HBASE
  [16..17] RN  [18] SN  [19..20] RV  [21] SV  [22..] (NI+NC) x {off s32, M u16, S u8}
  WBASE: satu langkah waktu, dibaca ulang tiap langkah: untuk lapis l, neuron j, gerbang z,r,n:
         W baris (in_l x s8), M u16, S u8, bW s16, R baris (H x s8), M u16, S u8, bR s16
  HBASE: untuk tiap keluaran: baris (H + 6*NI + NC) x s8, M u16, S u8, b s16
Memori masukan (int32): x[t][f] di alamat t*NI + f, lalu konteks di T*NI + c.
"""
import struct
from types import SimpleNamespace

import numpy as np

FA = 10
ONE = 1 << FA
RAW_FB = 16
LUT_N = 256


# ------------------------------------------------------------------ parameter float
def params_dari_onnx(path):
    import onnx
    from onnx import numpy_helper

    m = onnx.load(path)
    I = {i.name: numpy_helper.to_array(i).astype(np.float64) for i in m.graph.initializer}
    gru = sorted([k for k in I if k.startswith("onnx::GRU_")], key=lambda s: int(s.split("_")[-1]))
    lay = []
    for l in range(len(gru) // 3):
        W, R, B = (I[gru[3 * l + j]][0] for j in range(3))
        H = R.shape[1]
        lay.append(dict(W=W, R=R, Wb=B[:3 * H], Rb=B[3 * H:]))
    HW = np.concatenate([I["core.head_forecast.weight"], I["core.head_failure.weight"], I["core.head_ttb.weight"]])
    Hb = np.concatenate([I["core.head_forecast.bias"], I["core.head_failure.bias"], I["core.head_ttb.bias"]])
    if "fc_s" in I:      # v6: forecast residual, C = suhu terakhir + v * fc_s + fc_b (per horizon)
        fc_mul, fc_add, residual = I["fc_s"].ravel(), I["fc_b"].ravel(), True
    else:                # v5: forecast absolut, C = v * mul + add
        mul = [k for k in I if k.startswith("onnx::Mul_") and I[k].size == 1]
        add = [k for k in I if k.startswith("onnx::Add_") and I[k].size == 1]
        fc_mul, fc_add, residual = np.full(3, I[mul[0]].ravel()[0]), np.full(3, I[add[0]].ravel()[0]), False
    return dict(lay=lay, HW=HW, Hb=Hb, mean=I["mean"].ravel(), std=I["std"].ravel(),
                cmean=I["ctx_mean"].ravel(), cstd=I["ctx_std"].ravel(), fc_mul=fc_mul, fc_add=fc_add, residual=residual)


def params_acak(rng, L=2, H=16, NI=4, NC=2, NO=5, skala=0.4):
    lay, inn = [], NI
    for _ in range(L):
        lay.append(dict(W=rng.normal(0, skala, (3 * H, inn)), R=rng.normal(0, skala, (3 * H, H)),
                        Wb=rng.normal(0, 0.3, 3 * H), Rb=rng.normal(0, 0.3, 3 * H)))
        inn = H
    NZ = H + 6 * NI + NC
    return dict(lay=lay, HW=rng.normal(0, 0.3, (NO, NZ)), Hb=rng.normal(0, 0.3, NO),
                mean=rng.normal(0, 5, NI), std=rng.uniform(0.05, 20, NI),
                cmean=rng.normal(0, 5, NC), cstd=rng.uniform(0.01, 20, NC))


# ------------------------------------------------------------------ primitif fixed-point
def mul_shift(x):
    """x > 0 -> (M, S) dengan M / 2^S ~ x dan 16384 <= M <= 32767."""
    S = 0
    while x * (1 << S) < 16383.5:
        S += 1
    while x * (1 << S) > 32767:
        S -= 1
    assert 1 <= S <= 63, (x, S)
    return int(round(x * (1 << S))), S


def rq(x, M, S):
    return (x * M + (np.int64(1) << (S - 1))) >> S


def sat16(x):
    return np.clip(x, -32768, 32767)


def kuant_baris(W):
    s = np.abs(W).max(1) / 127.0
    s[s == 0] = 1.0
    return np.clip(np.round(W / s[:, None]), -127, 127).astype(np.int64), s


def _tabel():
    xs = -8 + np.arange(LUT_N + 1) * 16 / LUT_N
    xt = -4 + np.arange(LUT_N + 1) * 8 / LUT_N
    return (np.round(1 / (1 + np.exp(-xs)) * ONE).astype(np.int64), np.round(np.tanh(xt) * ONE).astype(np.int64))


SIG, TAN = _tabel()


def _lut(v, tab, lo, k):
    v = np.clip(v, -lo, lo - 1)
    u = v + lo
    idx, fr = u >> k, u & ((1 << k) - 1)
    a, b = tab[idx], tab[idx + 1]
    return a + (((b - a) * fr + (1 << (k - 1))) >> k)


def f_sig(v):
    return _lut(v, SIG, 8 * ONE, int(np.log2(16 * ONE // LUT_N)))


def f_tanh(v):
    return _lut(v, TAN, 4 * ONE, int(np.log2(8 * ONE // LUT_N)))


def isqrt(v):
    s = np.floor(np.sqrt(v.astype(np.float64))).astype(np.int64)
    s = np.where((s + 1) * (s + 1) <= v, s + 1, s)
    return np.where(s * s > v, s - 1, s)


def _recip(n):
    """1/n sebagai (R, S) dengan R < 2^16 (operand pengali RTL) dan S sebesar mungkin (<= 40)."""
    S = 40
    while round((1 << S) / n) >= 65536:
        S -= 1
    return int(round((1 << S) / n)), S


def _mv(q, a):
    return np.rint(a.astype(np.float64) @ q.T.astype(np.float64)).astype(np.int64)  # eksak, |jumlah| < 2^53


# ------------------------------------------------------------------ model integer
def kuantisasi(p, T):
    """Parameter float -> model integer (SimpleNamespace) untuk jendela T langkah."""
    m = SimpleNamespace(T=T, L=len(p["lay"]), H=p["lay"][0]["R"].shape[1], NI=p["lay"][0]["W"].shape[1],
                        NC=len(p["cmean"]), NO=p["HW"].shape[0])
    mean = np.concatenate([p["mean"], p["cmean"]]); std = np.concatenate([p["std"], p["cstd"]])
    m.n_off = np.round(mean * (1 << RAW_FB)).astype(np.int64)
    ms = [mul_shift(ONE / (s * (1 << RAW_FB))) for s in std]
    m.n_M = np.array([a for a, _ in ms], np.int64); m.n_S = np.array([b for _, b in ms], np.int64)

    def qm(W):
        q, s = kuant_baris(W)
        ms = [mul_shift(v) for v in s]
        return q, np.array([a for a, _ in ms], np.int64), np.array([b for _, b in ms], np.int64)

    def qb(b):
        b = np.round(np.asarray(b) * ONE).astype(np.int64)
        assert np.abs(b).max() <= 32767, "bias di luar int16"
        return b

    m.lay = []
    for L in p["lay"]:
        d = SimpleNamespace()
        d.Wq, d.WM, d.WS = qm(L["W"])
        d.Rq, d.RM, d.RS = qm(L["R"])
        d.Wb, d.Rb = qb(L["Wb"]), qb(L["Rb"])
        m.lay.append(d)
    m.Hq, m.HM, m.HS = qm(p["HW"])
    m.Hb = qb(p["Hb"])
    m.RN, m.SN = _recip(T)
    m.RV, m.SV = _recip(T * (T - 1))
    return m


def maju(m, Xr, Cr, jejak=None):
    """Xr (B,T,NI) int Q15.16, Cr (B,NC) -> (B,NO) int64 Q5.10."""
    Xr = np.asarray(Xr, np.int64); Cr = np.asarray(Cr, np.int64).reshape(len(Xr), m.NC)
    B, T, NI = Xr.shape; H = m.H; half = ONE >> 1
    assert T == m.T and NI == m.NI

    def norm(raw, j):
        return sat16(rq(raw - m.n_off[j], m.n_M[j], m.n_S[j]))
    xn = np.stack([norm(Xr[:, :, j], j) for j in range(NI)], 2)
    cn = np.stack([norm(Cr[:, j], NI + j) for j in range(m.NC)], 1) if m.NC else np.zeros((B, 0), np.int64)
    h = [np.zeros((B, H), np.int64) for _ in range(m.L)]
    for t in range(T):
        inp = xn[:, t]
        for l, d in enumerate(m.lay):
            gx = rq(_mv(d.Wq, inp), d.WM, d.WS) + d.Wb
            gh = rq(_mv(d.Rq, h[l]), d.RM, d.RS) + d.Rb
            z = f_sig(gx[:, :H] + gh[:, :H])
            r = f_sig(gx[:, H:2 * H] + gh[:, H:2 * H])
            n = f_tanh(gx[:, 2 * H:] + ((r * gh[:, 2 * H:] + half) >> FA))
            h[l] = n + ((z * (h[l] - n) + half) >> FA)
            inp = h[l]
        if jejak is not None:
            jejak.setdefault("h", []).append([x.copy() for x in h])
    S1 = xn.sum(1); S2 = (xn * xn).sum(1)
    mean = sat16(rq(S1, m.RN, m.SN))
    var = rq(T * S2 - S1 * S1, m.RV, m.SV)
    std = np.minimum(isqrt(var), 32767)
    feat = np.concatenate([h[-1], mean, std, xn.min(1), xn.max(1), xn[:, -1], sat16(xn[:, -1] - xn[:, 0]), cn], 1)
    if jejak is not None:
        jejak.update(xn=xn, cn=cn, feat=feat)
    return rq(_mv(m.Hq, feat), m.HM, m.HS) + m.Hb


# ------------------------------------------------------------------ image flash
def image(m):
    body = bytearray()
    for d in m.lay:
        for j in range(m.H):
            for g in range(3):
                r = g * m.H + j
                body += d.Wq[r].astype(np.int8).tobytes() + struct.pack("<HBh", d.WM[r], d.WS[r], d.Wb[r])
                body += d.Rq[r].astype(np.int8).tobytes() + struct.pack("<HBh", d.RM[r], d.RS[r], d.Rb[r])
    heads = bytearray()
    for o in range(m.NO):
        heads += m.Hq[o].astype(np.int8).tobytes() + struct.pack("<HBh", m.HM[o], m.HS[o], m.Hb[o])
    HL = 22 + 7 * (m.NI + m.NC)
    wbase, hbase = HL, HL + len(body)
    hdr = bytearray(b"GR") + struct.pack("<BBHBBBB", 1, m.L, m.H, m.NI, m.NC, m.T, m.NO)
    hdr += wbase.to_bytes(3, "little") + hbase.to_bytes(3, "little")
    hdr += struct.pack("<HBHB", m.RN, m.SN, m.RV, m.SV)
    for f in range(m.NI + m.NC):
        hdr += struct.pack("<iHB", m.n_off[f], m.n_M[f], m.n_S[f])
    assert len(hdr) == HL and hbase + len(heads) < (1 << 24)
    return bytes(hdr + body + heads)


def baca_image(img):
    """Kebalikan image(): model integer langsung dari byte flash (tanpa onnx)."""
    if img[:2] != b"GR" or img[2] != 1:
        raise ValueError("header image GRU tidak sah")
    L, H, NI, NC, T, NO = img[3], struct.unpack_from("<H", img, 4)[0], img[6], img[7], img[8], img[9]
    wbase, hbase = int.from_bytes(img[10:13], "little"), int.from_bytes(img[13:16], "little")
    m = SimpleNamespace(T=T, L=L, H=H, NI=NI, NC=NC, NO=NO)
    m.RN, m.SN, m.RV, m.SV = struct.unpack_from("<HBHB", img, 16)
    e = [struct.unpack_from("<iHB", img, 22 + 7 * f) for f in range(NI + NC)]
    m.n_off = np.array([a for a, _, _ in e], np.int64)
    m.n_M = np.array([b for _, b, _ in e], np.int64); m.n_S = np.array([c for _, _, c in e], np.int64)
    pos = wbase

    def baris(n):
        nonlocal pos
        w = np.frombuffer(img, np.int8, n, pos).astype(np.int64)
        M, S, b = struct.unpack_from("<HBh", img, pos + n)
        pos += n + 5
        return w, M, S, b
    m.lay = []
    for l in range(L):
        inn = NI if l == 0 else H
        d = SimpleNamespace(Wq=np.zeros((3 * H, inn), np.int64), Rq=np.zeros((3 * H, H), np.int64),
                            **{k: np.zeros(3 * H, np.int64) for k in ("WM", "WS", "Wb", "RM", "RS", "Rb")})
        for j in range(H):
            for g in range(3):
                r = g * H + j
                d.Wq[r], d.WM[r], d.WS[r], d.Wb[r] = baris(inn)
                d.Rq[r], d.RM[r], d.RS[r], d.Rb[r] = baris(H)
        m.lay.append(d)
    assert pos == hbase, "panjang bagian bobot tidak cocok dengan HBASE"
    NZ = H + 6 * NI + NC
    m.Hq = np.zeros((NO, NZ), np.int64)
    m.HM, m.HS, m.Hb = (np.zeros(NO, np.int64) for _ in range(3))
    for o in range(NO):
        m.Hq[o], m.HM[o], m.HS[o], m.Hb[o] = baris(NZ)
    return m


# ------------------------------------------------------------------ bantu
def raw_q(a):
    return np.round(np.asarray(a, np.float64) * (1 << RAW_FB)).astype(np.int64)


def kata_masukan(xr, cr):
    """Satu jendela (T,NI) + (NC,) -> daftar int32 untuk memori masukan."""
    return [int(v) for v in np.asarray(xr).reshape(-1)] + [int(v) for v in np.asarray(cr).reshape(-1)]


def tulis_lut_sv(path):
    """Tabel ROM untuk gru_engine (dibangkitkan, jangan diedit manual)."""
    def kasus(nama, tab, w):
        s = [f"function automatic logic signed [{w - 1}:0] {nama}(input logic [8:0] i);", "    case (i)"]
        s += [f"        9'd{i}: {nama} = {'-' if v < 0 else ''}{w}'sd{abs(v)};" for i, v in enumerate(tab)]
        s += [f"        default: {nama} = '0;", "    endcase", "endfunction"]
        return "\n".join(s)
    with open(path, "w") as f:
        f.write("// Dibangkitkan oleh hw/asic/GRU/golden/gru_golden.py (tulis_lut_sv). Jangan diedit manual.\n")
        f.write(f"// lut_sig: {LUT_N + 1} titik sigmoid di [-8, 8]; lut_tanh: {LUT_N + 1} titik tanh di [-4, 4]; "
                f"keluaran Q5.{FA}.\n")
        f.write(kasus("lut_sig", SIG, 12) + "\n" + kasus("lut_tanh", TAN, 12) + "\n")


def keluaran_v5(out_int, fc_mul, fc_add, suhu_terakhir=None):
    """Keluaran int Q5.10 kontrak coldtrack_v5/v6 -> forecast C (3), peluang kelas (7), ttb menit.
    Model residual (v6): suhu_terakhir = temp_c menit terakhir jendela, ditambahkan oleh host."""
    o = np.asarray(out_int, np.float64) / ONE
    fc = o[..., :3] * np.asarray(fc_mul) + np.asarray(fc_add)
    if suhu_terakhir is not None:
        fc = fc + np.asarray(suhu_terakhir, np.float64)[..., None]
    lg = o[..., 3:10]; pr = np.exp(lg - lg.max(-1, keepdims=True)); pr /= pr.sum(-1, keepdims=True)
    return fc, pr, np.clip(np.exp(o[..., 10]) - 1, 0, None)
