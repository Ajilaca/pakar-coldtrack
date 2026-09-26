import { Door, Package, SunDim, Thermometer, WifiSlash } from "@phosphor-icons/react/dist/ssr";
import { Driver, ShipmentStatus } from "./types";

const DIAGNOSIS_TEXT: Record<string, string> = {
  normal_sehat: "Normal",
  pintu_terbuka: "Pintu terbuka",
  pintu_terbuka_lama: "Pintu terbuka terlalu lama",
  kejutan_ambien_ekstrem: "Kejut suhu luar ekstrem",
  masalah_sensor: "Sensor bermasalah",
  suhu_muatan_mendekati_batas: "Suhu muatan mendekati batas",
};

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

export function diagnosisText(label: string): string {
  return DIAGNOSIS_TEXT[label] ?? humanize(label);
}

export function driverText(feature: string): string {
  return DRIVER_TEXT[feature] ?? humanize(feature);
}

// Reefer is out of scope for the UI; the backend may still rank it.
export function visibleDrivers(drivers: Driver[]): Driver[] {
  return drivers.filter((d) => !d.feature.includes("reefer"));
}

export function isSensorFault(label: string): boolean {
  return label.includes("sensor");
}

export function truckImage(status: ShipmentStatus, label: string): string {
  if (status === "AMAN") return "/images/truck/normal.webp";
  const tone = status === "KRITIS" ? "red" : "yellow";
  if (label.startsWith("pintu_terbuka")) return `/images/truck/door-open-${tone}.webp`;
  if (label === "kejutan_ambien_ekstrem") return `/images/truck/ambient-shock-${tone}.webp`;
  if (isSensorFault(label)) return "/images/truck/sensor-fault-yellow.webp";
  return `/images/truck/near-limit-${tone}.webp`;
}

export const STATUS_META: Record<ShipmentStatus, { text: string; tone: "ok" | "warn" | "crit" }> = {
  AMAN: { text: "Aman", tone: "ok" },
  WASPADA: { text: "Waspada", tone: "warn" },
  KRITIS: { text: "Kritis", tone: "crit" },
};

export function diagnosisIcon(label: string) {
  if (label.startsWith("pintu")) return Door;
  if (label.includes("ambien")) return SunDim;
  if (label.includes("sensor")) return WifiSlash;
  if (label.includes("batas")) return Thermometer;
  return Package;
}
