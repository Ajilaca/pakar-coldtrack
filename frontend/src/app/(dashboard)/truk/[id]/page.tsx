"use client";

import Link from "next/link";
import { ArrowLeft, WarningCircle } from "@phosphor-icons/react/dist/ssr";
import { FaktorCard, SuhuChart, TindakanCard } from "@/components/fleet/condition";
import { PageHeader } from "@/components/fleet/notifications";
import { Banner, useTruk } from "@/components/fleet/truck-panel";
import { Card, Galat, Muat } from "@/components/fleet/ui";
import { TrukDetail } from "@/lib/fleet-types";
import { muatan, tone } from "@/lib/fleet-status";
import { angka, menitLalu, suhu } from "@/lib/format";
import { useFleetCtx } from "@/lib/use-fleet";

export default function DetailTrukPage({ params }: { params: { id: string } }) {
  const id = decodeURIComponent(params.id);
  const { detail, riwayat } = useTruk(id);
  const t = detail.data;
  const kembali = (
    <Link href="/kondisi" className="mb-1 inline-flex items-center gap-1 text-[12px] font-medium text-muted hover:text-ink">
      <ArrowLeft size={14} aria-hidden /> Kondisi armada
    </Link>
  );
  return (
    <>
      <PageHeader
        title={t?.truck_id ?? id}
        subtitle={t ? `Detail truk · ${muatan(t.trip?.profil?.id)} · ${t.depot.nama}` : "Detail truk"}
        back={kembali}
      />
      {detail.error && <Galat pesan={detail.error} onRetry={detail.reload} />}
      {!t ? (
        !detail.error && <Muat tinggi={600} />
      ) : (
        <>
          {t.kondisi?.data_lengkap === false && t.status !== "TIDAK_ADA_DATA" && t.status !== "MENUNGGU_DATA" && (
            <div role="status" className="flex items-start gap-3 rounded-2xl border border-l-[3px] border-l-warn bg-warn-soft p-4 text-[13px]">
              <WarningCircle size={20} className="mt-0.5 shrink-0 text-warn" aria-hidden />
              <div>
                <p className="font-semibold">Data tidak lengkap</p>
                <p className="text-muted">
                  {t.kondisi.catatan_data ?? "Ada bacaan yang hilang dalam 60 menit terakhir."} Keyakinan diagnosis dibatasi 50%.
                </p>
              </div>
            </div>
          )}
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1.6fr]">
            <PosisiSensor t={t} />
            <KondisiLangsung t={t} />
          </div>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.6fr_1fr]">
            <Banner t={t} />
            <FaktorCard drivers={t.drivers} />
          </div>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.6fr_1fr]">
            <SuhuChart riwayat={riwayat.data} tHi={t.trip?.profil?.t_hi} />
            <TindakanCard actions={t.actions} />
          </div>
        </>
      )}
    </>
  );
}

function PosisiSensor({ t }: { t: TrukDetail }) {
  const b = t.bacaan_terakhir;
  const warna = tone(t.status).dot;
  return (
    <Card title="Posisi sensor di kargo">
      <svg viewBox="0 0 320 130" className="mx-auto w-full max-w-[340px]" role="img" aria-label="Truk dengan satu sensor suhu kargo di tengah">
        <rect x="10" y="20" width="220" height="80" rx="8" fill="#eef2fb" stroke="#2b3f87" strokeWidth="3" />
        <path d="M232 45 h40 l26 26 v29 h-66 z" fill="#2b3f87" />
        <circle cx="60" cy="112" r="11" fill="#2b3f87" /><circle cx="180" cy="112" r="11" fill="#2b3f87" /><circle cx="270" cy="112" r="11" fill="#2b3f87" />
        <circle cx="120" cy="60" r="8" fill={warna} stroke="#fff" strokeWidth="3" />
      </svg>
      <ul className="mt-3 flex flex-col gap-1 text-[13px]">
        <li className="flex items-center justify-between">
          <span className="flex items-center gap-2"><span className="size-2.5 rounded-full" style={{ background: warna }} />Sensor kargo</span>
          <span className="num font-semibold">{suhu(b?.temp_c)}</span>
        </li>
      </ul>
      <p className="mt-2 text-[11px] text-muted">Logger saat ini satu sensor per truk; desain Figma menampilkan tiga posisi (depan/tengah/belakang).</p>
    </Card>
  );
}

function KondisiLangsung({ t }: { t: TrukDetail }) {
  const { now } = useFleetCtx();
  const b = t.bacaan_terakhir;
  const profil = t.trip?.profil;
  const dibuka = menitLalu(t.pintu_terakhir_dibuka, b?.ts ?? now);
  const d = t.ambien_delta_10m;
  const tile = (judul: string, nilai: string, catatan: string) => (
    <div key={judul} className="rounded-xl bg-surface-muted p-3">
      <p className="text-[12px] text-muted">{judul}</p>
      <p className="num mt-1 text-[20px] font-bold leading-tight">{nilai}</p>
      <p className="text-[11px] text-muted">{catatan}</p>
    </div>
  );
  return (
    <Card title="Kondisi langsung">
      {!b ? (
        <p className="text-[13px] text-muted">Belum ada bacaan.</p>
      ) : (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
          {tile("Suhu kargo", suhu(b.temp_c), profil?.t_hi != null ? `Ambang ${suhu(profil.t_hi, 0)}` : "—")}
          {tile("Suhu ambien", suhu(b.ambient_c), d == null ? "—" : `${d >= 0 ? "Naik" : "Turun"} ${angka(Math.abs(d), 1)} °C / 10 mnt`)}
          {tile("Kelembapan", `${angka(b.humidity)} %`, b.humidity > 90 ? "Tinggi" : "Normal")}
          {tile("Pintu kargo", b.door_open ? "Terbuka" : "Tertutup", dibuka == null ? "Tidak dibuka dalam 60 mnt" : b.door_open ? "Sedang terbuka" : `Terakhir dibuka ${dibuka} mnt lalu`)}
          {tile("Reefer", b.reefer_on ? "Menyala" : "Mati", t.setpoint_c != null ? `Setpoint ${suhu(t.setpoint_c, 0)}` : "Setpoint mengikuti profil")}
          {tile("Kecepatan", `${angka(b.speed_kmh)} km/jam`, b.speed_kmh < 1 ? "Berhenti" : "Bergerak")}
        </div>
      )}
    </Card>
  );
}
