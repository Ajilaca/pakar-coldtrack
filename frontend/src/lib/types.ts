// Kontrak tipe data — HARUS tetap sinkron dengan backend/app/schemas.py.
// Kalau R3 mengubah bentuknya, ubah di sini dulu; TypeScript akan menunjukkan
// semua tempat yang harus mengikuti.

export type ShipmentStatus = "AMAN" | "WASPADA" | "KRITIS";

/**
 * Bentuk bacaan SESUAI KAWAT BACKEND (backend/app/schemas.py :: TelemetryReading).
 *
 * Ini yang dikirim ke POST /api/v1/analyze. Sebelumnya frontend memakai nama
 * sendiri (`temperature_c`, `ambient_temp_c`) yang tidak pernah cocok dengan
 * backend, sehingga setiap permintaan asli ditolak 422. Sekarang frontend
 * memakai nama backend apa adanya — dan untuk skenario pra-set, bacaannya
 * DIAMBIL dari backend lalu dikirim balik tanpa diubah, jadi tidak ada lagi
 * peluang nama field meleset.
 */
export interface TelemetryReading {
  ts: string;
  temp_c: number;
  humidity: number;
  ambient_c: number;
  door_open: boolean;
  reefer_on: boolean;
  lat?: number | null;
  lon?: number | null;
  speed_kmh: number;
  harsh_events: number;
  solar_radiation?: number | null;
}

/** Bentuk yang dipakai grafik & peta — hasil turunan dari TelemetryReading. */
export interface ChartPoint {
  /** menit sejak awal perjalanan (sumbu-x grafik) */
  t_min: number;
  temp_c: number;
  ambient_c?: number;
  door_open?: boolean;
  lat?: number | null;
  lon?: number | null;
}

export interface AnalyzeRequest {
  shipment_id: string;
  cargo_profile: string;
  readings: TelemetryReading[];
}

export interface FailureMode {
  label: string;
  confidence: number; // 0..1
}

export interface Forecast {
  t15: number;
  t30: number;
  t60: number;
}

export interface Driver {
  feature: string;
  value: string;
  contribution: number; // 0..1
}

export interface ActionStep {
  priority: number;
  text: string;
  /** backend/app/schemas.py: `eta_min: int | None` — boleh kosong */
  eta_min: number | null;
}

export interface AnalyzeResponse {
  status: ShipmentStatus;
  time_to_breach_min: number | null;
  failure_mode: FailureMode;
  forecast: Forecast;
  drivers: Driver[];
  actions: ActionStep[];
  /** field berikut disediakan backend; dipakai untuk transparansi teknis */
  risk_index?: number;
  model_version?: string;
  inference_ms?: number;
}

/** Ambang batas suhu kargo — dipakai untuk pita ambang di grafik. */
export interface CargoThreshold {
  min: number;
  max: number;
  label: string;
}

/** Metadata skenario dari GET /api/v1/scenarios (schemas.py :: ScenarioMetadata). */
export interface ScenarioMeta {
  id: string;
  title: string;
  description: string;
  cargo_profile: string;
  expected_status: string;
  reading_count: number;
}

/** Skenario siap pakai di UI — gabungan metadata + ambang tampilan. */
export interface ScenarioPreset {
  id: string;
  label: string;
  description: string;
  cargoProfile: string;
  threshold: CargoThreshold;
}
