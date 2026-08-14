// Kontrak tipe data — HARUS tetap sinkron dengan kontrak API dari R3
// (lihat "role context/context-r4-frontend.md" bagian "Kontrak API yang kamu konsumsi").
// Kalau R3 mengubah bentuk response, ubah di sini dulu, TypeScript akan
// menunjukkan semua tempat yang harus diikuti.

export type ShipmentStatus = "AMAN" | "WASPADA" | "KRITIS";

export interface SensorReading {
  /** menit sejak awal perjalanan (dipakai untuk sumbu-x grafik) */
  t_min: number;
  temperature_c: number;
  ambient_temp_c?: number;
  door_open?: boolean;
}

export interface AnalyzeRequest {
  shipment_id: string;
  cargo_profile: string;
  readings: { timestamp?: string; temperature_c: number; ambient_temp_c?: number; door_open?: boolean }[];
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
  contribution: number; // 0..1, dijumlahkan idealnya ~1 di antara semua driver
}

export interface ActionStep {
  priority: number;
  text: string;
  eta_min: number;
}

export interface AnalyzeResponse {
  status: ShipmentStatus;
  time_to_breach_min: number | null; // null kalau status AMAN dan tidak relevan
  failure_mode: FailureMode;
  forecast: Forecast;
  drivers: Driver[];
  actions: ActionStep[];
}

/** Ambang batas suhu kargo, dipakai untuk pita ambang di grafik. Statis untuk demo. */
export interface CargoThreshold {
  min: number;
  max: number;
  label: string;
}

export interface ScenarioPreset {
  id: string;
  label: string;
  description: string;
  cargoProfile: string;
  threshold: CargoThreshold;
  csvPath: string;
}