import { AnalyzeRequest, AnalyzeResponse, ScenarioPreset, TelemetryReading } from "./types";

/**
 * Lapisan tiruan — dipakai saat NEXT_PUBLIC_USE_MOCK tidak di-set ke "false",
 * supaya antarmuka tetap bisa didemokan tanpa backend menyala.
 *
 * PENTING: id, judul, profil kargo, mode kegagalan, keyakinan, dan TTB di
 * bawah ini disalin PERSIS dari backend/data/scenarios/*.json. Tujuannya agar
 * demo mode tiruan dan demo mode asli menampilkan angka yang sama — jangan
 * sampai naskah demo dihafal dari angka karangan lalu berubah di hari-H.
 */

const JAKARTA: [number, number] = [-6.2118, 106.8456];
const BANDUNG: [number, number] = [-6.9175, 107.6191];

/** Deterministik (bukan Math.random) supaya bentuk grafik selalu identik. */
function wobble(i: number, amp: number) {
  return amp * (Math.sin(i * 1.3) * 0.5 + Math.sin(i * 0.41) * 0.5);
}

interface MockSpec {
  id: string;
  label: string;
  description: string;
  cargoProfile: string;
  threshold: { min: number; max: number; label: string };
  n: number;
  /** suhu kargo pada menit ke-t */
  temp: (t: number, i: number, n: number) => number;
  ambient: (t: number, i: number, n: number) => number;
  door?: (t: number, i: number, n: number) => boolean;
  reefer?: (t: number, i: number, n: number) => boolean;
  response: Omit<AnalyzeResponse, "forecast"> & { forecast?: AnalyzeResponse["forecast"] };
}

