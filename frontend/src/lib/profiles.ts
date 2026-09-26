import { CargoProfile } from "./types";

// Copied from backend/config.yaml `cargo_profiles`; the API does not return them.
export const CARGO_PROFILES: CargoProfile[] = [
  { id: "vaksin_2_8C", name: "Vaksin & produk biologis (2–8°C)", min: 2, max: 8, critical: 10 },
  { id: "daging_beku_-18C", name: "Daging & makanan beku (−25…−18°C)", min: -25, max: -18, critical: -12 },
  { id: "buah_segar_2_4C", name: "Buah & sayur segar (2–4°C)", min: 2, max: 4, critical: 6 },
  { id: "ikan_segar_0_5C", name: "Ikan segar (0–5°C)", min: 0, max: 5, critical: 8 },
  { id: "produk_susu_2_4C", name: "Produk susu (2–4°C)", min: 2, max: 4, critical: 6 },
];

export function profileById(id: string): CargoProfile {
  return CARGO_PROFILES.find((p) => p.id === id) ?? CARGO_PROFILES[0];
}
