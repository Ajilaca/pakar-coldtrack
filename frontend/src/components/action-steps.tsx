import { ActionStep } from "@/lib/types";

/**
 * Langkah tindakan berurutan. Label bidang dirender oleh pemanggil;
 * komponen ini hanya daftarnya.
 *
 * Disusun mendatar di layar lebar supaya ketiganya terbaca sebagai satu
 * urutan langkah, bukan daftar bertumpuk yang harus dibaca ke bawah.
 */
export function ActionSteps({ actions }: { actions: ActionStep[] }) {
  const sorted = [...actions].sort((a, b) => a.priority - b.priority);

  return (
    <ol className="grid grid-cols-1 gap-2.5 lg:grid-cols-3">
      {sorted.map((action) => (
        <li
          key={action.priority}
          className="flex items-start gap-3 rounded-xl bg-secondary/60 px-3 py-3 transition-colors hover:bg-brand-soft"
        >
          <span className="grad-ocean flex size-7 shrink-0 items-center justify-center rounded-full t-body font-bold text-white shadow-[0_4px_10px_-4px_hsl(var(--ocean-deep)/0.6)]">
            {action.priority}
          </span>
          <div className="min-w-0 flex-1 space-y-1">
            <p className="t-body text-ink">{action.text}</p>
            {action.eta_min !== null && action.eta_min > 0 && (
              <span className="inline-flex items-center rounded-full bg-white/80 px-2 py-0.5 t-pill text-muted-foreground">
                ≈ {action.eta_min} menit
              </span>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
