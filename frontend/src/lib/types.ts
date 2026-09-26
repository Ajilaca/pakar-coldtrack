// Must stay in sync with backend/app/schemas.py.

export type ShipmentStatus = "AMAN" | "WASPADA" | "KRITIS";

export interface TelemetryReading {
  ts: string;
  temp_c: number;
  humidity: number;
  ambient_c: number;
  door_open: boolean;
  reefer_on: boolean;
  speed_kmh: number;
  harsh_events: number;
}

export interface AnalyzeRequest {
  shipment_id: string;
  cargo_profile: string;
  mass_kg?: number;
  readings: TelemetryReading[];
}

export interface FailureMode {
  label: string;
  confidence: number;
}

export interface Forecast {
  t15: number;
  t30: number;
  t60: number;
}

export interface Driver {
  feature: string;
  value: string;
  contribution: number;
}

export interface ActionStep {
  priority: number;
  text: string;
  eta_min: number | null;
}

export interface AnalyzeResponse {
  status: ShipmentStatus;
  risk_index: number;
  time_to_breach_min: number | null;
  ttb_model_min: number | null;
  failure_mode: FailureMode;
  forecast: Forecast;
  drivers: Driver[];
  actions: ActionStep[];
  model_version: string;
  inference_ms: number;
}

export interface CargoProfile {
  id: string;
  name: string;
  min: number;
  max: number;
  critical: number;
}

export interface ConditionInput {
  shipmentId: string;
  cargoProfile: string;
  massKg: number;
  tempNow: number;
  temp60Ago: number;
  ambient: number;
  humidity: number;
  doorOpen: boolean;
  doorMinutes: number;
  moving: boolean;
  stoppedMinutes: number;
}
