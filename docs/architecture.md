# System Architecture — ColdTrack AI

## 1. Overview & Architectural Philosophy

ColdTrack AI is designed as a **synchronous, stateless, single-transaction AI cold-chain risk evaluation platform**. The system takes 60-minute sliding windows of IoT telemetry readings (temperature, humidity, vehicle dynamics, ambient environmental conditions) and outputs:
1. Multi-horizon temperature forecasts ($t+15, t+30, t+60$ minutes).
2. Failure mode diagnosis across 7 operational anomaly classes.
3. Time-to-Breach (TTB) countdown in minutes before cargo safe thermal thresholds are violated.
4. Cargo Risk Index ($0.0 - 1.0$) and status classification (`AMAN`, `WASPADA`, `KRITIS`).
5. 3 prioritized response actions with ETA estimates.
6. Top 3 feature contribution drivers explaining the prediction rationale.

The architecture strictly adheres to a **zero-side-effect, zero-database design** to ensure single-command deployment (`docker compose up --build`), sub-5ms response latency, and bulletproof reliability during live competition demonstrations.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND INTERFACE                                 │
│                   Next.js 14 App Router + Tailwind CSS + Recharts               │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
                        POST /api/v1/analyze (HTTP/1.1 JSON)
                                         │
┌────────────────────────────────────────▼────────────────────────────────────────┐
│                              BACKEND FASTAPI ENGINE                             │
│                      Uvicorn Single-Worker Process (Python 3.11)                │
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │ 1. Pydantic v2 Input Validation (min_length=60, type checks)            │   │
│   └────────────────────────────────────┬────────────────────────────────────┘   │
│                                        │                                        │
│   ┌────────────────────────────────────▼────────────────────────────────────┐   │
│   │ 2. Preprocessing & Derived Feature Pipeline                             │   │
│   │    - Delta Temp, Delta Ambient, Reefer Duration, Hour of Day            │   │
│   │    - Target Leakage Guard & [1, 60, 12] Tensor Assembly                 │   │
│   └────────────────────────────────────┬────────────────────────────────────┘   │
│                                        │                                        │
│   ┌────────────────────────────────────▼────────────────────────────────────┐   │
│   │ 3. Dual-ONNX Runtime CPU Inference Engine                               │   │
│   │    ├─ coldtrack.onnx     ──► Forecast (t15,t30,t60) + Failure Probs(7)  │   │
│   │    └─ coldtrack_ttb.onnx ──► Dedicated Time-to-Breach Regression        │   │
│   └────────────────────────────────────┬────────────────────────────────────┘   │
│                                        │                                        │
│   ┌────────────────────────────────────▼────────────────────────────────────┐   │
│   │ 4. Cargo Risk Index Scorer & Status Classifier                          │   │
│   │    - Risk = 0.4*Temp + 0.25*Rate + 0.2*Reefer + 0.15*Door              │   │
│   └────────────────────────────────────┬────────────────────────────────────┘   │
│                                        │                                        │
│   ┌────────────────────────────────────▼────────────────────────────────────┐   │
│   │ 5. Deterministic Action & Feature Explanation Engine                    │   │
│   │    - 3 Priority Actions + Feature Contribution Drivers                  │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │
                             Single JSON Response Payload
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                               USER DASHBOARD CARD                               │
│       Status Badge │ TTB Big Number │ Forecast Chart │ Priority Actions             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Components Breakdown

### 2.1 Backend (`backend/`)
* **Framework**: FastAPI (Python 3.11), Uvicorn single-worker runner.
* **Validation**: Pydantic v2 schemas (`AnalyzeRequest`, `AnalyzeResponse`, `TelemetryReading`).
* **Inference Engine** (`app/inference.py`): physics/rule engine (`app/core/engine.py`) for status and
  displayed TTB, plus one **diagnosis provider** (two ONNX Runtime CPU sessions) for forecast,
  failure mode and an informational ML TTB. See §2.4.
* **Configuration**: Centralized `config.yaml` loaded via `pydantic-settings` / PyYAML.
* **Logging**: Structured JSON log stdout via `structlog`.
* **Testing**: `pytest` + `httpx.TestClient`, 33 tests including ONNX v3 vs PyTorch parity, loading of
  both diagnosis providers and `/analyze` end-to-end with each (`tests/test_providers.py`).

### 2.2 Frontend (`frontend/`)
* **Framework**: Next.js 14 App Router, TypeScript.
* **Styling**: Tailwind CSS + `shadcn/ui` UI component library.
* **Visualization**: Recharts for temperature timeseries and multi-horizon prediction curves.
* **State Management**: Local React state, zero Redux/Zustand overhead.

### 2.3 Machine Learning Artifacts (`ml/` & `backend/models/`)
| File (`backend/models/`) | Provider | What it is |
|---|---|---|
| `coldtrack_v3.onnx` (= `ml/reports/coldtrack_b3.onnx`) | **v3, default** | GRU 3 layers x hidden 128 + window summary stats; input `window [n, 60, 12]` raw; outputs forecast t+15/30/60, 7-class `failure_prob`, GRU TTB head (unused) |
| `coldtrack_v3.labels.json` | v3 | class order, configuration, metrics, limitations |
| `coldtrack_ttb_window.onnx` (= `ml/reports/coldtrack_ttb.onnx`) | v3 | XGBoost Time-to-Breach (300 trees), same window input; informational `ttb_model_min` |
| `coldtrack_gru.onnx` | checkpoint2 | previous GRU (inputs `x`, `s`): 3 events + cargo-temperature forecast |
| `coldtrack_ttb.onnx` | checkpoint2 | previous XGBoost TTB (input `features`) |

