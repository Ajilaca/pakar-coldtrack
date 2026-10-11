import {
  CheckCircle, CircleDashed, HourglassMedium, MinusCircle, Warning, WarningCircle, XCircle,
} from "@phosphor-icons/react/dist/ssr";
import { FleetStatus } from "./fleet-types";

type Tone = {
  word: string;          // teks pill
  short: string;         // label filter/legenda
  pill: string;          // kelas pill (latar + teks)
  dot: string;           // warna titik/marker (CSS var)
  text: string;
  banner: string;        // latar banner status
  Icon: typeof CheckCircle;
};

const GRAY = "var(--offline)";

export const FLEET_TONE: Record<FleetStatus, Tone> = {
  KRITIS: { word: "KRITIS", short: "Kritis", pill: "bg-crit-soft text-crit", dot: "var(--crit)", text: "text-crit", banner: "bg-crit", Icon: XCircle },
  WASPADA: { word: "WASPADA", short: "Waspada", pill: "bg-warn-soft text-warn", dot: "var(--warn)", text: "text-warn", banner: "bg-warn", Icon: Warning },
  AMAN: { word: "AMAN", short: "Aman", pill: "bg-ok-soft text-ok", dot: "var(--ok)", text: "text-ok", banner: "bg-ok", Icon: CheckCircle },
  DATA_TIDAK_LENGKAP: {
    word: "DATA TIDAK LENGKAP", short: "Data tidak lengkap", pill: "bg-offline-soft text-offline", dot: GRAY,
    text: "text-offline", banner: "bg-offline", Icon: WarningCircle,
  },
  MENUNGGU_DATA: {
    word: "MENUNGGU DATA", short: "Menunggu data", pill: "bg-offline-soft text-offline", dot: GRAY, text: "text-offline",
    banner: "bg-offline", Icon: HourglassMedium,
  },
  TIDAK_ADA_DATA: {
    word: "TIDAK ADA DATA", short: "Offline", pill: "bg-offline-soft text-offline", dot: GRAY, text: "text-offline",
    banner: "bg-offline", Icon: MinusCircle,
  },
  TANPA_TRIP: {
    word: "TANPA TRIP", short: "Tanpa trip", pill: "bg-offline-soft text-offline", dot: GRAY, text: "text-offline",
    banner: "bg-offline", Icon: CircleDashed,
  },
};

export const URUTAN: FleetStatus[] = [
  "KRITIS", "WASPADA", "TIDAK_ADA_DATA", "DATA_TIDAK_LENGKAP", "MENUNGGU_DATA", "AMAN", "TANPA_TRIP",
];

export function tone(s: string | null | undefined): Tone {
  return FLEET_TONE[(s as FleetStatus) ?? "TANPA_TRIP"] ?? FLEET_TONE.TANPA_TRIP;
}

/** Nama muatan singkat untuk tabel ("Daging beku", "Vaksin 2–8 °C"). */
const MUATAN: Record<string, string> = {
  vaksin_2_8C: "Vaksin 2–8 °C",
  "daging_beku_-18C": "Daging beku",
  buah_segar_2_4C: "Buah segar",
  ikan_segar_0_5C: "Ikan segar",
  produk_susu_2_4C: "Produk susu",
};

export function muatan(profil: string | null | undefined): string {
  if (!profil) return "—";
  return MUATAN[profil] ?? profil.replace(/_/g, " ");
}
