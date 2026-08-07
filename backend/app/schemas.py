"""Pydantic v2 schemas for ColdTrack AI API requests and responses."""

from datetime import datetime

from pydantic import BaseModel, Field


class TelemetryReading(BaseModel):
    """Single IoT telemetry reading point."""

    ts: datetime
    temp_c: float = Field(..., description="Cargo temperature in °C")
    humidity: float = Field(..., description="Cargo relative humidity (%)")
    ambient_c: float = Field(..., description="Ambient temperature in °C")
    door_open: bool = Field(..., description="Cargo door open status")
    reefer_on: bool = Field(..., description="Reefer cooling unit active status")
    lat: float = Field(..., description="Vehicle latitude")
    lon: float = Field(..., description="Vehicle longitude")
    speed_kmh: float = Field(..., description="Vehicle speed in km/h")
    harsh_events: int = Field(0, description="Harsh driving events count in window")
    solar_radiation: float | None = Field(
        0.0, description="Solar radiation in W/m²"
    )


class AnalyzeRequest(BaseModel):
    """Payload for POST /api/v1/analyze endpoint."""

    shipment_id: str = Field(..., json_schema_extra={"example": "TRK-JKT-0417"})
    cargo_profile: str = Field("vaksin_2_8C", json_schema_extra={"example": "vaksin_2_8C"})
    readings: list[TelemetryReading] = Field(..., min_length=1)


class FailureMode(BaseModel):
    """Predicted failure mode and confidence level."""

    label: str = Field(..., json_schema_extra={"example": "degradasi_kompresor"})
    confidence: float = Field(..., ge=0.0, le=1.0, json_schema_extra={"example": 0.91})


class Forecast(BaseModel):
    """Temperature prediction for future time horizons."""

    t15: float = Field(..., description="Predicted temperature at +15 minutes (°C)")
    t30: float = Field(..., description="Predicted temperature at +30 minutes (°C)")
    t60: float = Field(..., description="Predicted temperature at +60 minutes (°C)")


class FeatureDriver(BaseModel):
    """Feature contribution explanation driver."""

    feature: str = Field(..., json_schema_extra={"example": "laju_kenaikan_suhu"})
    value: str = Field(..., json_schema_extra={"example": "+0.13 C/mnt"})
    contribution: float = Field(..., ge=0.0, le=1.0, json_schema_extra={"example": 0.44})


class RecommendedAction(BaseModel):
    """Prioritized recommended response action."""

    priority: int = Field(..., json_schema_extra={"example": 1})
    text: str = Field(..., json_schema_extra={"example": "Hubungi pengemudi: hentikan di titik teduh terdekat."})
    eta_min: int | None = Field(None, json_schema_extra={"example": 5})


class AnalyzeResponse(BaseModel):
    """Response returned by POST /api/v1/analyze."""

    status: str = Field(..., json_schema_extra={"example": "KRITIS"})
    risk_index: float = Field(..., ge=0.0, le=1.0, json_schema_extra={"example": 0.87})
    time_to_breach_min: float | None = Field(None, json_schema_extra={"example": 23.4})
    failure_mode: FailureMode
    forecast: Forecast
    drivers: list[FeatureDriver]
    actions: list[RecommendedAction]
    model_version: str = Field("v1-finetuned-on-v3", json_schema_extra={"example": "coldtrack-gru-v1.3"})
    inference_ms: int = Field(..., json_schema_extra={"example": 187})


class ScenarioMetadata(BaseModel):
    """Metadata summary of a demo scenario."""

    id: str
    title: str
    description: str
    cargo_profile: str
    expected_status: str
    reading_count: int