`ml/reports/coldtrack.onnx` (v2, proposal) is kept for traceability and benchmarks, not served.
Metrics, selection and limitations: `docs/model_card.md`; reproduction: `bench/README.md`.

### 2.4 Diagnosis provider and rollback
`config.yaml` → `model.diagnosis_provider` selects the source of `forecast` and `failure_mode`:

* `v3` (default since 2026-10-11, gate G3 approved with notes): 7 failure classes, API labels
  `normal_sehat`, `pintu_terbuka_lama`, `reefer_mati_total`, `kejutan_ambien_ekstrem`,
  `prapendinginan_buruk`, `degradasi_bertahap`, `masalah_sensor`, plus `probabilities` per class.
* `checkpoint2`: the previous model (3 events: `pintu_terbuka_lama`, `kejutan_ambien_ekstrem`,
  `masalah_sensor`), `probabilities: null`.

**Rollback to checkpoint-2:** set `diagnosis_provider: checkpoint2` in `backend/config.yaml` and restart
the backend. No code change; both providers are tested in CI. `diagnosis_provider` and
`model_version` in every response show which one answered.

Sensor faults come only from the rule layer: v3's own `masalah_sensor` class is never used as the
label (checkpoint-2's rule applies instead: another fault class only if p >= 0.5, else
`normal_sehat`). `probabilities` is sent only when the label equals the model's top class.

Rules shared by both providers: a sensor fault from the rule layer overrides the model label; the
label is never `normal_sehat` while status is WASPADA/KRITIS (rule-derived `pintu_terbuka` /
`suhu_muatan_mendekati_batas` instead). Status AMAN/WASPADA/KRITIS and displayed TTB always come from
the physics engine, whichever provider is active.

**Incomplete data.** The window models were trained only on 60-minute windows without missing
readings. If the last 60 readings contain a time gap > 90 s, the response sets
`data_lengkap: false` with `catatan_data`, and the failure-mode confidence is capped at 0.5 (a
conservative display choice, not a calibrated value). Status is unaffected.

---

## 3. Data Flow & Processing Lifecycle

1. **Payload Receipt**: Next.js POSTs telemetry payload with 60 minute readings to `/api/v1/analyze`.
2. **Validation**: Pydantic checks payload schema and ensures sequence length $\ge 60$. Payloads $< 60$ return HTTP 400.
3. **Preprocessing**: Telemetry is converted to Pandas DataFrame. Derived features ($\Delta \text{temp}$, $\Delta \text{ambient}$, $\text{reefer\_duration\_min}$, $\text{hour\_of\_day}$) are computed. Forbidden columns (`is_anomaly`, `failure_mode`, `time_to_breach`) are strictly guarded.
4. **Physics engine** (`app/core/engine.py`): cargo-temperature observer, physics TTB, sensor rules ->
   status `AMAN`/`WASPADA`/`KRITIS`, displayed TTB and reason. Independent of the ONNX models.
5. **Diagnosis provider** (§2.4): v3 slices `[n, 60, 12]` windows from the per-minute features
   (`preprocess.features_per_minute`, `reefer_duration_min` recounted per window as in training) and
   returns forecast + 7-class probabilities; the window XGBoost returns an informational TTB.
   checkpoint2 runs its own cleaning and inputs.
6. **Guards**: shared label rules (§2.4) and the incomplete-data flag.
7. **Action Engine**: 3 priority recommendations from status + failure label (`app/rules.py`).
8. **Response Return**: Single JSON object is returned to UI in $< 5\text{ ms}$.

---

## 4. Empirical Latency Profile

Measured across 100 benchmark iterations per scenario using `httpx.TestClient`:

| Scenario ID | Primary Condition | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|---|
| `scenario_1_normal` | Normal Healthy (A0) | 2.14 ms | 3.82 ms | 5.41 ms |
| `scenario_2_door_open` | Prolonged Door Open (A1) | 2.08 ms | 3.65 ms | 4.98 ms |
| `scenario_3_compressor_degradation` | Cooling Degradation (A2/A4) | 2.12 ms | 3.71 ms | 5.12 ms |
| `scenario_4_reefer_failure` | Total Reefer Failure (A3) | 2.15 ms | 3.80 ms | 5.30 ms |
| `scenario_5_extreme_ambient` | Ambient Thermal Shock (A7) | 2.09 ms | 3.68 ms | 5.05 ms |

---

## 5. MVP Compliance Matrix

| MVP Constraint | Implementation Status | Evidence / Verification |
|---|---|---|
| **Synchronous Processing Only** | Fully Compliant | No Celery/RQ/cron workers in `backend/requirements.txt` or `app/` |
| **No Database** | Fully Compliant | No ORM or SQL drivers; scenarios stored as static JSON files in `backend/data/scenarios/` |
| **No Authentication** | Fully Compliant | No JWT, session, or login endpoints; direct open REST endpoints |
| **One-Command Execution** | Fully Compliant | Runs via single `docker compose up --build` command |
| **Static Parameters** | Fully Compliant | Cargo profiles, risk weights, and model paths centralized in `config.yaml` |
