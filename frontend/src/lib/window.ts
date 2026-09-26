import { ConditionInput, TelemetryReading } from "./types";

export const WINDOW_MINUTES = 60;

// Deterministic noise so the same input always yields the same window (and the same result).
function noise(i: number): number {
  const x = Math.sin(i * 12.9898) * 43758.5453;
  return (x - Math.floor(x) - 0.5) * 0.1;
}

function isoLocal(d: Date): string {
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? "+" : "-";
  const pad = (n: number) => String(Math.floor(Math.abs(n))).padStart(2, "0");
  const local = new Date(d.getTime() + off * 60000).toISOString().slice(0, 19);
  return `${local}${sign}${pad(off / 60)}:${pad(off % 60)}`;
}

/** Builds the 60 per-minute readings the backend requires from the user's current condition. */
export function buildWindow(c: ConditionInput, now: Date): TelemetryReading[] {
  const end = new Date(Math.floor(now.getTime() / 60000) * 60000);
  const readings: TelemetryReading[] = [];

  for (let i = 0; i < WINDOW_MINUTES; i++) {
    const minutesAgo = WINDOW_MINUTES - 1 - i;
    const frac = i / (WINDOW_MINUTES - 1);
    const temp = c.temp60Ago + (c.tempNow - c.temp60Ago) * frac + (i === WINDOW_MINUTES - 1 ? 0 : noise(i));
    readings.push({
      ts: isoLocal(new Date(end.getTime() - minutesAgo * 60000)),
      temp_c: Math.round(temp * 100) / 100,
      humidity: c.humidity,
      ambient_c: c.ambient,
      door_open: c.doorOpen && minutesAgo < c.doorMinutes,
      reefer_on: true,
      speed_kmh: !c.moving && minutesAgo < c.stoppedMinutes ? 0 : 40,
      harsh_events: 0,
    });
  }
  return readings;
}
