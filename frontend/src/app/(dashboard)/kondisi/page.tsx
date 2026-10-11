"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { PageHeader } from "@/components/fleet/notifications";
import { TruckPanel } from "@/components/fleet/truck-panel";
import { Card, Galat, Kosong, Muat, StatusPill } from "@/components/fleet/ui";
import { trukPath } from "@/lib/fleet-api";
import { FleetStatus, Truk } from "@/lib/fleet-types";
import { muatan } from "@/lib/fleet-status";
import { useFleet } from "@/lib/use-fleet";
import { cn } from "@/lib/utils";

const FILTER: { id: string; label: string; cocok: (s: FleetStatus) => boolean }[] = [
  { id: "semua", label: "Semua", cocok: () => true },
  { id: "kritis", label: "Kritis", cocok: (s) => s === "KRITIS" },
  { id: "waspada", label: "Waspada", cocok: (s) => s === "WASPADA" },
  { id: "aman", label: "Aman", cocok: (s) => s === "AMAN" },
  { id: "offline", label: "Offline", cocok: (s) => s === "TIDAK_ADA_DATA" },
  { id: "lain", label: "Data belum cukup", cocok: (s) => s === "MENUNGGU_DATA" || s === "DATA_TIDAK_LENGKAP" },
];

function Isi() {
  const truk = useFleet<Truk[]>("/api/v1/fleet/trucks");
  const params = useSearchParams();
  const router = useRouter();
  const [filter, setFilter] = useState("semua");
  const daftar = (truk.data ?? []).filter((t) => FILTER.find((f) => f.id === filter)!.cocok(t.status));
  const pilih = params.get("id") ?? truk.data?.[0]?.truck_id ?? null;

  return (
    <>
      <PageHeader title="Kondisi armada" subtitle="Status, prediksi suhu, dan tindakan per truk" />
      {truk.error && <Galat pesan={truk.error} onRetry={truk.reload} />}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
        <Card title="Daftar truk" className="lg:sticky lg:top-6 lg:max-h-[calc(100dvh-48px)] lg:overflow-y-auto">
          <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Saring status">
            {FILTER.map((f) => {
              const n = (truk.data ?? []).filter((t) => f.cocok(t.status)).length;
              if (f.id === "lain" && n === 0) return null;
              return (
                <button
                  key={f.id} type="button" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}
                  className={cn("rounded-full border px-3 py-1 text-[12px] font-medium", filter === f.id ? "border-[var(--chart-actual)] bg-[var(--chart-actual)] text-white" : "bg-surface hover:bg-surface-muted")}
                >
                  {f.label} <span className="num">{n}</span>
                </button>
              );
            })}
          </div>
          {!truk.data ? (
            <Muat tinggi={400} />
          ) : daftar.length === 0 ? (
            <Kosong>Tidak ada truk dengan status ini.</Kosong>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {daftar.map((t) => {
                const ttb = t.kondisi?.time_to_breach_min;
                const aktif = t.truck_id === pilih;
                return (
                  <li key={t.truck_id}>
                    <button
                      type="button"
                      onClick={() => router.replace(`/kondisi?id=${encodeURIComponent(t.truck_id)}`, { scroll: false })}
                      aria-current={aktif ? "true" : undefined}
                      className={cn("flex w-full items-center justify-between gap-2 rounded-xl border px-3 py-2.5 text-left", aktif ? "border-[var(--chart-actual)] bg-[#f3f6ff]" : "border-transparent hover:bg-surface-muted")}
                    >
                      <span className="min-w-0">
                        <span className="block font-semibold">{t.truck_id}</span>
                        <span className="block truncate text-[12px] text-muted">
                          {muatan(t.trip?.profil?.id)}
                          {ttb != null && ` · TTB ${Math.round(ttb)} mnt`}
                        </span>
                      </span>
                      <StatusPill status={t.status} />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
        <div className="flex min-w-0 flex-col gap-3">
          {pilih ? (
            <>
              <div className="flex items-center justify-between">
                <h2 className="text-[16px] font-semibold">{pilih}</h2>
                <Link href={trukPath(pilih)} className="text-[13px] font-medium text-accent hover:underline">Detail truk →</Link>
              </div>
              <TruckPanel truckId={pilih} />
            </>
          ) : (
            truk.data && <Kosong>Belum ada truk.</Kosong>
          )}
        </div>
      </div>
    </>
  );
}

export default function KondisiPage() {
  return (
    <Suspense fallback={<Muat tinggi={400} />}>
      <Isi />
    </Suspense>
  );
}
