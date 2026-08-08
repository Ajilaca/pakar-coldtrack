"use client";

import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Line, LineChart } from "recharts";
import { KpiCard } from "@/components/kpi-card";
import { Icon } from "@/components/icon";
import { TemperatureChart } from "@/components/temperature-chart";
import { DummyMap } from "@/components/dummy-map";
import { ChartLoading, PanelError, PanelEmpty } from "@/components/panel-states";
import { getRouteInfo, getVehicleLabel } from "@/lib/dashboard-data";
import { MONITORING_STATS, PREDICTION_TREND } from "@/lib/fleet-data";
import { AnalyzeResponse, CargoThreshold, SensorReading } from "@/lib/types";

interface OverviewPanelProps {
  loading: boolean;
  error: string | null;
  result: AnalyzeResponse | null;
  readings: SensorReading[] | null;
  threshold: CargoThreshold | null;
  scenarioId: string | null;
}

export function OverviewPanel({ loading, error, result, readings, threshold, scenarioId }: OverviewPanelProps) {
  const routeInfo = getRouteInfo(scenarioId);
  const vehicleLabel = getVehicleLabel(scenarioId);
  const last = readings ? readings[readings.length - 1] : null;
  const riskLabel = !result ? "\u2014" : result.status === "AMAN" ? "Low Risk" : result.status === "WASPADA" ? "Medium Risk" : "High Risk";
  const riskTextClass = !result ? "text-ink" : result.status === "AMAN" ? "text-mint" : result.status === "WASPADA" ? "text-amberwarn" : "text-critical";

  return (
    <div className="flex h-full flex-col gap-3">
      <div>
        <h2 className="font-display text-[19px] font-bold text-ink leading-tight">Cold Chain Logistics AI Dashboard</h2>
        <p className="text-xs text-muted-foreground mt-0">Real-time Monitoring • Predictive Analytics • Smart Decisions</p>
      </div>

      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5 shrink-0">
        <KpiCard accent="blue" label="Total Shipments" value="128" note="↑12%" noteTone="mint" />
        <KpiCard accent="mint" label="Vehicle ID" value={vehicleLabel} note="Live" />
        <KpiCard accent="blue" label="Temp. Compliance" value="98.2%" note="↑2.1%" noteTone="mint" />
        <KpiCard accent="coral" label="Active Vehicles" value={`${MONITORING_STATS.monitoredVehicles}`} note="Live" />
        <KpiCard accent="critical" label="At Risk Shipments" value="4" note="Attention" noteTone="critical" />
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
            {!loading && !error && (!result || !readings || !threshold) && (
              <PanelEmpty message="Select a scenario or import a CSV." />
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost flex flex-col min-h-0">
          <p className="mb-1 text-xs font-semibold text-ink shrink-0">Prediction Trend (Fleet-wide)</p>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={PREDICTION_TREND} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
                <XAxis dataKey="day" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ borderRadius: 12, borderColor: "hsl(var(--border))", fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                <Line isAnimationActive={false} type="monotone" dataKey="highRisk" name="High Risk" stroke="hsl(var(--critical))" strokeWidth={2} dot={{ r: 2 }} />
                <Line isAnimationActive={false} type="monotone" dataKey="tempViolation" name="Temp. Violation" stroke="hsl(var(--amber-warn))" strokeWidth={2} dot={{ r: 2 }} />
                <Line isAnimationActive={false} type="monotone" dataKey="delay" name="Delay" stroke="hsl(var(--brand))" strokeWidth={2} dot={{ r: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 shrink-0" style={{ height: 190 }}>
        <div className="min-h-0">
          <DummyMap
            routeInfo={routeInfo}
            vehicleLabel={vehicleLabel}
            status={result?.status ?? "AMAN"}
            currentTemp={last?.temperature_c ?? null}
            elapsedMin={last?.t_min ?? 0}
            compact
            fill
          />
        </div>

        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost overflow-hidden">
          <p className="mb-1.5 text-xs font-semibold text-ink">AI Prediction</p>
          {result ? (
            <div className="flex items-center gap-3">
              <div className="flex size-9 items-center justify-center rounded-xl bg-brand-soft shrink-0">
                <Icon size={16} tone="gray" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[10px] text-muted-foreground">Estimated Risk (Next 6 Hours)</p>
                <p className={`font-display text-base font-bold ${riskTextClass}`}>{riskLabel}</p>
              </div>
              <div className="w-24 shrink-0">
                <p className="text-[10px] text-muted-foreground text-right">Confidence</p>
                <p className="text-right text-sm font-semibold text-ink">{Math.round(result.failure_mode.confidence * 100)}%</p>
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">No analysis yet.</p>
          )}
          {result && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {result.drivers.slice(0, 3).map((d) => (
                <span key={d.feature} className="rounded-full bg-mint-soft px-2 py-0.5 text-[10px] font-medium text-mint">
                  ✓ {d.feature}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
