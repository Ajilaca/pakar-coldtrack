import { Icon, IconName } from "@/components/icon";
import { ProgressRing } from "@/components/progress-ring";
import { Driver } from "@/lib/types";

/**
 * Baris "Mengapa AI berpikir begini" — tiga fitur pendorong teratas, masing-
 * masing dalam kotaknya sendiri dengan cincin persentase.
 */

/**
 * Peta nama fitur dari backend (app/explain.py) ke ikon + nama yang terbaca
 * manusia. Backend mengirim snake_case seperti "laju_kenaikan_suhu"; itu nama
 * internal, tidak layak tampil apa adanya di depan juri.
 *
 * Kalau R3 menambah fitur pendorong baru, tambahkan barisnya di sini —
 * yang belum terdaftar akan jatuh ke tampilan cadangan di bawah.
 */
const FEATURE_META: Record<string, { icon: IconName; label: string }> = {
  laju_kenaikan_suhu: { icon: "rate", label: "Laju kenaikan suhu" },
  delta_suhu_ambien: { icon: "ambient", label: "Kenaikan suhu ambien" },
  beban_panas_berhenti: { icon: "ambient", label: "Panas saat berhenti" },
  durasi_reefer_aktif: { icon: "reefer", label: "Durasi pendingin aktif" },
  status_pintu: { icon: "door", label: "Status pintu kargo" },
  variansi_suhu: { icon: "sensor", label: "Variansi pembacaan suhu" },
};

/** Cadangan: ubah snake_case jadi kalimat berkapital. */
function humanize(feature: string) {
  const s = feature.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function DriverList({ drivers }: { drivers: Driver[] }) {
  if (drivers.length === 0) return null;
  const top3 = [...drivers].sort((a, b) => b.contribution - a.contribution).slice(0, 3);

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {top3.map((d, i) => {
        const meta = FEATURE_META[d.feature];
        const label = meta?.label ?? humanize(d.feature);
        const icon: IconName = meta?.icon ?? "sensor";

        return (
          <div
            key={d.feature}
            className="card glass-interactive flex flex-col items-center gap-2.5 px-3 py-4 text-center"
          >
            <ProgressRing value={d.contribution} size={76} />

            <div className="min-w-0 space-y-1">
              <div className="flex items-center justify-center gap-1.5">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-lg bg-brand-soft">
                  <Icon name={icon} size={13} className="text-brand" />
                </span>
                <p className="t-body truncate font-semibold text-ink" title={label}>
                  {label}
                </p>
              </div>
              <p className="t-meta truncate" title={d.value}>
                {d.value}
              </p>
            </div>

            {i === 0 && (
              <span className="rounded-full bg-brand-soft px-2 py-0.5 t-pill text-brand">
                Paling berpengaruh
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
