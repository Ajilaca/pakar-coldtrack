"""
Langkah latihan 2: GRU multi-tugas.
Keluaran: 3 kejadian (A1 pintu, A2 kejut, A3 sensor) + suhu muatan 15/30/60 menit + TTB.
Masukan: jendela [60, 8] + info muatan [4] (ditempel ke tiap langkah).
"""
import time, numpy as np, torch, torch.nn as nn

CONT_IDX = [0, 1, 2]        # kolom kontinu di FEATS yang dinormalisasi: T_sensor_clean, T_amb, RH_amb
TTB_MAX = 240.0


def fit_scalers(Xtr, Str, Ytr):
    fx = Xtr.reshape(-1, Xtr.shape[2])
    sc = dict(x_mu=fx[:, CONT_IDX].mean(0), x_sd=fx[:, CONT_IDX].std(0) + 1e-6,
              s_mu=Str.mean(0), s_sd=Str.std(0) + 1e-6)
    yt = Ytr[:, 4:7]
    sc["t_mu"] = float(np.nanmean(yt)); sc["t_sd"] = float(np.nanstd(yt))
    return sc


def to_tensors(X, S, Y, sc, device):
    X = X.copy()
    X[:, :, CONT_IDX] = (X[:, :, CONT_IDX] - sc["x_mu"]) / sc["x_sd"]
    Sn = (S - sc["s_mu"]) / sc["s_sd"]
    Xin = np.concatenate([X, np.repeat(Sn[:, None, :], X.shape[1], 1)], axis=2).astype(np.float32)
    ev = Y[:, :3]
    ttb = (Y[:, 3] / TTB_MAX)[:, None]
    T = (Y[:, 4:7] - sc["t_mu"]) / sc["t_sd"]
    mask = (~np.isnan(T)).astype(np.float32); T = np.nan_to_num(T)
    f = lambda a: torch.tensor(a, dtype=torch.float32, device=device)
    return f(Xin), f(ev), f(ttb), f(T), f(mask)


class ColdGRU(nn.Module):
    def __init__(self, n_in, hidden=64):
        super().__init__()
        self.gru = nn.GRU(n_in, hidden, batch_first=True)
        self.body = nn.Sequential(nn.Linear(hidden, 64), nn.ReLU())
        self.ev = nn.Linear(64, 3); self.temp = nn.Linear(64, 3); self.ttb = nn.Linear(64, 1)

    def forward(self, x):
        _, h = self.gru(x)
        z = self.body(h[-1])
        return self.ev(z), self.temp(z), torch.sigmoid(self.ttb(z))


def train(tr, va, epochs=25, lr=2e-3, bs=256, patience=5, device="cpu", seed=0, log=print):
    torch.manual_seed(seed)
    Xtr, EVtr, TTtr, Ttr, Mtr = tr
    model = ColdGRU(Xtr.shape[2]).to(device)
    pos = EVtr.mean(0).clamp(min=1e-3)
    bce = nn.BCEWithLogitsLoss(pos_weight=((1 - pos) / pos).clamp(max=20))
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    best, bad, best_state = 1e9, 0, None
    for ep in range(epochs):
        t0 = time.time(); model.train()
        perm = torch.randperm(len(Xtr), device=device)
        for i in range(0, len(perm), bs):
            b = perm[i:i + bs]
            e, t, q = model(Xtr[b])
            loss = bce(e, EVtr[b]) + ((t - Ttr[b]) ** 2 * Mtr[b]).sum() / Mtr[b].sum().clamp(min=1) \
                   + 3.0 * nn.functional.smooth_l1_loss(q, TTtr[b], beta=0.05)
            opt.zero_grad(); loss.backward(); opt.step()
        vl = evaluate_loss(model, va, bce)
        log(f"epoch {ep + 1:02d} | val loss {vl:.4f} | {time.time() - t0:.1f}s")
        if vl < best - 1e-4: best, bad, best_state = vl, 0, {k: v.clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= patience: log("berhenti lebih awal"); break
    model.load_state_dict(best_state)
    return model


@torch.no_grad()
def evaluate_loss(model, d, bce, bs=2048):
    model.eval(); X, EV, TT, T, M = d; tot = 0.0
    for i in range(0, len(X), bs):
        e, t, q = model(X[i:i + bs])
        tot += (bce(e, EV[i:i + bs]) + ((t - T[i:i + bs]) ** 2 * M[i:i + bs]).sum() / M[i:i + bs].sum().clamp(min=1)
                + 3.0 * nn.functional.smooth_l1_loss(q, TT[i:i + bs], beta=0.05)).item() * len(X[i:i + bs])
    return tot / len(X)


@torch.no_grad()
def predict(model, X, bs=2048):
    model.eval(); E, T, Q = [], [], []
    for i in range(0, len(X), bs):
        e, t, q = model(X[i:i + bs]); E.append(torch.sigmoid(e)); T.append(t); Q.append(q)
    return torch.cat(E).cpu().numpy(), torch.cat(T).cpu().numpy(), torch.cat(Q).cpu().numpy()[:, 0]


def report(model, d, Y, sc, meta=None, name="uji"):
    from sklearn.metrics import roc_auc_score, f1_score
    X = d[0]
    E, T, Q = predict(model, X)
    print(f"\n=== {name} ===")
    for j, nm in enumerate(["A1 pintu", "A2 kejut", "A3 sensor"]):
        y = Y[:, j] > 0.5
        auc = roc_auc_score(y, E[:, j]) if 0 < y.sum() < len(y) else float("nan")
        print(f"{nm}: AUC {auc:.3f} | F1@0.5 {f1_score(y, E[:, j] > 0.5):.3f} | porsi positif {y.mean():.3f}")
    Tp = T * sc["t_sd"] + sc["t_mu"]
    for k, h in enumerate([15, 30, 60]):
        ok = ~np.isnan(Y[:, 4 + k])
        print(f"suhu muatan +{h} mnt: MAE {np.abs(Tp[ok, k] - Y[ok, 4 + k]).mean():.2f} C")
    ttb_p, ttb_y = Q * TTB_MAX, Y[:, 3]
    base = np.abs(ttb_y - ttb_y.mean()).mean()
    print(f"TTB MAE {np.abs(ttb_p - ttb_y).mean():.1f} mnt (pembanding tebak-rata-rata {base:.1f})")
    near = ttb_y < 120
    print(f"TTB MAE khusus TTB<120 mnt ({near.mean():.3f} sampel): {np.abs(ttb_p[near] - ttb_y[near]).mean():.1f} mnt")
    return E, Tp, ttb_p
