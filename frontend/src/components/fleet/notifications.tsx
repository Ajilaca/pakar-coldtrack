"use client";

// Lonceng + panel notifikasi dan toast live (frame Figma "Ringkasan + notifikasi").

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowRight, Bell, CheckCircle, MinusCircle, Warning, WifiHigh, WifiSlash, X, XCircle } from "@phosphor-icons/react/dist/ssr";
import { tandaiDibaca, tandaiSemuaDibaca, trukPath } from "@/lib/fleet-api";
import { Notifikasi } from "@/lib/fleet-types";
import { relatif } from "@/lib/format";
import { useFleet, useFleetCtx } from "@/lib/use-fleet";
import { cn } from "@/lib/utils";

const LEVEL = {
  kritis: { Icon: XCircle, cls: "text-crit bg-crit-soft", bar: "bg-crit" },
  waspada: { Icon: Warning, cls: "text-warn bg-warn-soft", bar: "bg-warn" },
  ok: { Icon: CheckCircle, cls: "text-ok bg-ok-soft", bar: "bg-ok" },
  info: { Icon: MinusCircle, cls: "text-offline bg-offline-soft", bar: "bg-offline" },
};

export function NotificationBell() {
  const { data, reload } = useFleet<{ belum_dibaca: number; items: Notifikasi[] }>("/api/v1/notifications?limit=30");
  const { now, live } = useFleetCtx();
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
    <>
      {/* latar halaman diburamkan saat panel terbuka (Figma) */}
      {open && <div className="fixed inset-0 z-30 bg-[#dfe6f3]/60 backdrop-blur-[3px]" aria-hidden />}
      <div ref={ref} className="relative z-40">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-label={`Notifikasi, ${n} belum dibaca`}
          className="relative flex size-11 items-center justify-center rounded-full border bg-surface text-ink shadow-sm hover:bg-surface-muted"
        >
          <Bell size={22} aria-hidden />
          {n > 0 && (
            <span className="num absolute -right-1 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-crit px-1 text-[10px] font-bold text-white">
              {n > 99 ? "99+" : n}
            </span>
          )}
        </button>
        {open && (
          <div className="absolute right-0 top-14 w-[min(400px,calc(100vw-32px))] overflow-hidden rounded-2xl border bg-surface shadow-2xl">
            <div className="flex items-center justify-between px-5 py-4">
              <p className="text-[17px] font-semibold">Notifikasi</p>
              <button
                type="button"
                className="text-[13px] font-medium text-[var(--chart-actual)] hover:underline disabled:text-muted disabled:no-underline"
                disabled={n === 0}
                onClick={async () => {
                  await tandaiSemuaDibaca();
                  reload();
                }}
              >
                Tandai semua dibaca
              </button>
            </div>
            <ul className="max-h-[440px] overflow-y-auto border-t">
              {(data?.items ?? []).length === 0 && <li className="p-6 text-center text-[13px] text-muted">Belum ada notifikasi.</li>}
              {(data?.items ?? []).map((x) => {
                const L = LEVEL[x.level] ?? LEVEL.info;
                return (
                  <li key={x.id} className={cn("border-b last:border-0", !x.read_at && "bg-[#f1f4f9]")}>
                    <Link
                      href={x.truck_id ? trukPath(x.truck_id) : "/tindakan"}
                      onClick={async () => {
                        setOpen(false);
                        if (!x.read_at) {
                          await tandaiDibaca(x.id);
                          reload();
                        }
                      }}
                      className="flex items-start gap-3 px-5 py-3.5 hover:bg-surface-muted"
                    >
                      <span className={cn("mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full", L.cls)}>
                        <L.Icon size={18} weight="bold" aria-hidden />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[14px] font-semibold text-ink">{x.title}</span>
                        {x.body && <span className="block text-[13px] text-muted">{x.body}</span>}
                        <span className="block text-[12px] text-muted">{relatif(x.created_at, now)}</span>
                      </span>
                      {!x.read_at && <span className="mt-1.5 size-2 shrink-0 rounded-full bg-[var(--chart-actual)]" aria-label="belum dibaca" />}
                    </Link>
                  </li>
                );
              })}
            </ul>
            <p className="flex items-center gap-2 border-t px-5 py-3 text-[12px] text-muted">
              {live ? <WifiHigh size={16} className="text-ok" aria-hidden /> : <WifiSlash size={16} className="text-warn" aria-hidden />}
              {live ? "Terhubung via SSE · cadangan polling 30 detik" : "SSE terputus · memuat ulang tiap 30 detik"}
            </p>
          </div>
        )}
      </div>
    </>
  );
}

export function Toaster() {
  const { toasts, dismiss } = useFleetCtx();
  return (
    <div aria-live="assertive" className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(400px,calc(100vw-32px))] flex-col gap-3 lg:bottom-8 lg:right-8">
      {toasts.map((t) => {
        const L = LEVEL[t.level] ?? LEVEL.info;
        return (
          <div key={t.id} role="alert" className="pointer-events-auto flex items-start gap-3 rounded-2xl border bg-surface p-4 shadow-xl">
            <span className={cn("w-1 self-stretch rounded-full", L.bar)} aria-hidden />
            <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-full", L.cls)}>
              <L.Icon size={18} weight="bold" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[14px] font-semibold">{t.title}</p>
              {t.body && <p className="text-[13px] text-muted">{t.body}</p>}
              {t.truck_id && (
                <Link href={trukPath(t.truck_id)} className="mt-1 inline-flex items-center gap-1 text-[13px] font-semibold text-[var(--chart-actual)] hover:underline" onClick={() => dismiss(t.id)}>
                  Lihat truk <ArrowRight size={13} weight="bold" aria-hidden />
                </Link>
              )}
            </div>
            <button type="button" onClick={() => dismiss(t.id)} aria-label="Tutup" className="text-muted hover:text-ink">
              <X size={18} aria-hidden />
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
        <h1 className="text-[24px] font-bold tracking-[-0.02em] text-ink lg:text-[30px]">{title}</h1>
        {subtitle && <p className="mt-1 text-[14px] text-muted lg:text-[15px]">{subtitle}</p>}
      </div>
      <NotificationBell />
    </header>
  );
}
