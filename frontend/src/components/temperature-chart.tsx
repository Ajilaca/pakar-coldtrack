"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  Legend,
} from "recharts";
import { CargoThreshold, ChartPoint, Forecast } from "@/lib/types";

interface TemperatureChartProps {
  readings: ChartPoint[];
  forecast: Forecast;
  threshold: CargoThreshold;
  showAmbient?: boolean;
  compact?: boolean;
}

export function TemperatureChart({ readings, forecast, threshold, showAmbient, compact }: TemperatureChartProps) {
  const last = readings[readings.length - 1];
  const lastT = last?.t_min ?? 0;
  const lastTemp = last?.temp_c ?? 0;

  const data = [
    ...readings.map((r) => ({
      t: r.t_min,
      actual: r.temp_c,
      ambient: r.ambient_c,
      forecast: undefined as number | undefined,
    })),
    { t: lastT, actual: lastTemp, ambient: undefined, forecast: lastTemp }, // titik jembatan actual -> forecast
    { t: lastT + 15, actual: undefined, ambient: undefined, forecast: forecast.t15 },
    { t: lastT + 30, actual: undefined, ambient: undefined, forecast: forecast.t30 },
    { t: lastT + 60, actual: undefined, ambient: undefined, forecast: forecast.t60 },
  ];

  return (
    <div className={compact ? "h-full w-full" : "space-y-2"}>
      {!compact && (
        <p className="t-meta">
          Suhu kargo — aktual (garis penuh) vs prediksi (garis putus-putus)
        </p>
      )}
      <div className={compact ? "h-full w-full" : "h-64 w-full"}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="t"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(v) => `${v}m`}
              tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            />
            <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} unit="°C" width={44} />
            <Tooltip
              contentStyle={{ borderRadius: 12, border: "1px solid hsl(var(--border))", background: "hsl(var(--card))", color: "hsl(var(--ink))", fontSize: 11, boxShadow: "0 12px 28px -12px hsl(var(--ocean-deep) / 0.25)" }}
              formatter={(value: unknown, name: unknown) => [
                `${Number(value)}°C`,
                name === "actual" ? "Aktual" : name === "ambient" ? "Ambien" : "Prediksi",
              ]}
              labelFormatter={(v) => `t = ${v} menit`}
            />
            {!compact && (
              <Legend
                formatter={(value) => (value === "actual" ? "Aktual" : value === "ambient" ? "Ambien" : "Prediksi")}
                wrapperStyle={{ fontSize: 10 }}
              />
            )}
            {/* pita ambang aman */}
            <ReferenceArea
              y1={threshold.min}
              y2={threshold.max}
              fill="hsl(var(--mint))"
              fillOpacity={0.14}
              stroke="hsl(var(--mint))"
              strokeOpacity={0.35}
              label={
                compact
                  ? undefined
                  : {
                      value: `Ambang aman (${threshold.label})`,
                      position: "insideTopLeft",
                      fontSize: 10,
                      fill: "hsl(var(--mint))",
                    }
              }
            />
            <Line
              type="monotone"
              dataKey="actual"
              stroke="hsl(var(--brand))"
              strokeWidth={2.5}
              dot={false}
              connectNulls={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="forecast"
              stroke="hsl(var(--ink-2))"
              strokeWidth={2.5}
              strokeDasharray="5 5"
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            {showAmbient && (
              <Line
                type="monotone"
                dataKey="ambient"
                stroke="hsl(var(--ink-2))"
                strokeOpacity={0.55}
                strokeWidth={1.75}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}