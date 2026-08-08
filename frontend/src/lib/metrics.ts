import { CargoThreshold, SensorReading } from "./types";

export interface ComplianceBreakdown {
  total: number;
  compliantCount: number;
  minorCount: number;
  majorCount: number;
  compliantPct: number;
  minorPct: number;
  majorPct: number;
}

/**
 * Minor vs major is a simple, stated display heuristic (outside the safe
 * band by more than 1.5 degrees = major) — NOT the AI's own classification.
 * The authoritative status/diagnosis always comes from `result.status` and
 * `result.failure_mode`; this is only for the analytics breakdown chart.
 */
const MAJOR_MARGIN_C = 1.5;

export function computeCompliance(
  readings: SensorReading[] | null,
  threshold: CargoThreshold | null
): ComplianceBreakdown {
  if (!readings || readings.length === 0 || !threshold) {
    return { total: 0, compliantCount: 0, minorCount: 0, majorCount: 0, compliantPct: 0, minorPct: 0, majorPct: 0 };
  }
  let compliant = 0, minor = 0, major = 0;
  for (const r of readings) {
    const t = r.temperature_c;
    if (t >= threshold.min && t <= threshold.max) compliant++;
    else {
      const over = t > threshold.max ? t - threshold.max : threshold.min - t;
      if (over > MAJOR_MARGIN_C) major++;
      else minor++;
    }
  }
  const total = readings.length;
  return {
    total,
    compliantCount: compliant,
    minorCount: minor,
    majorCount: major,
    compliantPct: Math.round((compliant / total) * 1000) / 10,
    minorPct: Math.round((minor / total) * 1000) / 10,
    majorPct: Math.round((major / total) * 1000) / 10,
  };
}

export interface TempStats {
  min: number;
  max: number;
  avg: number;
  latest: number;
}

export function computeTempStats(readings: SensorReading[] | null): TempStats | null {
  if (!readings || readings.length === 0) return null;
  const temps = readings.map((r) => r.temperature_c);
  const min = Math.min(...temps);
  const max = Math.max(...temps);
  const avg = Math.round((temps.reduce((a, b) => a + b, 0) / temps.length) * 10) / 10;
  return { min, max, avg, latest: temps[temps.length - 1] };
}

export interface DistributionBucket {
  label: string;
  count: number;
  kind: "cold" | "safe" | "hot";
}

/** Buckets built relative to the active threshold, so this works for any cargo profile. */
export function computeDistribution(
  readings: SensorReading[] | null,
  threshold: CargoThreshold | null
): DistributionBucket[] {
  if (!readings || readings.length === 0 || !threshold) return [];
  const span = Math.max(threshold.max - threshold.min, 1);
  const step = span / 2;
  const edges = [
    threshold.min - 2 * step,
    threshold.min - step,
    threshold.min,
    threshold.max,
    threshold.max + step,
    threshold.max + 2 * step,
  ];
  const labels = [
    `< ${edges[1].toFixed(1)}\u00b0`,
    `${edges[1].toFixed(1)}-${edges[2].toFixed(1)}\u00b0`,
    `${edges[2].toFixed(1)}-${edges[3].toFixed(1)}\u00b0 (aman)`,
    `${edges[3].toFixed(1)}-${edges[4].toFixed(1)}\u00b0`,
    `> ${edges[4].toFixed(1)}\u00b0`,
  ];
  const kinds: DistributionBucket["kind"][] = ["cold", "cold", "safe", "hot", "hot"];
  const counts = [0, 0, 0, 0, 0];
  for (const r of readings) {
    const t = r.temperature_c;
    if (t < edges[1]) counts[0]++;
    else if (t < edges[2]) counts[1]++;
    else if (t <= edges[3]) counts[2]++;
    else if (t <= edges[4]) counts[3]++;
    else counts[4]++;
  }
  return labels.map((label, i) => ({ label, count: counts[i], kind: kinds[i] }));
}

export function countDoorEvents(readings: SensorReading[] | null): number {
  if (!readings || readings.length === 0) return 0;
  let events = 0;
  let prev = false;
  for (const r of readings) {
    const open = !!r.door_open;
    if (open && !prev) events++;
    prev = open;
  }
  return events;
}

export function formatDuration(min: number | null): string {
  if (min === null) return "\u2014";
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  if (h === 0) return `${m} menit`;
  return m === 0 ? `${h} jam` : `${h} jam ${m} menit`;
}
