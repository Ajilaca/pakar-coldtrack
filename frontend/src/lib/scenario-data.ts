import { AnalyzeResponse, ScenarioPreset, SensorReading } from "./types";

// =============================================================================
// PLACEHOLDER DATA — ganti dengan CSV asli dari R1 (simulator) begitu tersedia.
// Deterministik (bukan Math.random) supaya build/demo selalu identik.
// Interval bacaan: 5 menit. cargo_profile "vaksin_2_8C" → ambang 2-8°C.
// =============================================================================

const DT = 5; // menit antar-bacaan
const N = 31; // 0..150 menit

function wobble(i: number, amp: number) {
  // pengganti noise acak yang deterministik
  return amp * Math.sin(i * 1.3) * 0.5 + amp * 0.5 * Math.sin(i * 0.4);
}

function series(
  fn: (t: number, i: number) => number,
  ambientFn?: (t: number, i: number) => number,
  doorFn?: (t: number, i: number) => boolean
): SensorReading[] {
  return Array.from({ length: N }, (_, i) => {
    const t = i * DT;
    return {
      t_min: t,
      temperature_c: Math.round(fn(t, i) * 10) / 10,
      ambient_temp_c: ambientFn ? Math.round(ambientFn(t, i) * 10) / 10 : undefined,
      door_open: doorFn ? doorFn(t, i) : undefined,
    };
  });
}

// 1. Sehat — perjalanan normal, suhu stabil di dalam ambang
const READINGS_SEHAT = series((t, i) => 5 + wobble(i, 0.4), (t) => 22 + wobble(t, 1));

// 2. Pintu terbuka terlalu lama — lonjakan lalu pulih
const READINGS_PINTU = series(
  (t, i) => {
    const doorStart = 40,
      doorEnd = 60;
    if (t < doorStart) return 5 + wobble(i, 0.4);
    if (t <= doorEnd) return 5 + ((t - doorStart) / (doorEnd - doorStart)) * 4.5; // naik ke ~9.5
    const recover = Math.max(0, 1 - (t - doorEnd) / 40);
    return 5 + 4.5 * recover + wobble(i, 0.3);
  },
  (t) => 24 + wobble(t, 1),
  (t) => t >= 40 && t <= 60
);

// 3. Kompresor melemah — degradasi bertahap, halus, tidak terlihat manusia (paling dramatis untuk TTB)
const READINGS_KOMPRESOR = series(
  (t, i) => 5 + (t / 150) * 2.6 + wobble(i, 0.25),
  (t) => 23 + wobble(t, 1)
);

// 4. Sensor macet (stuck-at) — bacaan membeku di nilai tertentu setelah t=90
const READINGS_SENSOR_MACET = series((t, i) => {
  if (t <= 90) return 5.2 + wobble(i, 0.35);
  return 5.2; // frozen — tidak ada variasi sama sekali, ciri khas stuck-at
}, (t) => 22 + wobble(t, 1));

// 5. Kejut suhu ambien saat macet — ambient melonjak (macet siang hari), suhu kargo ikut naik
const READINGS_KEJUT_AMBIEN = series(
  (t, i) => 5 + Math.max(0, (t - 50) / 100) * 3.2 + wobble(i, 0.3),
  (t) => (t < 50 ? 24 + wobble(t, 1) : 24 + Math.min(14, (t - 50) * 0.35))
);

export const SCENARIOS: ScenarioPreset[] = [
  {
    id: "sehat",
    label: "Sehat",
    description: "Perjalanan normal, suhu stabil di dalam ambang.",
    cargoProfile: "vaksin_2_8C",
    threshold: { min: 2, max: 8, label: "Vaksin 2–8°C" },
    csvPath: "/scenarios/sehat.csv",
  },
  {
    id: "pintu_terbuka",
    label: "Pintu terbuka",
    description: "Pintu kargo terbuka terlalu lama saat bongkar-muat.",
    cargoProfile: "vaksin_2_8C",
    threshold: { min: 2, max: 8, label: "Vaksin 2–8°C" },
    csvPath: "/scenarios/pintu_terbuka.csv",
  },
  {
    id: "kompresor_melemah",
    label: "Kompresor melemah",
    description: "Degradasi bertahap dan halus — kasus utama untuk Time-to-Breach.",
    cargoProfile: "vaksin_2_8C",
    threshold: { min: 2, max: 8, label: "Vaksin 2–8°C" },
    csvPath: "/scenarios/kompresor_melemah.csv",
  },
  {
    id: "sensor_macet",
    label: "Sensor macet",
    description: "Bacaan sensor membeku (stuck-at) di satu nilai.",
    cargoProfile: "vaksin_2_8C",
    threshold: { min: 2, max: 8, label: "Vaksin 2–8°C" },
    csvPath: "/scenarios/sensor_macet.csv",
  },
  {
    id: "kejut_suhu_ambien",
    label: "Kejut suhu ambien saat macet",
    description: "Suhu ambien melonjak karena macet siang hari, membebani unit pendingin.",
    cargoProfile: "vaksin_2_8C",
    threshold: { min: 2, max: 8, label: "Vaksin 2–8°C" },
    csvPath: "/scenarios/kejut_suhu_ambien.csv",
  },
];

export const SCENARIO_READINGS: Record<string, SensorReading[]> = {
  sehat: READINGS_SEHAT,
  pintu_terbuka: READINGS_PINTU,
  kompresor_melemah: READINGS_KOMPRESOR,
  sensor_macet: READINGS_SENSOR_MACET,
  kejut_suhu_ambien: READINGS_KEJUT_AMBIEN,
};

