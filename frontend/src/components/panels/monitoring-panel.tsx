"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { KpiCard } from "@/components/kpi-card";
import { DonutStat } from "@/components/donut-stat";
import { TemperatureChart } from "@/components/temperature-chart";
import { ChartLoading, PanelError, PanelEmpty } from "@/components/panel-states";
import { getVehicleLabel } from "@/lib/dashboard-data";
import { MONITORING_STATS } from "@/lib/fleet-data";
import { AnalyzeResponse, CargoThreshold, SensorReading } from "@/lib/types";

interface MonitoringPanelProps {
  loading: boolean;
  error: string | null;
  result: AnalyzeResponse | null;
  readings: SensorReading[] | null;
  threshold: CargoThreshold | null;
  scenarioId: string | null;
}

const HOURS = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"];
const TEMP_OVERVIEW = HOURS.map((h, i) => ({
  hour: h,
  avg: 2.4 + Math.sin(i * 1.1) * 0.6,
  min: -1.2 + Math.sin(i * 0.9) * 0.5,
  max: 5.6 + Math.sin(i * 1.3) * 0.7,
  setPoint: 2.0,
}));

const DISTRIBUTION = [
  { name: "Within Range", value: MONITORING_STATS.withinRange.value, color: "hsl(var(--mint))" },
  { name: "Warning", value: MONITORING_STATS.deviations.value, color: "hsl(var(--amber-warn))" },
  { name: "Critical", value: MONITORING_STATS.criticalAlerts.value, color: "hsl(var(--critical))" },
];

const SENSOR_HEALTH = [
  { name: "Healthy", value: MONITORING_STATS.sensorHealthy, color: "hsl(var(--mint))" },
  { name: "Warning/Offline", value: 100 - MONITORING_STATS.sensorHealthy, color: "hsl(var(--amber-warn))" },
];

export function MonitoringPanel({ loading, error, result, readings, threshold, scenarioId }: MonitoringPanelProps) {
  const vehicleLabel = getVehicleLabel(scenarioId);

  return (
    <div className="flex h-full flex-col gap-3">
      <div>
        <h2 className="font-display text-[19px] font-bold text-ink leading-tight">Real-time Monitoring</h2>
        <p className="text-xs text-muted-foreground mt-0">Monitor temperature and status of shipments and vehicles in real-time.</p>
      </div>

      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
        <KpiCard accent="blue" label="Monitored Vehicles" value={`${MONITORING_STATS.monitoredVehicles}`} note="Live" />
        <KpiCard accent="blue" label="Active Shipments" value={`${MONITORING_STATS.activeShipments}`} note="In progress" />
        <KpiCard accent="mint" label="Within Temp. Range" value={`${MONITORING_STATS.withinRange.value} (${MONITORING_STATS.withinRange.pct}%)`} noteTone="mint" note="Good" />
        <KpiCard accent="amber" label="Temp. Deviations" value={`${MONITORING_STATS.deviations.value} (${MONITORING_STATS.deviations.pct}%)`} noteTone="amber" note="Warning" />
        <KpiCard accent="critical" label="Critical Alerts" value={`${MONITORING_STATS.criticalAlerts.value} (${MONITORING_STATS.criticalAlerts.pct}%)`} noteTone="critical" note="Critical" />
      </div>

      <div className="grid flex-1 grid-cols-1 gap-3 lg:grid-cols-2 min-h-0">
        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost flex flex-col min-h-0">
          <p className="mb-1 text-xs font-semibold text-ink shrink-0">Temperature Overview (All Vehicles)</p>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={TEMP_OVERVIEW} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
                <XAxis dataKey="hour" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} unit="°C" />
                <Tooltip contentStyle={{ borderRadius: 12, borderColor: "hsl(var(--border))", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                <Line isAnimationActive={false} type="monotone" dataKey="avg" name="Average" stroke="hsl(var(--brand))" strokeWidth={2} dot={false} />
                <Line isAnimationActive={false} type="monotone" dataKey="min" name="Min" stroke="hsl(var(--mint))" strokeWidth={2} dot={false} />
                <Line isAnimationActive={false} type="monotone" dataKey="max" name="Max" stroke="hsl(var(--critical))" strokeWidth={2} dot={false} />
                <Line isAnimationActive={false} type="monotone" dataKey="setPoint" name="Set Point" stroke="hsl(var(--ink-2))" strokeDasharray="4 4" strokeWidth={1.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost flex flex-col min-h-0">
          <p className="mb-1 text-xs font-semibold text-ink shrink-0">{`Temperature — ${vehicleLabel}`}</p>
          <div className="flex-1 min-h-0">
            {loading && <ChartLoading />}
            {!loading && error && <PanelError message={error} />}
            {!loading && !error && result && readings && threshold && (
              <TemperatureChart readings={readings} forecast={result.forecast} threshold={threshold} compact />
            )}
            {!loading && !error && (!result || !readings || !threshold) && (
              <PanelEmpty message="Select a scenario or import a CSV." />
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 shrink-0">
        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost flex items-center gap-4">
          <DonutStat segments={DISTRIBUTION} size={84} />
          <div>
            <p className="mb-1 text-xs font-semibold text-ink">Temperature Distribution</p>
            <div className="space-y-0.5 text-[11px]">
              {DISTRIBUTION.map((d) => (
                <div key={d.name} className="flex items-center gap-1.5">
                  <span className="size-1.5 rounded-full" style={{ backgroundColor: d.color }} />
                  <span className="text-muted-foreground">{d.name}</span>
                  <span className="font-medium text-ink">{d.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost flex items-center gap-4">
          <DonutStat segments={SENSOR_HEALTH} size={84} centerValue={`${MONITORING_STATS.sensorHealthy}%`} />
          <div>
            <p className="text-xs font-semibold text-ink">Sensor Health</p>
            <p className="text-[11px] text-muted-foreground">Healthy vehicle sensors fleet-wide</p>
          </div>
        </div>
      </div>
    </div>
  );
}
