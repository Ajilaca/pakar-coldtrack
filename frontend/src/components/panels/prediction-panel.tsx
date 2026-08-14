"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from "recharts";
import { KpiCard } from "@/components/kpi-card";
import { DonutStat } from "@/components/donut-stat";
import { Icon } from "@/components/icon";
import { ChartLoading, PanelError, PanelEmpty } from "@/components/panel-states";
import { getVehicleLabel } from "@/lib/dashboard-data";
import {
  PREDICTION_STATS,
  RISK_DISTRIBUTION,
  PREDICTION_TREND,
  TOP_RISK_FACTORS,
  AI_RECOMMENDATIONS,
  AI_INSIGHT,
} from "@/lib/fleet-data";
import { AnalyzeResponse, CargoThreshold, SensorReading } from "@/lib/types";

interface PredictionPanelProps {
  loading: boolean;
  error: string | null;
  result: AnalyzeResponse | null;
  readings: SensorReading[] | null;
  threshold: CargoThreshold | null;
  scenarioId: string | null;
}

const RISK_PIE = [
  { name: "Low", value: RISK_DISTRIBUTION.low.value, color: "hsl(var(--mint))" },
  { name: "Medium", value: RISK_DISTRIBUTION.medium.value, color: "hsl(var(--amber-warn))" },
  { name: "High", value: RISK_DISTRIBUTION.high.value, color: "hsl(var(--critical))" },
];

export function PredictionPanel({ loading, error, result, readings, threshold, scenarioId }: PredictionPanelProps) {
  const vehicleLabel = getVehicleLabel(scenarioId);
  const last = readings ? readings[readings.length - 1] : null;
  const forecastData =
    result && last
      ? [
          { t: "Now", temp: last.temperature_c },
          { t: "+15m", temp: result.forecast.t15 },
          { t: "+30m", temp: result.forecast.t30 },
          { t: "+60m", temp: result.forecast.t60 },
        ]
      : [];

  return (
    <div className="flex h-full flex-col gap-3">
      <div>
        <h2 className="font-display text-[19px] font-bold text-ink leading-tight">AI Prediction</h2>
        <p className="text-xs text-muted-foreground mt-0">Leverage AI to predict risks, delays, and temperature violations before they happen.</p>
      </div>

      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5 shrink-0">
        <KpiCard accent="blue" label="Total Predictions" value={`${PREDICTION_STATS.totalPredictions.value}`} note={`↑${PREDICTION_STATS.totalPredictions.delta}`} noteTone="mint" />
        <KpiCard accent="critical" label="High Risk Shipments" value={`${PREDICTION_STATS.highRiskShipments.value}`} note={`↑${PREDICTION_STATS.highRiskShipments.delta}`} noteTone="critical" />
        <KpiCard accent="amber" label="Pred. Temp. Violations" value={`${PREDICTION_STATS.predictedTempViolations.value}`} note={`↓${PREDICTION_STATS.predictedTempViolations.delta}`} noteTone="mint" />
        <KpiCard accent="coral" label="Predicted Delays" value={`${PREDICTION_STATS.predictedDelays.value}`} note={`↑${PREDICTION_STATS.predictedDelays.delta}`} noteTone="amber" />
        <KpiCard accent="mint" label="Prediction Accuracy" value={`${PREDICTION_STATS.predictionAccuracy.value}%`} note={`↑${PREDICTION_STATS.predictionAccuracy.delta}`} noteTone="mint" />
      </div>

      <div className="grid flex-1 grid-cols-1 gap-3 lg:grid-cols-2 min-h-0">
        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost flex flex-col min-h-0">
          <p className="mb-1 text-xs font-semibold text-ink shrink-0">{`Forecast — ${vehicleLabel}`}</p>
          <div className="flex-1 min-h-0">
            {loading && <ChartLoading />}
            {!loading && error && <PanelError message={error} />}
            {!loading && !error && result && threshold && forecastData.length > 0 && (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={forecastData} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
                  <XAxis dataKey="t" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} unit="°C" />
                  <Tooltip contentStyle={{ borderRadius: 12, borderColor: "hsl(var(--border))", fontSize: 12 }} />
                  <ReferenceLine y={threshold.max} stroke="hsl(var(--critical))" strokeDasharray="4 4" />
                  <ReferenceLine y={threshold.min} stroke="hsl(var(--critical))" strokeDasharray="4 4" />
                  <Line isAnimationActive={false} type="monotone" dataKey="temp" stroke="hsl(var(--brand))" strokeWidth={2.5} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            )}
            {!loading && !error && (!result || !threshold) && <PanelEmpty message="Select a scenario or CSV." />}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost flex flex-col min-h-0">
          <p className="mb-1 text-xs font-semibold text-ink shrink-0">Prediction Trend (Fleet-wide)</p>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={PREDICTION_TREND} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ borderRadius: 12, borderColor: "hsl(var(--border))", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 9 }} />
                <Line isAnimationActive={false} type="monotone" dataKey="highRisk" name="High Risk" stroke="hsl(var(--critical))" strokeWidth={2} dot={{ r: 2 }} />
                <Line isAnimationActive={false} type="monotone" dataKey="tempViolation" name="Temp. Violation" stroke="hsl(var(--amber-warn))" strokeWidth={2} dot={{ r: 2 }} />
                <Line isAnimationActive={false} type="monotone" dataKey="delay" name="Delay" stroke="hsl(var(--brand))" strokeWidth={2} dot={{ r: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[0.8fr_1fr_1.2fr] shrink-0" style={{ height: 150 }}>
        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost flex items-center gap-3">
          <DonutStat segments={RISK_PIE} size={72} centerValue={`${RISK_DISTRIBUTION.total}`} />
          <div className="text-[10px] space-y-0.5">
            {RISK_PIE.map((d) => (
              <div key={d.name} className="flex items-center gap-1 text-muted-foreground">
                <span className="size-1.5 rounded-full" style={{ backgroundColor: d.color }} />
                {d.name} <span className="font-medium text-ink">{d.value}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost overflow-y-auto">
          <p className="mb-1.5 text-[11px] font-semibold text-ink">Top Risk Factors</p>
          <div className="space-y-1.5">
            {TOP_RISK_FACTORS.slice(0, 4).map((f) => (
              <div key={f.label}>
                <div className="flex justify-between text-[10px] mb-0.5">
                  <span className="text-ink truncate">{f.label}</span>
                  <span className="font-medium text-muted-foreground shrink-0">{f.pct}%</span>
                </div>
                <div className="h-1 w-full overflow-hidden rounded-full bg-secondary">
                  <div className="h-full rounded-full bg-brand" style={{ width: `${f.pct}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-brand-soft p-3 overflow-y-auto">
          <div className="flex items-center gap-1.5 mb-1">
            <Icon size={13} tone="gray" />
            <p className="text-[11px] font-semibold text-ink">AI Insights & Recommendations</p>
          </div>
          <p className="text-[10px] leading-snug text-ink/80 mb-1.5">{AI_INSIGHT}</p>
          <ul className="space-y-0.5">
            {AI_RECOMMENDATIONS.slice(0, 2).map((r) => (
              <li key={r} className="flex items-start gap-1.5 text-[10px] text-ink">
                <span className="mt-0.5 shrink-0 text-mint">✓</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
