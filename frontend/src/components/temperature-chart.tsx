"use client";

import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { ChartLineUp } from "@phosphor-icons/react/dist/ssr";
import { CardTitle } from "./card-title";
import { CargoProfile, Forecast, TelemetryReading } from "@/lib/types";

interface Props {
  readings: TelemetryReading[];
  forecast: Forecast;
  profile: CargoProfile;
}

export function TemperatureChart({ readings, forecast, profile }: Props) {
  const n = readings.length;
  const last = readings[n - 1].temp_c;
  const data: { t: number; actual?: number; forecast?: number }[] = readings.map((r, i) => ({
    t: i - (n - 1),
    actual: r.temp_c,
  }));
  data[n - 1].forecast = last;
  data.push({ t: 15, forecast: forecast.t15 }, { t: 30, forecast: forecast.t30 }, { t: 60, forecast: forecast.t60 });

  const values = [...readings.map((r) => r.temp_c), forecast.t15, forecast.t30, forecast.t60, profile.min, profile.critical];
  const lo = Math.floor(Math.min(...values) - 1);
  const hi = Math.ceil(Math.max(...values) + 1);

  const summary = `Suhu muatan sekarang ${last.toFixed(1)}°C. Prediksi ${forecast.t15.toFixed(1)}°C dalam 15 menit, ${forecast.t30.toFixed(1)}°C dalam 30 menit, dan ${forecast.t60.toFixed(1)}°C dalam 60 menit. Batas aman ${profile.min} sampai ${profile.max}°C.`;

  return (
    <section className="card flex flex-col gap-3 p-5">
      <CardTitle icon={ChartLineUp}>Suhu muatan</CardTitle>
      <div>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-muted">
          <li className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-accent" />Aktual</li>
          <li className="flex items-center gap-1.5"><span className="h-0 w-4 border-t-2 border-dashed border-accent" />Prediksi</li>
          <li className="flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-sm bg-ok-soft" />Rentang aman</li>
          <li className="flex items-center gap-1.5"><span className="h-0 w-4 border-t border-dashed border-crit" />Batas kritis</li>
        </ul>
      </div>
      <p className="sr-only">{summary}</p>
      <div className="h-[240px] w-full" aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="t" type="number" domain={[-(n - 1), 60]} ticks={[-60, -45, -30, -15, 0, 15, 30, 45, 60]}
              tickFormatter={(v: number) => (v === 0 ? "sekarang" : `${v > 0 ? "+" : ""}${v}m`)}
              tick={{ fontSize: 11, fill: "var(--text-muted)" }} stroke="var(--border)"
            />
            <YAxis
              domain={[lo, hi]} width={48} tickFormatter={(v: number) => `${v}°`}
              tick={{ fontSize: 11, fill: "var(--text-muted)" }} stroke="var(--border)"
            />
            <ReferenceArea y1={profile.min} y2={profile.max} fill="var(--ok)" fillOpacity={0.08} stroke="none" />
            <ReferenceLine
              y={profile.critical} stroke="var(--crit)" strokeWidth={1.5} strokeDasharray="6 4"
              label={{ value: `Batas kritis ${profile.critical}°C`, position: "insideTopRight", fontSize: 11, fill: "var(--crit)" }}
            />
            <ReferenceLine x={0} stroke="var(--border)" />
            <Tooltip
              contentStyle={{ borderRadius: 6, border: "1px solid var(--border)", background: "var(--surface)", fontSize: 12 }}
              labelFormatter={(v) => (Number(v) === 0 ? "Sekarang" : `${Number(v) > 0 ? "+" : ""}${v} menit`)}
              formatter={(v, name) => [`${Number(v).toFixed(1)}°C`, name === "actual" ? "Aktual" : "Prediksi"]}
            />
            <defs>
              <linearGradient id="actualFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.18} />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area dataKey="actual" stroke="var(--accent)" strokeWidth={2.5} fill="url(#actualFill)" dot={false} isAnimationActive={false} baseValue={lo} />
            <Line
              dataKey="forecast" stroke="var(--accent)" strokeWidth={2} strokeDasharray="6 4"
              dot={{ r: 3.5, fill: "var(--accent)", strokeWidth: 0 }} connectNulls isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
