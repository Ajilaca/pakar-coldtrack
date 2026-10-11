"use client";

import Link from "next/link";
import { PageHeader } from "@/components/fleet/notifications";
import { FleetMap, LegendaPeta } from "@/components/fleet/map-legend";
import { Card, Galat, Kosong, Muat, StatusPill } from "@/components/fleet/ui";
import { trukPath } from "@/lib/fleet-api";
import { Peta, Truk } from "@/lib/fleet-types";
import { muatan, tone } from "@/lib/fleet-status";
import { useFleet } from "@/lib/use-fleet";

export default function LokasiPage() {
  const peta = useFleet<Peta>("/api/v1/fleet/map");
  const truk = useFleet<Truk[]>("/api/v1/fleet/trucks");
  const perhatian = (truk.data ?? []).filter((t) => t.status === "KRITIS" || t.status === "WASPADA" || t.status === "TIDAK_ADA_DATA");

  return (
    <>
      <PageHeader title="Lokasi armada" subtitle="Posisi truk dan status depo/hub di Jawa" />
      {peta.error && <Galat pesan={peta.error} onRetry={peta.reload} />}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.8fr_1fr]">
        <Card
          title="Peta armada · Jawa"
          aside={<span className="text-[12px] text-muted">Klik penanda untuk membuka detail truk</span>}
        >
          <div className="h-[460px]">{peta.data ? <FleetMap peta={peta.data} /> : <Muat tinggi={460} />}</div>
          <LegendaPeta />
        </Card>
        <div className="flex flex-col gap-4">
          <Card title="Depo / hub">
            {!peta.data ? (
              <Muat tinggi={240} />
            ) : (
              <ul className="flex flex-col gap-3">
                {peta.data.depo.map((d) => (
                  <li key={d.id} className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2.5">
                      <span className="size-3 rounded-[3px]" style={{ background: d.status ? tone(d.status).dot : "var(--offline)" }} />
                      <span>
                        <span className="block text-[13px] font-semibold">{d.kota}</span>
                        <span className="block text-[11px] text-muted">{d.n_truk_aktif} truk aktif</span>
                      </span>
                    </span>
                    {d.status && <StatusPill status={d.status} />}
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Truk perlu perhatian">
            {!truk.data ? (
              <Muat tinggi={200} />
            ) : perhatian.length === 0 ? (
              <Kosong>Tidak ada truk berstatus kritis, waspada, atau offline.</Kosong>
            ) : (
              <ul className="flex flex-col divide-y">
                {perhatian.map((t) => {
                  const ttb = t.kondisi?.time_to_breach_min;
                  const b = t.bacaan_terakhir;
                  return (
                    <li key={t.truck_id} className="flex items-center justify-between gap-2 py-2.5">
                      <Link href={trukPath(t.truck_id)} className="min-w-0 hover:underline">
                        <span className="block text-[13px] font-semibold">{t.truck_id}</span>
                        <span className="block truncate text-[11px] text-muted">
                          {muatan(t.trip?.profil?.id)} · {t.depot.kota}
                          {b?.lat != null && b?.lon != null && ` · ${b.lat.toFixed(2)}, ${b.lon.toFixed(2)}`}
                          {ttb != null && ` · TTB ${Math.round(ttb)} mnt`}
                        </span>
                      </Link>
                      <StatusPill status={t.status} />
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
