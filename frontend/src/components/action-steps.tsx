import { ActionStep } from "@/lib/types";

/**
 * Tiga langkah tindakan berurutan. Label bidang dirender oleh pemanggil;
 * komponen ini hanya daftarnya.
 */
export function ActionSteps({ actions }: { actions: ActionStep[] }) {
  const sorted = [...actions].sort((a, b) => a.priority - b.priority);

  return (
    <ol className="space-y-2">
      {sorted.map((action) => (
        <li key={action.priority} className="flex items-start gap-2.5 rounded-xl bg-secondary/70 px-2.5 py-2">
          <span className="flex size-5 shrink-0 items-center justify-center grad-ocean rounded-full t-pill text-white">
            {action.priority}
          </span>
          <div className="min-w-0 flex-1">
            <p className="t-body text-ink">{action.text}</p>
            {action.eta_min !== null && action.eta_min > 0 && (
              <p className="t-meta mt-0.5">≈ {action.eta_min} menit</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
