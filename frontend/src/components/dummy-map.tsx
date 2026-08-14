"use client";

import { Icon } from "@/components/icon";
import { RouteInfo } from "@/lib/dashboard-data";
import { formatDuration } from "@/lib/metrics";
import { ShipmentStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

interface DummyMapProps {
  routeInfo: RouteInfo;
  vehicleLabel: string;
  status: ShipmentStatus;
  currentTemp: number | null;
  elapsedMin: number;
  compact?: boolean;
  fill?: boolean;
}

const STATUS_DOT: Record<ShipmentStatus, { dot: string; text: string }> = {
  AMAN: { dot: "bg-mint", text: "text-mint" },
  WASPADA: { dot: "bg-amberwarn", text: "text-amberwarn" },
  KRITIS: { dot: "bg-critical", text: "text-critical" },
};

function quadPoint(p0: { x: number; y: number }, p1: { x: number; y: number }, p2: { x: number; y: number }, t: number) {
  const mt = 1 - t;
  return {
    x: mt * mt * p0.x + 2 * mt * t * p1.x + t * t * p2.x,
    y: mt * mt * p0.y + 2 * mt * t * p1.y + t * t * p2.y,
  };
}

function approxLength(p0: { x: number; y: number }, p1: { x: number; y: number }, p2: { x: number; y: number }) {
  let len = 0;
  let prev = p0;
  for (let i = 1; i <= 24; i++) {
    const pt = quadPoint(p0, p1, p2, i / 24);
    len += Math.hypot(pt.x - prev.x, pt.y - prev.y);
    prev = pt;
  }
  return len;
}

export function DummyMap({ routeInfo, vehicleLabel, status, currentTemp, elapsedMin, compact, fill }: DummyMapProps) {
  const { originPoint: p0, waypoint: p1, destPoint: p2, distanceKm, durationMin, origin, destination } = routeInfo;
  const rawProgress = durationMin ? (elapsedMin / durationMin) * 100 : 50;
  const progress = Math.min(96, Math.max(4, rawProgress));
  const truckPos = quadPoint(p0, p1, p2, progress / 100);
  const pathD = `M ${p0.x} ${p0.y} Q ${p1.x} ${p1.y} ${p2.x} ${p2.y}`;
  const length = approxLength(p0, p1, p2);

  return (
    <div
      className="relative overflow-hidden rounded-2xl border border-border shadow-frost"
      style={fill ? { height: "100%" } : { height: compact ? 220 : 400 }}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-brand-soft via-[hsl(205,55%,96%)] to-mint-soft" />
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
        {Array.from({ length: 9 }).map((_, i) => (
          <line key={`v${i}`} x1={i * 12.5} y1={0} x2={i * 12.5} y2={100} stroke="white" strokeOpacity={0.5} strokeWidth={0.3} />
        ))}
        {Array.from({ length: 7 }).map((_, i) => (
          <line key={`h${i}`} x1={0} y1={i * 16.6} x2={100} y2={i * 16.6} stroke="white" strokeOpacity={0.5} strokeWidth={0.3} />
        ))}
        <path d={pathD} fill="none" stroke="hsl(var(--ink-2))" strokeOpacity={0.18} strokeWidth={1.6} strokeLinecap="round" />
        <path
          d={pathD}
          fill="none"
          stroke="hsl(var(--brand))"
          strokeWidth={1.6}
          strokeLinecap="round"
          strokeDasharray={`${length} ${length}`}
          strokeDashoffset={length * (1 - progress / 100)}
        />
      </svg>

      <div
        className="absolute flex -translate-x-1/2 -translate-y-full flex-col items-center drop-shadow"
        style={{ left: `${p0.x}%`, top: `${p0.y}%` }}
      >
        <div className={cn("flex items-center justify-center rounded-full ring-2 ring-white", compact ? "size-6" : "size-8", "bg-mint")}>
          <Icon size={compact ? 12 : 16} tone="white" />
        </div>
      </div>
      <div
        className="absolute flex -translate-x-1/2 -translate-y-full flex-col items-center drop-shadow"
        style={{ left: `${p2.x}%`, top: `${p2.y}%` }}
      >
        <div className={cn("flex items-center justify-center rounded-full ring-2 ring-white", compact ? "size-6" : "size-8", "bg-coral")}>
          <Icon size={compact ? 12 : 16} tone="white" />
        </div>
      </div>
      <div
        className="absolute -translate-x-1/2 -translate-y-1/2 drop-shadow-lg"
        style={{ left: `${truckPos.x}%`, top: `${truckPos.y}%` }}
      >
        <div className={cn("flex items-center justify-center rounded-full ring-2 ring-white bg-ink", compact ? "size-7" : "size-9")}>
          <Icon size={compact ? 14 : 18} tone="white" />
        </div>
      </div>

      <span className="absolute left-3 top-3 rounded-full bg-ink/80 px-2.5 py-1 text-[10px] font-medium text-white backdrop-blur-sm">
        Pratinjau peta — integrasi Google Maps segera
      </span>

      {!compact && (
        <div className="absolute right-3 top-3 w-56 rounded-xl bg-white/95 p-3 shadow-frost backdrop-blur-sm">
          <div className="flex items-center justify-between">
            <span className="font-mono text-sm font-semibold text-ink">{vehicleLabel}</span>
            <span className={cn("flex items-center gap-1 text-[10px] font-medium", STATUS_DOT[status].text)}>
              <span className={cn("size-1.5 rounded-full", STATUS_DOT[status].dot)} />
              {status}
            </span>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">Rute</p>
          <p className="text-sm font-medium text-ink">{origin} → {destination}</p>
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
            <div>
              <p className="text-muted-foreground">Jarak</p>
              <p className="font-medium text-ink">{distanceKm ? `${distanceKm} km` : "\u2014"}</p>
            </div>
            <div>
              <p className="text-muted-foreground">Estimasi tempuh</p>
              <p className="font-medium text-ink">{formatDuration(durationMin)}</p>
            </div>
          </div>
          <div className="mt-2 flex items-center justify-between border-t border-border pt-2">
            <span className="text-xs text-muted-foreground">Suhu saat ini</span>
            <span className="text-xs font-semibold text-ink">{currentTemp !== null ? `${currentTemp}\u00b0C` : "\u2014"}</span>
          </div>
        </div>
      )}
    </div>
  );
}