const SPECS: MockSpec[] = [
  {
    id: "scenario_1_normal",
    label: "Perjalanan Normal (Kondisi Aman)",
    description: "Reefer aktif konsisten sepanjang perjalanan, suhu terkendali di dalam pita aman.",
    cargoProfile: "vaksin_2_8C",
    threshold: { min: 2, max: 8, label: "Vaksin 2–8°C" },
    n: 125,
    temp: (t, i) => 4.8 + wobble(i, 0.35),
    ambient: (t, i) => 29 + wobble(i, 1.6),
    response: {
      status: "AMAN",
      time_to_breach_min: null,
      failure_mode: { label: "Tidak ada anomali terdeteksi (A0)", confidence: 0.876 },
      drivers: [
        { feature: "Kestabilan suhu 30 menit", value: "±0,4 °C", contribution: 0.46 },
        { feature: "Reefer aktif", value: "100% waktu", contribution: 0.33 },
        { feature: "Status pintu", value: "tertutup", contribution: 0.21 },
      ],
      actions: [
        { priority: 1, text: "Lanjutkan pemantauan rutin sesuai SOP.", eta_min: null },
        { priority: 2, text: "Catat perjalanan ini sebagai baseline referensi.", eta_min: null },
      ],
    },
  },
  {
    id: "scenario_2_door_open",
    label: "Pintu Kargo Terbuka Terlalu Lama",
    description: "Pintu kargo terbuka saat bongkar muat, memicu lonjakan suhu tajam.",
    cargoProfile: "daging_beku_-18C",
    threshold: { min: -25, max: -18, label: "Daging beku −25…−18°C" },
    n: 150,
    temp: (t, i, n) => {
      const a = n * 0.55, b = n * 0.72;
      if (i < a) return -21 + wobble(i, 0.5);
      if (i <= b) return -21 + ((i - a) / (b - a)) * 6.5;
      return -14.5 - Math.min(4, (i - b) * 0.06) + wobble(i, 0.4);
    },
    ambient: (t, i) => 31 + wobble(i, 2),
    door: (t, i, n) => i >= n * 0.55 && i <= n * 0.72,
    response: {
      status: "KRITIS",
      time_to_breach_min: 19,
      failure_mode: { label: "Pintu kargo terbuka terlalu lama (A1)", confidence: 1.0 },
      drivers: [
        { feature: "Durasi pintu terbuka", value: "24 menit", contribution: 0.52 },
        { feature: "Laju kenaikan suhu", value: "+0,27 °C/mnt", contribution: 0.29 },
        { feature: "Suhu ambien", value: "31 °C", contribution: 0.19 },
      ],
      actions: [
        { priority: 1, text: "Hubungi pengemudi: pastikan pintu kargo tertutup rapat sekarang.", eta_min: 2 },
        { priority: 2, text: "Turunkan setpoint reefer ke batas bawah untuk pemulihan cepat.", eta_min: 5 },
        { priority: 3, text: "Siapkan pemeriksaan mutu di titik bongkar berikutnya.", eta_min: 20 },
      ],
    },
  },
  {
    id: "scenario_3_compressor_degradation",
    label: "Kompresor Melemah Bertahap",
    description: "Kapasitas pendinginan meluruh perlahan — terlalu halus untuk disadari manusia.",
    cargoProfile: "produk_susu_2_4C",
    threshold: { min: 2, max: 4, label: "Produk susu 2–4°C" },
    n: 150,
    temp: (t, i, n) => 2.6 + (i / n) * 2.0 + wobble(i, 0.18),
    ambient: (t, i) => 30 + wobble(i, 1.5),
    response: {
      status: "KRITIS",
      time_to_breach_min: 20,
      failure_mode: { label: "Degradasi bertahap unit pendingin", confidence: 0.351 },
      drivers: [
        { feature: "Laju kenaikan suhu", value: "+0,013 °C/mnt", contribution: 0.44 },
        { feature: "Selisih suhu vs setpoint", value: "+1,8 °C", contribution: 0.34 },
        { feature: "Beban kerja reefer", value: "naik terus", contribution: 0.22 },
      ],
      actions: [
        { priority: 1, text: "Hubungi pengemudi: hentikan di titik teduh terdekat.", eta_min: 5 },
        { priority: 2, text: "Periksa tekanan refrigeran dan kondisi kondensor.", eta_min: 15 },
        { priority: 3, text: "Siapkan opsi pemindahan muatan bila tren berlanjut.", eta_min: 25 },
      ],
    },
  },
  {
    id: "scenario_4_sensor_stuck",
    label: "Sensor Macet (Stuck-at)",
    description: "Sensor membeku pada satu nilai sementara suhu kargo sesungguhnya terus berubah.",
    cargoProfile: "buah_segar_2_4C",
    threshold: { min: 2, max: 4, label: "Buah & sayur 2–4°C" },
    n: 150,
    temp: (t, i, n) => (i <= n * 0.6 ? 3.1 + wobble(i, 0.25) : 3.1),
    ambient: (t, i) => 30 + wobble(i, 1.8),
    response: {
      status: "WASPADA",
      time_to_breach_min: 20,
      failure_mode: { label: "Masalah sensor — pembacaan macet", confidence: 0.494 },
      drivers: [
        { feature: "Variansi suhu 30 menit", value: "0,00 °C", contribution: 0.57 },
        { feature: "Ketidakcocokan vs ambien", value: "tidak wajar", contribution: 0.26 },
        { feature: "Durasi nilai identik", value: "60 menit", contribution: 0.17 },
      ],
      actions: [
        { priority: 1, text: "Verifikasi suhu manual dengan termometer cadangan.", eta_min: 10 },
        { priority: 2, text: "Jangan ambil keputusan dari sensor ini sampai diverifikasi.", eta_min: null },
        { priority: 3, text: "Jadwalkan kalibrasi ulang sensor setelah perjalanan.", eta_min: null },
      ],
    },
  },
  {
    id: "scenario_5_extreme_ambient",
    label: "Kejut Suhu Ambien saat Macet",
    description: "Kendaraan berhenti lama di bawah radiasi matahari tinggi, beban termal melonjak.",
    cargoProfile: "produk_susu_2_4C",
    threshold: { min: 2, max: 4, label: "Produk susu 2–4°C" },
    n: 150,
    temp: (t, i, n) => {
      const s = n * 0.5;
      if (i < s) return 2.8 + wobble(i, 0.2);
      return 2.8 + Math.min(2.4, (i - s) * 0.035) + wobble(i, 0.2);
    },
    ambient: (t, i, n) => (i < n * 0.5 ? 30 + wobble(i, 1.5) : 38 + wobble(i, 1.2)),
    response: {
      status: "WASPADA",
      time_to_breach_min: 20,
      failure_mode: { label: "Beban panas ambien berlebih saat berhenti (A7)", confidence: 1.0 },
      drivers: [
        { feature: "Suhu ambien", value: "38 °C", contribution: 0.48 },
        { feature: "Kecepatan kendaraan", value: "0 km/j (macet)", contribution: 0.31 },
        { feature: "Radiasi matahari", value: "tinggi", contribution: 0.21 },
      ],
      actions: [
        { priority: 1, text: "Arahkan kendaraan ke area teduh atau lanjut jalan.", eta_min: 5 },
        { priority: 2, text: "Naikkan daya reefer sementara beban ambien tinggi.", eta_min: 8 },
        { priority: 3, text: "Pantau ulang dalam 15 menit.", eta_min: 15 },
      ],
    },
  },
];

export const MOCK_SCENARIOS: ScenarioPreset[] = SPECS.map((s) => ({
  id: s.id,
  label: s.label,
  description: s.description,
  cargoProfile: s.cargoProfile,
  threshold: s.threshold,
}));

