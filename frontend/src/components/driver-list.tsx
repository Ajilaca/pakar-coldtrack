import { Driver } from "@/lib/types";

/**
 * Baris "Mengapa AI berpikir begini" — tiga fitur pendorong teratas.
 * Label bidang dirender oleh pemanggil; komponen ini hanya isinya.
 */
export function DriverList({ drivers }: { drivers: Driver[] }) {
  if (drivers.length === 0) return null;
  const top3 = [...drivers].sort((a, b) => b.contribution - a.contribution).slice(0, 3);

  return (
    <div className="space-y-2">
      {top3.map((d) => (
        <div key={d.feature} className="space-y-1">
          <div className="flex items-baseline justify-between gap-2">
            <span className="t-body truncate text-ink">{d.feature}</span>
            <span className="t-meta shrink-0 tabular">{Math.round(d.contribution * 100)}%</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
            <div
              className="grad-brand h-full rounded-full"
              style={{ width: `${Math.round(d.contribution * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
