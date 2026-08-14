"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { KpiCard } from "@/components/kpi-card";
import { TemperatureChart } from "@/components/temperature-chart";
import { DummyMap } from "@/components/dummy-map";
import { ChartLoading, PanelError, PanelEmpty } from "@/components/panel-states";
import { getVehicleLabel } from "@/lib/dashboard-data";
import { ROUTE_STATS, ROUTES, SELECTED_ROUTE_DETAIL } from "@/lib/fleet-data";
import { AnalyzeResponse, CargoThreshold, SensorReading } from "@/lib/types";
import { cn } from "@/lib/utils";

interface RoutePanelProps {
  loading: boolean;
  error: string | null;
  result: AnalyzeResponse | null;
  readings: SensorReading[] | null;
  threshold: CargoThreshold | null;
  scenarioId: string | null;
}

const DISTANCE_REMAINING = ROUTES.map((r) => ({
  route: r.route.split(" → ")[0],
  km: parseInt(r.distanceRemaining) || 0,
  tone: r.tempTone,
}));

export function RoutePanel({ loading, error, result, readings, threshold, scenarioId }: RoutePanelProps) {
  const vehicleLabel = getVehicleLabel(scenarioId);
  const mapRoute = {
    origin: SELECTED_ROUTE_DETAIL.origin,
    destination: SELECTED_ROUTE_DETAIL.destination,
    distanceKm: SELECTED_ROUTE_DETAIL.distanceKm,
    durationMin: 248,
    originPoint: SELECTED_ROUTE_DETAIL.originPoint,
    waypoint: SELECTED_ROUTE_DETAIL.waypoint,
    destPoint: SELECTED_ROUTE_DETAIL.destPoint,
  };

  return (
    <div className="flex h-full flex-col gap-3">
      <div>
        <h2 className="font-display text-[19px] font-bold text-ink leading-tight">Route Tracking</h2>
        <p className="text-xs text-muted-foreground mt-0">Track routes and monitor shipments and vehicles in real-time.</p>
      </div>

      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5 shrink-0">
        <KpiCard accent="blue" label="Active Routes" value={`${ROUTE_STATS.activeRoutes}`} note="Live" />
        <KpiCard accent="mint" label="Total Distance" value={`${ROUTE_STATS.totalDistanceKm.toLocaleString()} km`} note="Today" />
        <KpiCard accent="blue" label="On Time" value={`${ROUTE_STATS.onTimePct}%`} note={ROUTE_STATS.onTimeRatio} />
        <KpiCard accent="amber" label="Delayed" value={`${ROUTE_STATS.delayed}`} noteTone="amber" note="Routes" />
        <KpiCard accent="coral" label="Completed" value={`${ROUTE_STATS.completed}`} note="Today" />
      </div>

      <div className="grid flex-1 grid-cols-1 gap-3 lg:grid-cols-[1.3fr_1fr] min-h-0">
        <DummyMap
          routeInfo={mapRoute}
          vehicleLabel={SELECTED_ROUTE_DETAIL.vehicleId}
          status="AMAN"
          currentTemp={2.4}
          elapsedMin={186}
          fill
        />

        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost overflow-y-auto">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-ink">Selected Route Details</p>
            <span className="rounded-full bg-mint-soft px-2 py-0.5 text-[10px] font-medium text-mint">In Transit</span>
          </div>
          <div className="mt-2 space-y-1 text-[11px]">
            <div className="flex justify-between"><span className="text-muted-foreground">Route</span><span className="font-medium text-ink">{SELECTED_ROUTE_DETAIL.route}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Vehicle ID</span><span className="font-mono text-ink">{SELECTED_ROUTE_DETAIL.vehicleId}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Driver</span><span className="font-medium text-brand">{SELECTED_ROUTE_DETAIL.driver}</span></div>
            <div className="flex justify-between"><span className="text-muted-foreground">Distance</span><span className="font-medium text-ink">{SELECTED_ROUTE_DETAIL.distanceKm} km</span></div>
          </div>
          <div className="mt-2">
            <div className="flex justify-between text-[11px] mb-1"><span className="text-muted-foreground">Progress</span><span className="font-medium text-ink">{SELECTED_ROUTE_DETAIL.progressPct}%</span></div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
              <div className="h-full rounded-full bg-brand" style={{ width: `${SELECTED_ROUTE_DETAIL.progressPct}%` }} />
            </div>
          </div>
          <p className="mt-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Route Stops</p>
          <ol className="mt-1 space-y-1">
            {SELECTED_ROUTE_DETAIL.stops.map((s) => (
              <li key={s.name} className="flex items-center justify-between text-[11px]">
                <span className="flex items-center gap-1.5">
                  <span className={cn("size-1.5 rounded-full", s.state === "ETA" ? "bg-secondary" : s.state === "In Progress" ? "bg-amberwarn" : "bg-mint")} />
                  <span className="font-medium text-ink">{s.name}</span>
                </span>
                <span className="text-muted-foreground">{s.time}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 shrink-0" style={{ height: 150 }}>
        <div className="rounded-2xl border border-border bg-card p-3 shadow-frost flex flex-col min-h-0">
          <p className="mb-1 text-xs font-semibold text-ink shrink-0">{`Temperature en route — ${vehicleLabel}`}</p>
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
          <p className="mb-1 text-xs font-semibold text-ink shrink-0">Distance Remaining (All Routes)</p>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={DISTANCE_REMAINING} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" vertical={false} />
                <XAxis dataKey="route" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ borderRadius: 12, borderColor: "hsl(var(--border))", fontSize: 12 }} />
                <Bar isAnimationActive={false} dataKey="km" radius={[6, 6, 0, 0]}>
                  {DISTANCE_REMAINING.map((d, i) => (
                    <Cell key={i} fill={d.tone === "high" ? "hsl(var(--critical))" : "hsl(var(--brand))"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}