// Response tiruan per skenario — dipakai lib/mock.ts sebagai pengganti endpoint R3
// sebelum endpoint asli siap (lihat kontrak API di role-context R4).
export const SCENARIO_MOCK_RESPONSES: Record<string, AnalyzeResponse> = {
  sehat: {
    status: "AMAN",
    time_to_breach_min: null,
    failure_mode: { label: "Tidak ada anomali terdeteksi", confidence: 0.97 },
    forecast: { t15: 5.1, t30: 5.0, t60: 5.2 },
    drivers: [
      { feature: "Variansi suhu 30 menit terakhir", value: "±0.4°C", contribution: 0.42 },
      { feature: "Suhu ambien", value: "22°C (stabil)", contribution: 0.31 },
      { feature: "Status pintu", value: "tertutup", contribution: 0.27 },
    ],
    actions: [
      { priority: 1, text: "Tidak ada tindakan diperlukan — lanjutkan pemantauan rutin.", eta_min: 0 },
      { priority: 2, text: "Jadwalkan pengecekan berikutnya sesuai SOP standar.", eta_min: 60 },
      { priority: 3, text: "Simpan log perjalanan sebagai baseline referensi.", eta_min: 0 },
    ],
  },
  pintu_terbuka: {
    status: "WASPADA",
    time_to_breach_min: 34.2,
    failure_mode: { label: "Pintu terbuka terlalu lama", confidence: 0.88 },
    forecast: { t15: 7.6, t30: 6.4, t60: 5.3 },
    drivers: [
      { feature: "Durasi pintu terbuka", value: "20 menit", contribution: 0.51 },
      { feature: "Laju kenaikan suhu", value: "+0.22°C/menit", contribution: 0.33 },
      { feature: "Suhu ambien saat pintu terbuka", value: "24°C", contribution: 0.16 },
    ],
    actions: [
      { priority: 1, text: "Tutup pintu kargo segera dan konfirmasi rapat pada seal.", eta_min: 2 },
      { priority: 2, text: "Turunkan set-point sementara 1°C untuk kompensasi pemulihan.", eta_min: 5 },
      { priority: 3, text: "Catat insiden pada log bongkar-muat untuk audit.", eta_min: 15 },
    ],
  },
  kompresor_melemah: {
    status: "KRITIS",
    time_to_breach_min: 23.4,
    failure_mode: { label: "Kompresor melemah (degradasi bertahap)", confidence: 0.91 },
    forecast: { t15: 6.9, t30: 8.4, t60: 11.2 },
    drivers: [
      { feature: "Laju kenaikan suhu 60 menit", value: "+0.017°C/menit (konsisten)", contribution: 0.44 },
      { feature: "Siklus duty kompresor", value: "memanjang tidak wajar", contribution: 0.35 },
      { feature: "Selisih suhu kargo–ambien", value: "menyempit bertahap", contribution: 0.21 },
    ],
    actions: [
      { priority: 1, text: "Alihkan muatan ke unit reefer cadangan pada pemberhentian terdekat.", eta_min: 15 },
      { priority: 2, text: "Hubungi teknisi untuk diagnostik kompresor jarak jauh.", eta_min: 10 },
      { priority: 3, text: "Siapkan dokumen klaim asuransi bila breach terjadi.", eta_min: 20 },
    ],
  },
  sensor_macet: {
    status: "WASPADA",
    time_to_breach_min: null,
    failure_mode: { label: "Sensor macet (stuck-at)", confidence: 0.94 },
    forecast: { t15: 5.2, t30: 5.2, t60: 5.2 },
    drivers: [
      { feature: "Variansi bacaan 30 menit terakhir", value: "0.0°C (tidak wajar)", contribution: 0.62 },
      { feature: "Korelasi dengan sensor ambien", value: "hilang", contribution: 0.28 },
      { feature: "Riwayat kalibrasi sensor", value: "> 6 bulan", contribution: 0.10 },
    ],
    actions: [
      { priority: 1, text: "Anggap suhu aktual tidak terpantau — kirim tim ke titik pemberhentian terdekat.", eta_min: 20 },
      { priority: 2, text: "Aktifkan sensor cadangan bila tersedia pada unit.", eta_min: 5 },
      { priority: 3, text: "Jadwalkan kalibrasi ulang sensor setelah perjalanan.", eta_min: 0 },
    ],
  },
  kejut_suhu_ambien: {
    status: "WASPADA",
    time_to_breach_min: 41.7,
    failure_mode: { label: "Beban panas ambien berlebih saat macet", confidence: 0.85 },
    forecast: { t15: 6.8, t30: 7.5, t60: 8.9 },
    drivers: [
      { feature: "Suhu ambien", value: "38°C (naik dari 24°C)", contribution: 0.47 },
      { feature: "Durasi macet", value: "> 40 menit", contribution: 0.34 },
      { feature: "Laju kenaikan suhu kargo", value: "+0.032°C/menit", contribution: 0.19 },
    ],
    actions: [
      { priority: 1, text: "Turunkan set-point unit pendingin untuk mengimbangi beban ambien.", eta_min: 5 },
      { priority: 2, text: "Cari rute alternatif untuk keluar dari titik macet bila memungkinkan.", eta_min: 10 },
      { priority: 3, text: "Pantau ketat 30 menit ke depan — status dapat memburuk ke KRITIS.", eta_min: 0 },
    ],
  },
};