"use client";

import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { KpiCard } from "@/components/kpi-card";
import { Icon } from "@/components/icon";
import { TemperatureChart } from "@/components/temperature-chart";
import { ChartLoading, PanelError, PanelEmpty } from "@/components/panel-states";
import { getVehicleLabel } from "@/lib/dashboard-data";
import { SHIPMENT_STATS, SHIPMENTS, FleetShipment } from "@/lib/fleet-data";
import { AnalyzeResponse, CargoThreshold, SensorReading } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ShipmentPanelProps {
  loading: boolean;
  error: string | null;
  result: AnalyzeResponse | null;
  readings: SensorReading[] | null;
  threshold: CargoThreshold | null;
  scenarioId: string | null;
}

const STATUS_STYLE: Record<FleetShipment["status"], string> = {
  "In Transit": "bg-mint-soft text-mint",
  Delivered: "bg-brand-soft text-brand",
  "In Warehouse": "bg-secondary text-muted-foreground",
  Delayed: "bg-critical-soft text-critical",
};

const STATUS_BREAKDOWN = [
  { label: "In Transit", value: SHIPMENT_STATS.inTransit.value, color: "hsl(var(--mint))" },
  { label: "Delivered", value: SHIPMENT_STATS.delivered.value, color: "hsl(var(--brand))" },
  { label: "Warehouse", value: SHIPMENT_STATS.inWarehouse.value, color: "hsl(var(--coral))" },
  { label: "Delayed", value: SHIPMENT_STATS.delayed.value, color: "hsl(var(--critical))" },
];

export function ShipmentPanel({ loading, error, result, readings, threshold, scenarioId }: ShipmentPanelProps) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string>("All");
  const vehicleLabel = getVehicleLabel(scenarioId);

  const filtered = SHIPMENTS.filter((s) => {
    const matchesStatus = status === "All" || s.status === status;
    const q = query.trim().toLowerCase();
    const matchesQuery =
      q === "" || s.id.toLowerCase().includes(q) || s.route.toLowerCase().includes(q) || s.vehicleId.toLowerCase().includes(q);
    return matchesStatus && matchesQuery;
  });

  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex shrink-0 items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-[19px] font-bold text-ink leading-tight">Shipments</h2>
          <p className="text-xs text-muted-foreground mt-0">Track and manage all your shipments in real-time.</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-xl border border-border bg-card px-2.5 py-1.5 shadow-frost">
            <Icon size={13} tone="gray" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search..."
              className="w-32 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
            />
          </div>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-xl border border-border bg-card px-2.5 py-1.5 text-xs shadow-frost outline-none"
          >
            {["All", "In Transit", "Delivered", "In Warehouse", "Delayed"].map((s) => (
              <option key={s} value={s}>Status: {s}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5 shrink-0">
        <KpiCard accent="blue" label="Total Shipments" value={`${SHIPMENT_STATS.total.value}`} note={`↑${SHIPMENT_STATS.total.delta}`} noteTone="mint" />
        <KpiCard accent="blue" label="In Transit" value={`${SHIPMENT_STATS.inTransit.value}`} note={`↑${SHIPMENT_STATS.inTransit.delta}`} noteTone="mint" />
        <KpiCard accent="mint" label="Delivered" value={`${SHIPMENT_STATS.delivered.value}`} note={`↑${SHIPMENT_STATS.delivered.delta}`} noteTone="mint" />
        <KpiCard accent="coral" label="In Warehouse" value={`${SHIPMENT_STATS.inWarehouse.value}`} note={SHIPMENT_STATS.inWarehouse.delta} noteTone="critical" />
        <KpiCard accent="critical" label="Delayed" value={`${SHIPMENT_STATS.delayed.value}`} note={SHIPMENT_STATS.delayed.delta} noteTone="critical" />
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 shrink-0" style={{ height: 210 }}>
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
          <p className="mb-1 text-xs font-semibold text-ink shrink-0">Shipment Status (All Vehicles)</p>
          <div className="flex-1 min-h-0">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={STATUS_BREAKDOWN} layout="vertical" margin={{ top: 0, right: 16, left: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-border" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="label" tick={{ fontSize: 10 }} width={64} interval={0} />
                <Tooltip contentStyle={{ borderRadius: 12, borderColor: "hsl(var(--border))", fontSize: 12 }} />
                <Bar isAnimationActive={false} dataKey="value" radius={[0, 6, 6, 0]}>
                  {STATUS_BREAKDOWN.map((d, i) => (
                    <Cell key={i} fill={d.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-border bg-card shadow-frost flex-1 min-h-0 overflow-y-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border text-left text-[10px] text-muted-foreground sticky top-0 bg-card">
              <th className="whitespace-nowrap px-3 py-2 font-medium">Shipment ID</th>
              <th className="whitespace-nowrap px-3 py-2 font-medium">Route</th>
              <th className="whitespace-nowrap px-3 py-2 font-medium">Vehicle ID</th>
              <th className="whitespace-nowrap px-3 py-2 font-medium">Status</th>
              <th className="whitespace-nowrap px-3 py-2 font-medium">Product</th>
              <th className="whitespace-nowrap px-3 py-2 font-medium">Qty</th>
              <th className="whitespace-nowrap px-3 py-2 font-medium">Temp. Range</th>
              <th className="whitespace-nowrap px-3 py-2 font-medium">ETA</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => (
              <tr key={s.id} className="border-b border-border/60 last:border-0">
                <td className="whitespace-nowrap px-3 py-2.5 font-mono text-brand">{s.id}</td>
                <td className="whitespace-nowrap px-3 py-2.5 text-ink">{s.route}</td>
                <td className="whitespace-nowrap px-3 py-2.5 font-mono text-ink">{s.vehicleId}</td>
                <td className="whitespace-nowrap px-3 py-2.5">
                  <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", STATUS_STYLE[s.status])}>{s.status}</span>
                </td>
                <td className="whitespace-nowrap px-3 py-2.5 text-ink">{s.product}</td>
                <td className="whitespace-nowrap px-3 py-2.5 text-ink">{s.quantity}</td>
                <td className="whitespace-nowrap px-3 py-2.5 text-muted-foreground">{s.tempRange}</td>
                <td className="whitespace-nowrap px-3 py-2.5 text-muted-foreground">{s.eta}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
