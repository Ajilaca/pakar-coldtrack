"use client";

// Panel kondisi satu truk dari API armada: dipakai halaman Kondisi (kanan) dan Detail truk.

import { Riwayat, TrukDetail } from "@/lib/fleet-types";
import { muatan } from "@/lib/fleet-status";
import { useFleet } from "@/lib/use-fleet";
import { FaktorCard, StatusBanner, SuhuChart, TindakanCard } from "./condition";
import { Galat, Muat } from "./ui";

export function useTruk(truckId: string | null) {
  const key = truckId ? encodeURIComponent(truckId.replace(/\s+/g, "")) : null;
  const detail = useFleet<TrukDetail>(key ? `/api/v1/fleet/trucks/${key}` : null);
  const riwayat = useFleet<Riwayat>(key ? `/api/v1/fleet/trucks/${key}/history?menit=120` : null);
  return { detail, riwayat };
}

export function Banner({ t }: { t: TrukDetail }) {
  const fm = t.kondisi?.failure_mode;
  const catatan = t.status === "TIDAK_ADA_DATA" || t.status === "MENUNGGU_DATA" || t.kondisi?.data_lengkap === false
    ? t.kondisi?.catatan_data
    : null;
  return (
    <StatusBanner
      status={t.status}
      subjudul={`${t.truck_id} · ${muatan(t.trip?.profil?.id)}`}
      ttb={t.kondisi?.time_to_breach_min}
      label={fm?.label}
      confidence={fm?.confidence}
      dataLengkap={t.kondisi?.data_lengkap}
      catatan={catatan}
    />
  );
}

/** Banner + grafik + faktor + tindakan (frame Kondisi, kolom kanan). */
export function TruckPanel({ truckId }: { truckId: string }) {
  const { detail, riwayat } = useTruk(truckId);
  if (detail.error) return <Galat pesan={detail.error} onRetry={detail.reload} />;
  const t = detail.data;
  if (!t) return <Muat tinggi={520} />;
  return (
    <div className="flex flex-col gap-4">
      <Banner t={t} />
      <SuhuChart riwayat={riwayat.data} tHi={t.trip?.profil?.t_hi} />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <FaktorCard drivers={t.drivers} />
        <TindakanCard actions={t.actions} />
      </div>
    </div>
  );
}
