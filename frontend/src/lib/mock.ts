import { AnalyzeRequest, AnalyzeResponse, SensorReading } from "./types";
import { SCENARIO_MOCK_RESPONSES } from "./scenario-data";

/**
 * Endpoint tiruan (mock) — dipakai selama R3 belum menyelesaikan /api/v1/analyze asli.
 * Begitu endpoint asli tersedia, cukup set NEXT_PUBLIC_USE_MOCK=false di .env.local
 * (tidak perlu ubah komponen manapun, lihat lib/api.ts).
 */

function heuristicMockAnalyze(readings: SensorReading[]): AnalyzeResponse {
  // Heuristik kasar untuk CSV yang diunggah pengguna sendiri (bukan salah satu
  // dari 5 skenario pra-set) — hanya untuk pengembangan, BUKAN model AI sungguhan.
  if (readings.length < 2) {
    return {
      status: "AMAN",
      time_to_breach_min: null,
      failure_mode: { label: "Data tidak cukup untuk dianalisis", confidence: 0.3 },
      forecast: { t15: readings[0]?.temperature_c ?? 5, t30: readings[0]?.temperature_c ?? 5, t60: readings[0]?.temperature_c ?? 5 },
      drivers: [],
      actions: [{ priority: 1, text: "Unggah data dengan lebih banyak titik bacaan.", eta_min: 0 }],
    };
  }

  const last = readings[readings.length - 1];
  const first = readings[0];
  const dt = last.t_min - first.t_min || 1;
  const rate = (last.temperature_c - first.temperature_c) / dt; // °C per menit
  const upperThreshold = 8; // asumsi profil vaksin 2-8°C untuk mode heuristik

  const t15 = Math.round((last.temperature_c + rate * 15) * 10) / 10;
  const t30 = Math.round((last.temperature_c + rate * 30) * 10) / 10;
  const t60 = Math.round((last.temperature_c + rate * 60) * 10) / 10;

  const minutesToBreach =
    rate > 0.001 ? Math.round(((upperThreshold - last.temperature_c) / rate) * 10) / 10 : null;

  let status: AnalyzeResponse["status"] = "AMAN";
  if (minutesToBreach !== null && minutesToBreach < 30) status = "KRITIS";
  else if (minutesToBreach !== null && minutesToBreach < 90) status = "WASPADA";
  else if (last.temperature_c > upperThreshold) status = "KRITIS";

  return {
    status,
    time_to_breach_min: status === "AMAN" ? null : minutesToBreach,
    failure_mode: {
      label: rate > 0.02 ? "Kenaikan suhu bertahap (kemungkinan degradasi unit pendingin)" : "Tidak ada anomali signifikan",
      confidence: 0.6,
    },
    forecast: { t15, t30, t60 },
    drivers: [
      { feature: "Laju kenaikan suhu", value: `${rate.toFixed(3)}°C/menit`, contribution: 0.6 },
      { feature: "Suhu bacaan terakhir", value: `${last.temperature_c}°C`, contribution: 0.4 },
    ],
    actions:
      status === "AMAN"
        ? [{ priority: 1, text: "Lanjutkan pemantauan rutin.", eta_min: 0 }]
        : [
            { priority: 1, text: "Periksa kondisi unit pendingin dan segel pintu kargo.", eta_min: 10 },
            { priority: 2, text: "Siapkan opsi pemindahan muatan bila tren berlanjut.", eta_min: 20 },
          ],
  };
}

export async function mockAnalyze(
  payload: AnalyzeRequest,
  scenarioId?: string
): Promise<AnalyzeResponse> {
  // Simulasikan latensi jaringan supaya skeleton loader terlihat wajar saat demo
  await new Promise((r) => setTimeout(r, 900));

  if (scenarioId && SCENARIO_MOCK_RESPONSES[scenarioId]) {
    return SCENARIO_MOCK_RESPONSES[scenarioId];
  }

  const readings: SensorReading[] = payload.readings.map((r, i) => ({
    t_min: i * 5,
    temperature_c: r.temperature_c,
    ambient_temp_c: r.ambient_temp_c,
    door_open: r.door_open,
  }));
  return heuristicMockAnalyze(readings);
}