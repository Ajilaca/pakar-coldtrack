"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { KpiCard } from "@/components/kpi-card";
import { DonutStat } from "@/components/donut-stat";
import { TemperatureChart } from "@/components/temperature-chart";
import { ChartLoading, PanelError, PanelEmpty } from "@/components/panel-states";
import { getVehicleLabel } from "@/lib/dashboard-data";
import { TEMP_ANALYTICS_STATS, TEMP_DISTRIBUTION, TEMP_VIOLATIONS } from "@/lib/fleet-data";
import { AnalyzeResponse, CargoThreshold, SensorReading } from "@/lib/types";

interface AnalyticsPanelProps {
  loading: boolean;
  error: string | null;
  result: AnalyzeResponse | null;
  readings: SensorReading[] | null;
  threshold: CargoThreshold | null;
  scenarioId: string | null;
}

const VIOLATIONS_PIE = [
  { name: "Minor", value: TEMP_VIOLATIONS.minor.value, color: "hsl(var(--amber-warn))" },
  { name: "Major", value: TEMP_VIOLATIONS.major.value, color: "hsl(var(--critical))" },
  { name: "Beyond Limit", value: TEMP_VIOLATIONS.beyondLimit.value, color: "hsl(var(--brand))" },
];

export function AnalyticsPanel({ loading, error, result, readings, threshold, scenarioId }: AnalyticsPanelProps) {
  const { compliant, minor, major } = TEMP_ANALYTICS_STATS.compliance;
  const vehicleLabel = getVehicleLabel(scenarioId);

  return (
    <div className="flex h-full flex-col gap-3">
      <div>
        <h2 className="font-display text-[19px] font-bold text-ink leading-tight">Temperature Analytics</h2>
        <p className="text-xs text-muted-foreground mt-0">Analyze temperature performance and compliance.</p>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[0.9fr_2.4fr] shrink-0">
        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost flex items-center gap-3">
          <DonutStat segments={[{ value: compliant, color: "hsl(var(--mint))" }, { value: minor, color: "hsl(var(--amber-warn))" }, { value: major, color: "hsl(var(--critical))" }]} size={72} centerValue={`${compliant}%`} />
          <div>
            <p className="text-xs font-semibold text-ink">Compliance</p>
            <p className="text-[10px] text-muted-foreground">{compliant}% compliant, {minor}% minor, {major}% major</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          <KpiCard accent="blue" label="Total Shipments" value={`${TEMP_ANALYTICS_STATS.totalShipments}`} note="↑12%" noteTone="mint" />
          <KpiCard accent="coral" label="Monitored Vehicles" value={`${TEMP_ANALYTICS_STATS.monitoredVehicles}`} note="↑8%" noteTone="mint" />
          <KpiCard accent="blue" label="Avg. Temp." value={`${TEMP_ANALYTICS_STATS.avgTemp}°C`} note="In range" noteTone="mint" />
          <KpiCard accent="amber" label="Temp. Alerts" value={`${TEMP_ANALYTICS_STATS.tempAlerts}`} note="↓14%" noteTone="mint" />
        </div>
      </div>

      <div className="grid flex-1 grid-cols-1 gap-3 lg:grid-cols-2 min-h-0">
        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost flex flex-col min-h-0">
          <p className="mb-1 text-xs font-semibold text-ink shrink-0">{`Temperature — ${vehicleLabel}`}</p>
          <div className="flex-1 min-h-0">
            {loading && <ChartLoading />}
            {!loading && error && <PanelError message={error} />}
            {!loading && !error && result && readings && threshold && (
              <TemperatureChart readings={readings} forecast={result.forecast} threshold={threshold} compact />
            )}
            {!loading && !error && (!result || !readings || !threshold) && <PanelEmpty message="Select a scenario or CSV." />}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost flex flex-col min-h-0">
          <p className="mb-1 text-xs font-semibold text-ink shrink-0">Temperature Distribution (All Vehicles)</p>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={TEMP_DISTRIBUTION} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 8 }} interval={0} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ borderRadius: 12, borderColor: "hsl(var(--border))", fontSize: 12 }} />
                <Bar isAnimationActive={false} dataKey="compliant" name="Compliant" stackId="a" fill="hsl(var(--mint))" />
                <Bar isAnimationActive={false} dataKey="minor" name="Minor" stackId="a" fill="hsl(var(--amber-warn))" />
                <Bar isAnimationActive={false} dataKey="major" name="Major" stackId="a" fill="hsl(var(--critical))" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card p-3 shadow-frost shrink-0 flex items-center gap-4" style={{ height: 96 }}>
        <DonutStat segments={VIOLATIONS_PIE} size={72} centerValue={`${TEMP_VIOLATIONS.total}`} />
        <div>
          <p className="text-xs font-semibold text-ink mb-1">Temperature Violations</p>
          <div className="flex gap-3 text-[11px]">
            {VIOLATIONS_PIE.map((d) => (
              <span key={d.name} className="flex items-center gap-1 text-muted-foreground">
                <span className="size-1.5 rounded-full" style={{ backgroundColor: d.color }} />
                {d.name} <span className="font-medium text-ink">{d.value}</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
