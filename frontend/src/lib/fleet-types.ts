// Kontrak API armada (docs/api_contract.md §7, backend/app/fleet/queries.py). Harus sinkron dengan backend.

import { ActionStep, Driver, FailureMode, Forecast } from "./types";

export type FleetStatus =
  | "AMAN"
  | "WASPADA"
  | "KRITIS"
  | "DATA_TIDAK_LENGKAP"
  | "MENUNGGU_DATA"
  | "TIDAK_ADA_DATA"
  | "TANPA_TRIP";

export type Phase = "TERDETEKSI" | "DITUGASKAN" | "DITANGANI" | "SELESAI" | "GAGAL";

export interface Profil {
  id: string;
  nama: string;
  t_lo: number | null;
  t_hi: number | null;
  t_kritis: number | null;
}

export interface Kondisi {
  reason: string | null;
  risk_index: number | null;
  time_to_breach_min: number | null;
  ttb_model_min: number | null;
  forecast: Forecast | null;
  failure_mode: FailureMode | null;
  data_lengkap: boolean | null;
  catatan_data: string | null;
  t_cargo_est: number | null;
  model_version: string | null;
  provider: string | null;
}

export interface Bacaan {
  ts: string;
  temp_c: number;
  humidity: number;
  ambient_c: number;
  door_open: boolean;
  reefer_on: boolean;
  speed_kmh: number;
  lat: number | null;
  lon: number | null;
}

export interface Perangkat {
  id: string;
  online: boolean;
  battery_v: number | null;
  firmware: string | null;
  gateway_version: string | null;
  calibrated_at: string | null;
  last_status_at: string | null;
}

export interface Truk {
  truck_id: string;
  label: string | null;
  depot: { id: string; nama: string; kota: string };
  status: FleetStatus;
  last_ts: string | null;
  computed_at: string | null;
  trip: { id: number; profil: Profil | null; mass_kg: number | null; cargo_value_idr: number | null; started_at: string } | null;
  kondisi: Kondisi | null;
  bacaan_terakhir: Bacaan | null;
  sensor: { score: number | null; grade: string | null };
  perangkat: Perangkat | null;
  n_perlu_diperbarui: number;
  insiden_terbuka: { id: number; phase: Phase; status_puncak: string; detected_at: string; assignee: string | null } | null;
}

export interface SensorHealth {
  score: number | null;
  grade: string;
  alasan: string[];
  komponen: Record<string, number | null>;
}

export interface Temuan {
  jenis: "hardware" | "software";
  kode: string;
  tingkat: "waspada" | "kritis";
  pesan: string;
  device_id?: string;
  truck_id?: string;
}

export interface Notifikasi {
  id: number;
  created_at: string;
  truck_id: string | null;
  incident_id: number | null;
  level: "info" | "ok" | "waspada" | "kritis";
  title: string;
  body: string | null;
  read_at: string | null;
}

export interface TrukDetail extends Truk {
  sensor_health: SensorHealth | null;
  perlu_diperbarui: Temuan[] | null;
  insiden: Insiden[];
  notifikasi: Notifikasi[];
  drivers: Driver[];
  actions: ActionStep[];
  ambien_delta_10m: number | null;
  pintu_terakhir_dibuka: string | null;
  setpoint_c: number | null;
}

export interface Ringkasan {
  now: string;
  n_truk: number;
  n_trip_aktif: number;
  per_status: Record<FleetStatus, number>;
  kritis_vs_tidak: { kritis: number; tidak_kritis: number };
  per_diagnosis: Record<string, number>;
  per_grade_sensor: Record<string, number>;
  insiden_terbuka_per_fase: Record<string, number>;
  notifikasi_belum_dibaca: number;
  nilai_muatan_aktif_idr: number;
  kerugian_24j: RingkasanKerugian;
}

export interface Riwayat {
  truck_id: string;
  dari: string;
  sampai: string;
  profil: Profil | null;
  aktual: { ts: string; temp_c: number; ambient_c: number; door_open: boolean }[];
  prediksi: { ts: string; status: FleetStatus; forecast: Forecast | null; data_lengkap: boolean | null }[];
  garis_prediksi: { horizon_min: number; ts: string; temp_c: number }[] | null;
}

export interface Peta {
  depo: { id: string; nama: string; kota: string; lat: number; lon: number; status: FleetStatus | null; n_truk_aktif: number }[];
  truk: { truck_id: string; label: string | null; status: FleetStatus; online: boolean | null; lat: number | null; lon: number | null; ts: string | null; depot_id: string }[];
}

export interface SensorPerangkat extends Perangkat {
  truck_id: string;
  label: string | null;
  sensor_health: SensorHealth | null;
  n_perlu_diperbarui: number;
}

export interface DataSensor {
  perangkat: SensorPerangkat[];
  perlu_diperbarui: Temuan[];
  per_grade: Record<string, number>;
}

export interface LossInsiden {
  nilai_muatan_idr: number | null;
  nilai_berisiko_idr: number;
  kerugian_terjadi_idr: number;
  berhasil_diatasi_idr: number;
  lead_time_min: number | null;
  hasil: "breach" | "diatasi" | "terbuka" | "ditutup";
}

export interface RingkasanKerugian {
  nilai_berisiko_idr: number;
  kerugian_terjadi_idr: number;
  berhasil_diatasi_idr: number;
  n_insiden: number;
  n_breach: number;
  n_diatasi: number;
  lead_time_median_min: number | null;
  lead_time_rata_min: number | null;
  catatan: string;
}

export interface DataKerugian {
  dari: string;
  sampai: string;
  ringkasan: RingkasanKerugian;
  insiden: (LossInsiden & { incident_id: number; truck_id: string; phase: Phase; failure_label: string | null; detected_at: string; breach_at: string | null })[];
}

export interface EventInsiden {
  id: number;
  incident_id: number;
  at: string;
  actor: string;
  from_phase: Phase | null;
  to_phase: Phase;
  note: string | null;
  truck_id?: string;
}

export interface Insiden {
  id: number;
  truck_id: string;
  trip_id: number | null;
  jenis: "kondisi" | "data";
  phase: Phase;
  status_puncak: string;
  failure_label: string | null;
  detected_at: string;
  breach_at: string | null;
  recovered_at: string | null;
  closed_at: string | null;
  assignee: string | null;
  cargo_value_idr: number | null;
  label?: string | null;
  cargo_profile?: string | null;
  ttb_now_min?: number | null;
  last_event?: EventInsiden | null;
  loss?: LossInsiden;
  events?: EventInsiden[];
}
