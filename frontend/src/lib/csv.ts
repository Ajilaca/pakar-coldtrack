import { TelemetryReading } from "./types";

/**
 * Parser CSV minimal. Keluarannya langsung dalam BENTUK KAWAT BACKEND
 * (TelemetryReading) supaya bisa dikirim ke POST /api/v1/analyze tanpa
 * penerjemahan nama field lagi.
 *
 * Kolom wajib : ts, temp_c, ambient_c
 * Kolom opsional: humidity, door_open, reefer_on, lat, lon, speed_kmh,
 *                 harsh_events, solar_radiation
 *
 * Nilai default diisi untuk field yang diwajibkan backend tapi tidak ada di
 * CSV — lebih baik terisi wajar daripada permintaannya ditolak 422.
 */

/** Backend menolak payload di bawah 60 bacaan (main.py:111). */
export const MIN_READINGS = 60;

function bool(v: string | undefined): boolean {
  if (!v) return false;
  const s = v.trim().toLowerCase();
  return s === "true" || s === "1" || s === "yes" || s === "ya";
}

function num(v: string | undefined, fallback: number): number {
  if (v === undefined || v.trim() === "") return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

export function parseReadingsCsv(text: string): TelemetryReading[] {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0);

  if (lines.length < 2) return [];

  const header = lines[0].split(",").map((h) => h.trim().toLowerCase());
  const col = (name: string) => header.indexOf(name);

  const iTs = col("ts");
  const iTemp = col("temp_c");
  const iAmbient = col("ambient_c");

  if (iTemp === -1) {
    throw new Error("CSV harus punya kolom `temp_c`. Kolom lain yang dikenali: ts, ambient_c, humidity, door_open, reefer_on, lat, lon, speed_kmh, harsh_events.");
  }

  const iHum = col("humidity");
  const iDoor = col("door_open");
  const iReefer = col("reefer_on");
  const iLat = col("lat");
  const iLon = col("lon");
  const iSpeed = col("speed_kmh");
  const iHarsh = col("harsh_events");
  const iSolar = col("solar_radiation");

  const base = Date.now() - lines.length * 60000;

  return lines.slice(1).map((line, i) => {
    const c = line.split(",").map((x) => x.trim());

    const temp_c = Number(c[iTemp]);
    if (!Number.isFinite(temp_c)) {
      throw new Error(`Baris ${i + 2}: nilai temp_c tidak valid ("${c[iTemp] ?? ""}").`);
    }

    // Tanpa kolom ts, waktu dibuat berjarak 1 menit — model hanya butuh
    // urutan dan jarak antar-bacaan, bukan tanggal sebenarnya.
    let ts: string;
    const raw = iTs !== -1 ? c[iTs] : undefined;
    const parsed = raw ? Date.parse(raw) : NaN;
    if (Number.isFinite(parsed)) ts = new Date(parsed).toISOString();
    else ts = new Date(base + i * 60000).toISOString();

    return {
      ts,
      temp_c,
      humidity: num(c[iHum], 65),
      ambient_c: num(c[iAmbient], 30),
      door_open: iDoor !== -1 ? bool(c[iDoor]) : false,
      reefer_on: iReefer !== -1 ? bool(c[iReefer]) : true,
      lat: iLat !== -1 && c[iLat] !== "" ? num(c[iLat], 0) : null,
      lon: iLon !== -1 && c[iLon] !== "" ? num(c[iLon], 0) : null,
      speed_kmh: num(c[iSpeed], 45),
      harsh_events: Math.round(num(c[iHarsh], 0)),
      solar_radiation: num(c[iSolar], 0),
    };
  });
}
