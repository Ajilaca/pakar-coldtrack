import { Driver } from "./types";

// Nama tampilan mengikuti Figma (frame Ringkasan/Kondisi/Simulasi).
const DIAGNOSIS_TEXT: Record<string, string> = {
  normal_sehat: "Normal / sehat",
  pintu_terbuka: "Pintu terbuka",
  pintu_terbuka_lama: "Pintu terbuka lama",
  kejutan_ambien_ekstrem: "Kejut ambien",
  masalah_sensor: "Masalah sensor",
  suhu_muatan_mendekati_batas: "Suhu muatan mendekati batas",
  // model v3 (7 kelas)
  reefer_mati_total: "Reefer mati total",
  prapendinginan_buruk: "Prapendinginan buruk",
  degradasi_bertahap: "Degradasi pendinginan",
};

/** Urutan 7 kelas v3 untuk grafik "Truk per diagnosis". */
export const KELAS_V3 = [
  "normal_sehat", "pintu_terbuka_lama", "degradasi_bertahap", "masalah_sensor", "kejutan_ambien_ekstrem",
  "reefer_mati_total", "prapendinginan_buruk",
];

const DRIVER_TEXT: Record<string, string> = {
  laju_kenaikan_suhu: "Laju kenaikan suhu",
  delta_suhu_ambien: "Kenaikan suhu luar",
  beban_panas_berhenti: "Panas saat berhenti",
  status_pintu: "Status pintu",
  variansi_suhu: "Variasi bacaan suhu",
};

function humanize(s: string): string {
  const t = s.replace(/_/g, " ");
  return t.charAt(0).toUpperCase() + t.slice(1);
}

// Never blank, never throws: unknown labels become readable text, missing ones a neutral message.
export function diagnosisText(label: string | null | undefined): string {
  if (!label || !label.trim()) return "Diagnosis tidak tersedia";
  return DIAGNOSIS_TEXT[label] ?? humanize(label);
}

export function driverText(feature: string): string {
  return DRIVER_TEXT[feature] ?? humanize(feature);
}

// Reefer is out of scope for the UI; the backend may still rank it.
export function visibleDrivers(drivers: Driver[]): Driver[] {
  return drivers.filter((d) => !d.feature.includes("reefer"));
}