/** Bacaan tiruan dalam BENTUK KAWAT BACKEND, termasuk lat/lon Jakarta→Bandung. */
export function mockScenarioReadings(scenarioId: string): TelemetryReading[] {
  const spec = SPECS.find((s) => s.id === scenarioId) ?? SPECS[0];
  const start = Date.UTC(2026, 7, 19, 1, 0, 0); // 08:00 WIB
  const stepMin = 1;

  return Array.from({ length: spec.n }, (_, i) => {
    const t = i * stepMin;
    const f = i / (spec.n - 1);
    return {
      ts: new Date(start + t * 60000).toISOString(),
      temp_c: Math.round(spec.temp(t, i, spec.n) * 10) / 10,
      humidity: Math.round((68 + wobble(i, 6)) * 10) / 10,
      ambient_c: Math.round(spec.ambient(t, i, spec.n) * 10) / 10,
      door_open: spec.door ? spec.door(t, i, spec.n) : false,
      reefer_on: spec.reefer ? spec.reefer(t, i, spec.n) : true,
      lat: Math.round((JAKARTA[0] + (BANDUNG[0] - JAKARTA[0]) * f) * 1e4) / 1e4,
      lon: Math.round((JAKARTA[1] + (BANDUNG[1] - JAKARTA[1]) * f) * 1e4) / 1e4,
      speed_kmh: Math.round(Math.max(0, 52 + wobble(i, 22)) * 10) / 10,
      harsh_events: 0,
      solar_radiation: Math.round(Math.max(0, 620 + wobble(i, 180))),
    };
  });
}

/** Heuristik kasar untuk CSV unggahan pengguna — BUKAN model AI sungguhan. */
function heuristicAnalyze(readings: TelemetryReading[]): AnalyzeResponse {
  const last = readings[readings.length - 1];
  const first = readings[0];
  const dt = Math.max(1, (new Date(last.ts).getTime() - new Date(first.ts).getTime()) / 60000);
  const rate = (last.temp_c - first.temp_c) / dt;
  const upper = 8;

  const t15 = Math.round((last.temp_c + rate * 15) * 10) / 10;
  const t30 = Math.round((last.temp_c + rate * 30) * 10) / 10;
  const t60 = Math.round((last.temp_c + rate * 60) * 10) / 10;

  const ttb = rate > 0.001 ? Math.round(((upper - last.temp_c) / rate) * 10) / 10 : null;
  let status: AnalyzeResponse["status"] = "AMAN";
  if (ttb !== null && ttb < 30) status = "KRITIS";
  else if (ttb !== null && ttb < 90) status = "WASPADA";
  else if (last.temp_c > upper) status = "KRITIS";

  return {
    status,
    time_to_breach_min: status === "AMAN" ? null : ttb,
    failure_mode: {
      label: rate > 0.02 ? "Kenaikan suhu bertahap (kemungkinan degradasi pendingin)" : "Tidak ada anomali signifikan",
      confidence: 0.6,
    },
    forecast: { t15, t30, t60 },
    drivers: [
      { feature: "Laju kenaikan suhu", value: `${rate.toFixed(3)} °C/mnt`, contribution: 0.6 },
      { feature: "Suhu bacaan terakhir", value: `${last.temp_c} °C`, contribution: 0.4 },
    ],
    actions:
      status === "AMAN"
        ? [{ priority: 1, text: "Lanjutkan pemantauan rutin.", eta_min: null }]
        : [
            { priority: 1, text: "Periksa unit pendingin dan segel pintu kargo.", eta_min: 10 },
            { priority: 2, text: "Siapkan opsi pemindahan muatan bila tren berlanjut.", eta_min: 20 },
          ],
  };
}

export async function mockAnalyze(payload: AnalyzeRequest, scenarioId?: string): Promise<AnalyzeResponse> {
  // Jeda buatan supaya skeleton loader terlihat wajar saat demo.
  await new Promise((r) => setTimeout(r, 850));

  const spec = scenarioId ? SPECS.find((s) => s.id === scenarioId) : undefined;
  if (spec) {
    const last = payload.readings[payload.readings.length - 1];
    const base = last?.temp_c ?? 5;
    const slope = spec.response.status === "AMAN" ? 0 : 0.05;
    return {
      ...spec.response,
      forecast:
        spec.response.forecast ?? {
          t15: Math.round((base + slope * 15) * 10) / 10,
          t30: Math.round((base + slope * 30) * 10) / 10,
          t60: Math.round((base + slope * 60) * 10) / 10,
        },
      model_version: "mock-offline",
      inference_ms: 0,
    };
  }

  return heuristicAnalyze(payload.readings);
}
