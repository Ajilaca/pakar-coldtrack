import { SensorReading } from "./types";

/**
 * Parser CSV minimal — cukup untuk kolom: t_min,temperature_c,ambient_temp_c,door_open
 * Tidak menangani quoted-comma; cukup untuk data sensor numerik sederhana.
 * Kalau butuh CSV yang lebih kompleks nanti, ganti dengan papaparse.
 */
export function parseReadingsCsv(text: string): SensorReading[] {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0);

  if (lines.length < 2) return [];

  const header = lines[0].split(",").map((h) => h.trim().toLowerCase());
  const idx = {
    t: header.indexOf("t_min"),
    temp: header.indexOf("temperature_c"),
    ambient: header.indexOf("ambient_temp_c"),
    door: header.indexOf("door_open"),
  };

  if (idx.t === -1 || idx.temp === -1) {
    throw new Error(
      "CSV harus punya kolom minimal: t_min,temperature_c (opsional: ambient_temp_c,door_open)"
    );
  }

  return lines.slice(1).map((line, i) => {
    const cols = line.split(",").map((c) => c.trim());
    const t_min = Number(cols[idx.t]);
    const temperature_c = Number(cols[idx.temp]);
    if (Number.isNaN(t_min) || Number.isNaN(temperature_c)) {
      throw new Error(`Baris ${i + 2} tidak valid: "${line}"`);
    }
    return {
      t_min,
      temperature_c,
      ambient_temp_c:
        idx.ambient !== -1 && cols[idx.ambient] !== "" ? Number(cols[idx.ambient]) : undefined,
      door_open: idx.door !== -1 ? cols[idx.door] === "true" || cols[idx.door] === "1" : undefined,
    };
  });
}

export function readingsToCsv(readings: SensorReading[]): string {
  const header = "t_min,temperature_c,ambient_temp_c,door_open";
  const rows = readings.map(
    (r) =>
      `${r.t_min},${r.temperature_c},${r.ambient_temp_c ?? ""},${r.door_open ?? ""}`
  );
  return [header, ...rows].join("\n");
}