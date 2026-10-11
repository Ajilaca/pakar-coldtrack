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

// label: v3 (default) can return normal_sehat, pintu_terbuka_lama, reefer_mati_total,
// kejutan_ambien_ekstrem, prapendinginan_buruk, degradasi_bertahap, masalah_sensor, plus the
// rule-derived pintu_terbuka / suhu_muatan_mendekati_batas. Unknown labels must still render
// (lib/labels.ts falls back to a readable text).
export interface FailureMode {
  label: string;
  confidence: number;
  probabilities?: Record<string, number> | null; // v3 only
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
  diagnosis_provider?: string; // v3 | checkpoint2 | engine-only
  data_lengkap?: boolean; // false: readings missing in the last 60 -> diagnosis less reliable
  catatan_data?: string | null;
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
