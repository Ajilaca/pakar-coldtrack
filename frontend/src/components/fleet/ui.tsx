// Potongan UI armada kecil yang dipakai banyak halaman (pill, KPI, kartu, keadaan muat/galat).

import { ReactNode } from "react";
import type { Icon } from "@phosphor-icons/react";
import { WarningCircle } from "@phosphor-icons/react/dist/ssr";
import { tone } from "@/lib/fleet-status";
import { cn } from "@/lib/utils";

export function StatusPill({ status, className }: { status: string; className?: string }) {
  const t = tone(status);
  return (
    <span className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-bold tracking-[0.02em]", t.pill, className)}>
      <t.Icon size={13} weight="bold" aria-hidden />
      {t.word}
    </span>
  );
}

export function Card({ title, aside, children, className }: { title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("min-w-0 rounded-2xl border bg-surface p-5 shadow-[0_1px_2px_rgb(15_23_42/0.04)]", className)}>
      {(title || aside) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-[15px] font-semibold text-ink">{title}</h2>}
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

const KPI_TONE = {
  ink: { text: "text-ink", ring: "bg-[#e8edfb] text-[#2b3f87]" },
  crit: { text: "text-crit", ring: "bg-crit-soft text-crit" },
  warn: { text: "text-warn", ring: "bg-warn-soft text-warn" },
  ok: { text: "text-ok", ring: "bg-ok-soft text-ok" },
};

export function Kpi({ label, value, note, icon: I, tone: t = "ink" }: {
  label: string; value: ReactNode; note?: ReactNode; icon: Icon; tone?: keyof typeof KPI_TONE;
}) {
  const k = KPI_TONE[t];
  return (
    <section className="flex min-w-0 flex-col gap-3 rounded-2xl border bg-surface p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[13px] text-muted">{label}</p>
          <p className={cn("num mt-2 whitespace-nowrap text-[28px] font-bold leading-none tracking-[-0.02em] xl:text-[30px]", k.text)}>{value}</p>
        </div>
        <span className={cn("flex size-14 shrink-0 items-center justify-center rounded-full", k.ring)}>
          <I size={28} aria-hidden />
        </span>
      </div>
      {note && <p className="text-[12px] text-muted">{note}</p>}
    </section>
  );
}

export function Bar({ value, max = 1, color = "var(--chart-actual)", className }: { value: number; max?: number; color?: string; className?: string }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div className={cn("h-1.5 overflow-hidden rounded-full bg-[#e9edf5]", className)} aria-hidden>
      <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

export function Muat({ tinggi = 240, className }: { tinggi?: number; className?: string }) {
  return <div className={cn("animate-pulse rounded-2xl bg-surface-muted", className)} style={{ height: tinggi }} aria-busy="true" aria-label="Memuat" />;
}

export function Galat({ pesan, onRetry }: { pesan: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-2xl border border-l-[3px] border-l-crit bg-surface p-4">
      <WarningCircle size={20} className="mt-0.5 shrink-0 text-crit" aria-hidden />
      <div className="flex flex-col gap-2">
        <p className="font-semibold">Data armada tidak dapat dimuat</p>
        <p className="text-muted">{pesan}</p>
        {onRetry && (
          <button type="button" onClick={onRetry} className="w-fit rounded-md bg-brand px-3 py-1.5 text-[13px] font-medium text-brand-on hover:opacity-90">
            Coba lagi
          </button>
        )}
      </div>
    </div>
  );
}

export function Kosong({ children }: { children: ReactNode }) {
  return <p className="rounded-xl border border-dashed p-6 text-center text-[13px] text-muted">{children}</p>;
}
