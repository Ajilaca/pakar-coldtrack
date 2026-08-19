import {
  AnalyzeRequest,
  AnalyzeResponse,
  ChartPoint,
  ScenarioMeta,
  ScenarioPreset,
  TelemetryReading,
} from "./types";
import { mockAnalyze, mockScenarioReadings, MOCK_SCENARIOS } from "./mock";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Default true supaya frontend tetap bisa didemokan tanpa backend menyala.
// Set NEXT_PUBLIC_USE_MOCK=false di .env.local untuk memakai API asli.
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK !== "false";

export const usingMock = USE_MOCK;

export class ApiError extends Error {}

/**
 * Ambang tampilan per profil kargo — disalin dari backend/config.yaml
 * (blok `cargo_profiles`). Backend tidak mengirimkannya di respons, jadi
 * nilainya digandakan di sini. Kalau config.yaml berubah, samakan di sini.
 */
const THRESHOLD_BY_PROFILE: Record<string, { min: number; max: number; label: string }> = {
  vaksin_2_8C: { min: 2, max: 8, label: "Vaksin 2–8°C" },
  "daging_beku_-18C": { min: -25, max: -18, label: "Daging beku −25…−18°C" },
  buah_segar_2_4C: { min: 2, max: 4, label: "Buah & sayur 2–4°C" },
  ikan_segar_0_5C: { min: 0, max: 5, label: "Ikan segar 0–5°C" },
  produk_susu_2_4C: { min: 2, max: 4, label: "Produk susu 2–4°C" },
};
const DEFAULT_THRESHOLD = { min: 2, max: 8, label: "Vaksin 2–8°C" };

export function thresholdFor(cargoProfile: string) {
  return THRESHOLD_BY_PROFILE[cargoProfile] ?? DEFAULT_THRESHOLD;
}

function metaToPreset(m: ScenarioMeta): ScenarioPreset {
  return {
    id: m.id,
    // judul backend berformat "Skenario 1: Perjalanan Normal (Kondisi Aman)" —
    // buang nomornya supaya muat di dropdown
    label: m.title.replace(/^Skenario\s*\d+:\s*/i, ""),
    description: m.description,
    cargoProfile: m.cargo_profile,
    threshold: thresholdFor(m.cargo_profile),
  };
}

/** Daftar skenario demo. */
export async function fetchScenarios(): Promise<ScenarioPreset[]> {
  if (USE_MOCK) return MOCK_SCENARIOS;

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/scenarios`);
  } catch {
    throw new ApiError("Tidak bisa menghubungi server. Pastikan backend berjalan di " + API_URL + ".");
  }
  if (!res.ok) throw new ApiError(`Gagal memuat daftar skenario (${res.status}).`);
  const list: ScenarioMeta[] = await res.json();
  return list.map(metaToPreset);
}

/**
 * Telemetri satu skenario, dalam bentuk kawat backend.
 *
 * Bacaan ini dikirim kembali apa adanya ke POST /analyze — itulah yang
 * menghilangkan seluruh risiko ketidakcocokan nama field.
 */
export async function fetchScenarioReadings(scenarioId: string): Promise<TelemetryReading[]> {
  if (USE_MOCK) return mockScenarioReadings(scenarioId);

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/scenarios/${scenarioId}`);
  } catch {
    throw new ApiError("Tidak bisa menghubungi server analisis.");
  }
  if (!res.ok) throw new ApiError(`Gagal memuat skenario "${scenarioId}" (${res.status}).`);
  const data = await res.json();
  const readings: TelemetryReading[] = data.readings ?? [];
  if (readings.length === 0) throw new ApiError("Skenario tidak berisi bacaan.");
  return readings;
}

export async function analyzeShipment(
  payload: AnalyzeRequest,
  scenarioId?: string
): Promise<AnalyzeResponse> {
  if (USE_MOCK) return mockAnalyze(payload, scenarioId);

  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiError("Tidak bisa menghubungi server analisis. Periksa koneksi atau status backend.");
  }

  if (res.status === 400 || res.status === 422) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body?.detail === "string" ? ` ${body.detail}` : "";
    } catch {
      /* biarkan kosong */
    }
    throw new ApiError(`Data yang dikirim ditolak server (${res.status}).${detail}`);
  }
  if (!res.ok) throw new ApiError(`Server mengembalikan error (${res.status}). Coba lagi sebentar.`);

  return res.json();
}

/** Ubah bacaan kawat backend jadi titik siap-gambar untuk grafik & peta. */
export function toChartPoints(readings: TelemetryReading[]): ChartPoint[] {
  if (readings.length === 0) return [];
  const t0 = new Date(readings[0].ts).getTime();

  return readings.map((r, i) => {
    const t = new Date(r.ts).getTime();
    const t_min = Number.isFinite(t) && Number.isFinite(t0) ? Math.round((t - t0) / 60000) : i;
    return {
      t_min,
      temp_c: r.temp_c,
      ambient_c: r.ambient_c,
      door_open: r.door_open,
      lat: r.lat,
      lon: r.lon,
    };
  });
}
