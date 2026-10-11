"use client";

// Lonceng + kotak masuk (dropdown) dan toast notifikasi live (frame "Ringkasan + notifikasi").

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Bell, Info, Warning, X, XCircle } from "@phosphor-icons/react/dist/ssr";
import { tandaiDibaca, tandaiSemuaDibaca, trukPath } from "@/lib/fleet-api";
import { Notifikasi } from "@/lib/fleet-types";
import { relatif } from "@/lib/format";
import { useFleet, useFleetCtx } from "@/lib/use-fleet";
import { cn } from "@/lib/utils";

const LEVEL = {
  kritis: { Icon: XCircle, cls: "text-crit bg-crit-soft" },
  waspada: { Icon: Warning, cls: "text-warn bg-warn-soft" },
  info: { Icon: Info, cls: "text-offline bg-offline-soft" },
};

export function NotificationBell() {
  const { data, reload } = useFleet<{ belum_dibaca: number; items: Notifikasi[] }>("/api/v1/notifications?limit=30");
  const { now } = useFleetCtx();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const n = data?.belum_dibaca ?? 0;

  useEffect(() => {
    if (!open) return;
    const tutup = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", tutup);
    document.addEventListener("keydown", tutup);
    return () => {
      document.removeEventListener("mousedown", tutup);
      document.removeEventListener("keydown", tutup);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={`Notifikasi, ${n} belum dibaca`}
        className="relative flex size-10 items-center justify-center rounded-full text-ink hover:bg-surface-muted"
      >
        <Bell size={22} aria-hidden />
        {n > 0 && (
          <span className="num absolute -right-0.5 -top-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-crit px-1 text-[10px] font-bold text-white">
            {n > 99 ? "99+" : n}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-12 z-40 w-[min(380px,calc(100vw-32px))] overflow-hidden rounded-2xl border bg-surface shadow-xl">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <p className="font-semibold">Kotak masuk</p>
            <button
              type="button"
              className="text-[12px] font-medium text-accent hover:underline disabled:text-muted"
              disabled={n === 0}
              onClick={async () => {
                await tandaiSemuaDibaca();
                reload();
              }}
            >
              Tandai semua dibaca
            </button>
          </div>
          <ul className="max-h-[420px] overflow-y-auto">
            {(data?.items ?? []).length === 0 && <li className="p-6 text-center text-[13px] text-muted">Belum ada notifikasi.</li>}
            {(data?.items ?? []).map((x) => {
              const L = LEVEL[x.level] ?? LEVEL.info;
              return (
                <li key={x.id} className={cn("border-b last:border-0", !x.read_at && "bg-[#f6f8fe]")}>
                  <Link
                    href={x.truck_id ? trukPath(x.truck_id) : "/tindakan"}
                    onClick={async () => {
                      setOpen(false);
                      if (!x.read_at) {
                        await tandaiDibaca(x.id);
                        reload();
                      }
                    }}
                    className="flex items-start gap-3 px-4 py-3 hover:bg-surface-muted"
                  >
                    <span className={cn("mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full", L.cls)}>
                      <L.Icon size={15} weight="bold" aria-hidden />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[13px] font-medium text-ink">{x.title}</span>
                      {x.body && <span className="block truncate text-[12px] text-muted">{x.body}</span>}
                      <span className="block text-[11px] text-muted">{relatif(x.created_at, now)}</span>
                    </span>
                    {!x.read_at && <span className="mt-2 size-2 shrink-0 rounded-full bg-accent" aria-label="belum dibaca" />}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

export function Toaster() {
  const { toasts, dismiss } = useFleetCtx();
  return (
    <div aria-live="assertive" className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(360px,calc(100vw-32px))] flex-col gap-2">
      {toasts.map((t) => {
        const L = LEVEL[t.level] ?? LEVEL.info;
        return (
          <div key={t.id} role="alert" className={cn("pointer-events-auto flex items-start gap-3 rounded-xl border bg-surface p-3 shadow-lg", t.level === "kritis" ? "border-l-4 border-l-crit" : "border-l-4 border-l-warn")}>
            <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-full", L.cls)}>
              <L.Icon size={16} weight="bold" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold">{t.title}</p>
              {t.truck_id && (
                <Link href={trukPath(t.truck_id)} className="text-[12px] font-medium text-accent hover:underline" onClick={() => dismiss(t.id)}>
                  Buka detail truk →
                </Link>
              )}
            </div>
            <button type="button" onClick={() => dismiss(t.id)} aria-label="Tutup" className="text-muted hover:text-ink">
              <X size={16} aria-hidden />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export function PageHeader({ title, subtitle, back }: { title: string; subtitle?: string; back?: React.ReactNode }) {
  return (
    <header className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        {back}
        <h1 className="text-[24px] font-bold tracking-[-0.02em] text-ink lg:text-[28px]">{title}</h1>
        {subtitle && <p className="mt-1 text-[14px] text-muted">{subtitle}</p>}
      </div>
      <NotificationBell />
    </header>
  );
}
