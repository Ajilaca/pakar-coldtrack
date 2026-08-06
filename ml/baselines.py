"""Fase 5 R2 -- baseline pembanding, menjawab pertanyaan juri "kenapa harus deep learning?".

XGBoost/Linear/IsolationForest tidak bisa memakan data berurutan, jadi tiap jendela
60x12 diringkas jadi 72 fitur agregat (6 statistik x 12 kolom).

Menjalankan: python -m ml.baselines
"""

import json
import time

import numpy as np
import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.metrics import average_precision_score, f1_score

from ml.preprocess.build_windows import FAILURE_CLASSES

TRAIN_PATH = "data/processed/windows/windows_train.npz"
VAL_PATH = "data/processed/windows/windows_val.npz"
OUT_PATH = "ml/reports/baseline_metrics.json"

SENTINEL = 999.0
XGB_PARAMS = dict(n_estimators=300, max_depth=6, learning_rate=0.1,
                  n_jobs=-1, tree_method='hist', random_state=42)


def aggregate(X):
    """Ringkas jendela (n, 60, 12) jadi (n, 72): 6 statistik per fitur."""
    return np.concatenate([
        X.mean(axis=1),                    # rata-rata sepanjang jendela
        X.std(axis=1),                     # seberapa bergejolak
        X.min(axis=1),
        X.max(axis=1),
        X[:, -1, :],                       # nilai di menit terakhir ("sekarang")
        X[:, -1, :] - X[:, 0, :],          # tren: selisih akhir vs awal
    ], axis=1)


def main():
    tr, va = np.load(TRAIN_PATH), np.load(VAL_PATH)
    Xtr, Xva = aggregate(tr['X']), aggregate(va['X'])
    print(f"Fitur agregat: train={Xtr.shape}, val={Xva.shape}\n")

    hasil = {}

    # --- Head-1: forecast t+30 ---
    t0 = time.time()
    lin = LinearRegression().fit(Xtr, tr['y_forecast'][:, 1])
    mae_lin = float(np.abs(lin.predict(Xva) - va['y_forecast'][:, 1]).mean())

    xg_fc = xgb.XGBRegressor(**XGB_PARAMS).fit(Xtr, tr['y_forecast'][:, 1])
    mae_xgb = float(np.abs(xg_fc.predict(Xva) - va['y_forecast'][:, 1]).mean())

    hasil['forecast_t30_mae_c'] = {'linear': mae_lin, 'xgboost': mae_xgb}
    print(f"Forecast t+30 MAE (C)  linear={mae_lin:.3f}  xgboost={mae_xgb:.3f}   ({time.time()-t0:.0f}s)")

    # --- Head-2: mode kegagalan ---
    t0 = time.time()
    clf = xgb.XGBClassifier(objective='multi:softprob', num_class=len(FAILURE_CLASSES), **XGB_PARAMS)
    clf.fit(Xtr, tr['y_mode'])
    pred = clf.predict(Xva)
    f1 = float(f1_score(va['y_mode'], pred, average='macro'))
    acc = float((pred == va['y_mode']).mean())

    hasil['failure_mode'] = {'xgboost_macro_f1': f1, 'xgboost_akurasi': acc}
    print(f"Failure mode           macro_f1={f1:.4f}  akurasi={acc:.4f}   ({time.time()-t0:.0f}s)")

    # --- Head-3: time-to-breach (sentinel di-mask, sama seperti GRU) ---
    t0 = time.time()
    m_tr, m_va = tr['y_ttb'] != SENTINEL, va['y_ttb'] != SENTINEL
    xg_ttb = xgb.XGBRegressor(**XGB_PARAMS).fit(Xtr[m_tr], np.log1p(tr['y_ttb'][m_tr]))
    mae_ttb = float(np.abs(np.expm1(xg_ttb.predict(Xva[m_va])) - va['y_ttb'][m_va]).mean())

    hasil['ttb_mae_menit'] = {'xgboost': mae_ttb}
    print(f"Time-to-breach MAE     xgboost={mae_ttb:.2f} menit   ({time.time()-t0:.0f}s)")

    # --- Deteksi anomali biner ---
    t0 = time.time()
    is_anom = (va['y_mode'] != 0).astype(int)

    # IsolationForest dilatih HANYA pada data sehat -- deteksi anomali murni tanpa label
    iso = IsolationForest(n_estimators=200, contamination=0.4, random_state=42, n_jobs=-1)
    iso.fit(Xtr[tr['y_mode'] == 0])
    prauc_iso = float(average_precision_score(is_anom, -iso.score_samples(Xva)))
    prauc_xgb = float(average_precision_score(is_anom, 1 - clf.predict_proba(Xva)[:, 0]))

    hasil['anomali_pr_auc'] = {'isolation_forest': prauc_iso, 'xgboost': prauc_xgb}
    print(f"Deteksi anomali PR-AUC iso_forest={prauc_iso:.4f}  xgboost={prauc_xgb:.4f}   ({time.time()-t0:.0f}s)")

    hasil['catatan'] = (
        "Dievaluasi di split validasi dataset v3. XGBoost melatih model terpisah per tugas, "
        "sedangkan GRU memakai satu backbone bersama untuk 3 kepala -- perbandingan tidak "
        "sepenuhnya setara dan perlu disebut saat melaporkan."
    )

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(hasil, f, indent=2, ensure_ascii=False)
    print(f"\nTersimpan: {OUT_PATH}")


if __name__ == "__main__":
    main()
