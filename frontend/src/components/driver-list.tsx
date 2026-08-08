import { Driver } from "@/lib/types";

export function DriverList({ drivers }: { drivers: Driver[] }) {
  if (drivers.length === 0) return null;
  const top3 = [...drivers].sort((a, b) => b.contribution - a.contribution).slice(0, 3);

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Faktor pendorong utama
      </p>
      <div className="space-y-2">
        {top3.map((d) => (
          <div key={d.feature} className="flex items-center gap-3 text-sm">
            <span className="w-40 shrink-0 text-foreground">{d.feature}</span>
            <div className="h-1.5 flex-1 rounded-full bg-muted overflow-hidden">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${Math.round(d.contribution * 100)}%` }}
              />
            </div>
            <span className="w-9 shrink-0 text-right text-xs text-muted-foreground">
              {Math.round(d.contribution * 100)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}