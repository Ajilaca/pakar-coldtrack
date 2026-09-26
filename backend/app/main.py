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
from app.rules import generate_recommended_actions
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

    # df_features only feeds the heuristic driver panel (explain.py).
    _, df_features = prepare_onnx_input_tensor(payload.readings)

    # Status, TTB and risk come from the physics engine and never depend on ONNX.
    # If the GRU failed to load, forecast/diagnosis fall back to heuristics.
    model_version = settings.get("model", {}).get("version", "coldtrack-hybrid-v3")
    result = inference_engine.predict(payload.readings, payload.cargo_profile, payload.mass_kg)
    if result["forecast"] is None:
        forecast, failure_mode = _fallback_forecast(df_features, result["sensor_status"])
        model_version = "coldtrack-engine-only"
    else:
        forecast = Forecast(**result["forecast"])
        failure_mode = FailureMode(**result["failure_mode"])

    actions = generate_recommended_actions(
        status=result["status"],
        failure_label=failure_mode.label,
        cargo_profile=payload.cargo_profile,
    )
    drivers = compute_feature_drivers(df_features)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    logger.info("analyze", shipment_id=payload.shipment_id, status=result["status"], reason=result["reason"])

    return AnalyzeResponse(
        status=result["status"],
        risk_index=result["risk_index"],
        time_to_breach_min=result["time_to_breach_min"],
        ttb_model_min=result["ttb_model_min"],
        failure_mode=failure_mode,
        forecast=forecast,
        drivers=drivers,
        actions=actions,
        model_version=model_version,
        inference_ms=max(1, elapsed_ms),
    )


def _fallback_forecast(df_features: Any, sensor_status: int) -> tuple[Forecast, FailureMode]:
    """Linear extrapolation + simple diagnosis, used only when the GRU is unavailable."""
    latest = float(df_features["temp_c"].iloc[-1])
    rate = float(df_features["delta_temp"].iloc[-5:].mean())
    forecast = Forecast(**{f"t{h}": float(round(latest + rate * h, 2)) for h in (15, 30, 60)})

    if sensor_status == 2:
        failure_mode = FailureMode(label="masalah_sensor", confidence=0.9)
    elif int(df_features["door_open"].iloc[-1]) == 1:
        failure_mode = FailureMode(label="pintu_terbuka_lama", confidence=0.88)
    else:
        failure_mode = FailureMode(label="normal_sehat", confidence=0.9)
    return forecast, failure_mode
