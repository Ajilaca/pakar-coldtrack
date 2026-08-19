"""ColdTrack AI Backend — Core FastAPI Service."""

import logging
import os
import time
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.explain import compute_feature_drivers
from app.inference import inference_engine
from app.preprocess import prepare_onnx_input_tensor
from app.rules import (
    compute_risk_index,
    evaluate_cargo_limits,
    generate_recommended_actions,
)
from app.scenarios import scenario_manager
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    FailureMode,
    Forecast,
    ScenarioMetadata,
)

# Structlog configuration for audit-trail JSON logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger("coldtrack.api")

ENABLE_LLM = os.getenv("ENABLE_LLM", "false").lower() == "true"

app = FastAPI(
    title="ColdTrack AI Backend",
    description="Synchronous AI-powered Cold Chain Telemetry Analysis Engine",
    version="1.0.0",
)

# Enable CORS for Next.js frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", summary="Docker healthcheck probe")
def health_check() -> dict[str, str]:
    """Healthcheck endpoint for Docker container status monitoring."""
    return {"status": "ok"}


@app.get(
    "/api/v1/scenarios",
    response_model=list[ScenarioMetadata],
    summary="List available demo scenarios",
)
def list_scenarios() -> list[ScenarioMetadata]:
    """Return metadata list of preset transport demo scenarios."""
    return scenario_manager.list_scenarios()


@app.get(
    "/api/v1/scenarios/{scenario_id}",
    summary="Get single scenario telemetry dataset",
)
def get_scenario(scenario_id: str) -> dict[str, Any]:
    """Retrieve full telemetry readings and metadata for a single demo scenario."""
    scenario = scenario_manager.get_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=404, detail=f"Scenario '{scenario_id}' not found"
        )
    return scenario


@app.post(
    "/api/v1/analyze",
    response_model=AnalyzeResponse,
    summary="Core analytical endpoint for telemetric cold chain risk prediction",
)
def analyze_telemetry(payload: AnalyzeRequest) -> AnalyzeResponse:
    """Process timeseries telemetry readings, execute ONNX model inference,

    evaluate risk rules, and return risk metrics, failure mode, temperature forecast,
    and priority response actions.
    """
    start_time = time.perf_counter()

    if not payload.readings:
        raise HTTPException(
            status_code=400, detail="Readings list cannot be empty"
        )

    # GRU fusion model computes internal summary stats (std, trend, etc.) over the
    # window. Padded windows produce incorrect std/trend and the model was never
    # trained on them, leading to silently degraded predictions.
    if len(payload.readings) < 60:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Minimum 60 readings required for reliable inference, "
                f"got {len(payload.readings)}."
            ),
        )

    # 1. Preprocessing & Feature Engineering
    tensor_3d, df_features = prepare_onnx_input_tensor(payload.readings)
    latest_temp = float(df_features["temp_c"].iloc[-1])

    # 2. Model Inference (ONNX or Fallback)
    model_version = settings.get("model", {}).get("version", "coldtrack-gru-v1.3")
    if inference_engine.is_ready:
        try:
            forecast_dict, failure_dict, ttb_predicted = inference_engine.predict(
                tensor_3d
            )
            forecast = Forecast(**forecast_dict)
            failure_mode = FailureMode(**failure_dict)
            time_to_breach = ttb_predicted
        except Exception as e:  # noqa: BLE001
            logger.warning(f"ONNX inference failed, utilizing rule engine: {e}")
            forecast, failure_mode, time_to_breach = _fallback_inference(
                latest_temp, df_features, payload.cargo_profile
            )
            model_version = "coldtrack-rule-v1.0"
    else:
        forecast, failure_mode, time_to_breach = _fallback_inference(
            latest_temp, df_features, payload.cargo_profile
        )
        model_version = "coldtrack-rule-v1.0"

    # 3. Cargo Risk Index & Status Evaluation
    # TTB ikut dikirim: status yang dihitung dari forecast saja bisa
    # bertentangan dengan TTB (lihat catatan di rules.py :: compute_risk_index).
    risk_index, status = compute_risk_index(
        current_temp=latest_temp,
        forecast=forecast.model_dump(),
        cargo_profile=payload.cargo_profile,
        df_features=df_features,
        time_to_breach_min=time_to_breach,
        failure_label=failure_mode.label,
    )

    # Heuristic TTB fallback if ONNX returned None during warning or critical status
    if time_to_breach is None and status in ["WASPADA", "KRITIS"]:
        limits = evaluate_cargo_limits(payload.cargo_profile)
        max_limit = limits["max_temp_c"]
        delta_temp_avg = float(df_features["delta_temp"].iloc[-5:].mean())
        if latest_temp >= max_limit:
            time_to_breach = 0.0
        elif delta_temp_avg > 0:
            time_to_breach = float(round((max_limit - latest_temp) / delta_temp_avg, 1))

    # 4. Recommended Actions & Driver Explanations
    actions = generate_recommended_actions(
        status=status,
        failure_label=failure_mode.label,
        cargo_profile=payload.cargo_profile,
    )
    drivers = compute_feature_drivers(df_features)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    return AnalyzeResponse(
        status=status,
        risk_index=risk_index,
        time_to_breach_min=time_to_breach,
        failure_mode=failure_mode,
        forecast=forecast,
        drivers=drivers,
        actions=actions,
        model_version=model_version,
        inference_ms=max(1, elapsed_ms),
    )


def _fallback_inference(
    latest_temp: float, df_features: Any, cargo_profile: str
) -> tuple:
    """Heuristic fallback when ONNX model is uninitialized."""
    delta_temp = float(df_features["delta_temp"].iloc[-5:].mean())
    limits = evaluate_cargo_limits(cargo_profile)
    max_limit = limits["max_temp_c"]

    t15 = float(round(latest_temp + delta_temp * 15, 2))
    t30 = float(round(latest_temp + delta_temp * 30, 2))
    t60 = float(round(latest_temp + delta_temp * 60, 2))
    forecast = Forecast(t15=t15, t30=t30, t60=t60)

    door_open = int(df_features["door_open"].iloc[-1])
    reefer_on = int(df_features["reefer_on"].iloc[-1])

    if door_open == 1:
        failure_mode = FailureMode(label="pintu_terbuka_lama", confidence=0.88)
    elif reefer_on == 0:
        failure_mode = FailureMode(label="kegagalan_reefer_total", confidence=0.92)
    elif delta_temp > 0.05:
        failure_mode = FailureMode(label="degradasi_kompresor", confidence=0.85)
    else:
        failure_mode = FailureMode(label="normal_sehat", confidence=0.95)

    if delta_temp > 0 and latest_temp < max_limit:
        ttb = float(round((max_limit - latest_temp) / delta_temp, 1))
    elif latest_temp >= max_limit:
        ttb = 0.0
    else:
        ttb = None

    return forecast, failure_mode, ttb
