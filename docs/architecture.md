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
* **Inference Engine**: Dual ONNXRuntime CPU sessions (`coldtrack.onnx` and `coldtrack_ttb.onnx`).
* **Configuration**: Centralized `config.yaml` loaded via `pydantic-settings` / PyYAML.
* **Logging**: Structured JSON log stdout via `structlog`.
* **Testing**: `pytest` + `httpx.TestClient` with 23 automated integration and unit tests.

### 2.2 Frontend (`frontend/`)
* **Framework**: Next.js 14 App Router, TypeScript.
* **Styling**: Tailwind CSS + `shadcn/ui` UI component library.
* **Visualization**: Recharts for temperature timeseries and multi-horizon prediction curves.
* **State Management**: Local React state, zero Redux/Zustand overhead.

### 2.3 Machine Learning Artifacts (`ml/` & `backend/models/`)
* **`coldtrack.onnx`**: 2-layer GRU backbone (~55k parameters) trained multi-task for temperature forecast and 7-class failure mode classification.
* **`coldtrack_ttb.onnx`**: XGBoost regressor (300 trees) trained specifically for high-accuracy short-horizon Time-to-Breach estimation (MAE 3.46 min at $\le 10$ min horizon).
* **`labels.json`**: Metadata defining model feature inputs, failure mode class labels, and scaling params.

---

## 3. Data Flow & Processing Lifecycle

1. **Payload Receipt**: Next.js POSTs telemetry payload with 60 minute readings to `/api/v1/analyze`.
2. **Validation**: Pydantic checks payload schema and ensures sequence length $\ge 60$. Payloads $< 60$ return HTTP 400.
3. **Preprocessing**: Telemetry is converted to Pandas DataFrame. Derived features ($\Delta \text{temp}$, $\Delta \text{ambient}$, $\text{reefer\_duration\_min}$, $\text{hour\_of\_day}$) are computed. Forbidden columns (`is_anomaly`, `failure_mode`, `time_to_breach`) are strictly guarded.
4. **Tensor Assembly**: Data is formatted as a `[1, 60, 12]` float32 tensor.
5. **Dual ONNX Inference**:
   * `coldtrack.onnx` returns temperature forecasts $(T_{15}, T_{30}, T_{60})$ and failure mode probabilities.
   * `coldtrack_ttb.onnx` returns raw Time-to-Breach minutes.
6. **TTB Gating**: If failure mode is healthy (`normal_sehat` / `A0`) or TTB exceeds 30 minutes display cap, TTB is set to `null`.
7. **Risk & Action Engine**: Evaluates Cargo Risk Index ($0.0 - 1.0$), classifies status (`AMAN`, `WASPADA`, `KRITIS`), and generates 3 priority recommendations.
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
