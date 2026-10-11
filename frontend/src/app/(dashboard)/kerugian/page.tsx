"use client";

import Link from "next/link";
import { useState } from "react";
import { Clock, ShieldCheck, Warning, XCircle } from "@phosphor-icons/react/dist/ssr";
import { PageHeader } from "@/components/fleet/notifications";
import { Card, Galat, Kosong, Kpi, Muat } from "@/components/fleet/ui";
import { trukPath } from "@/lib/fleet-api";
import { DataKerugian, Insiden } from "@/lib/fleet-types";
import { angka, rupiah, tanggalJam } from "@/lib/format";
import { diagnosisText } from "@/lib/labels";
import { useFleet } from "@/lib/use-fleet";
import { cn } from "@/lib/utils";

const RENTANG = [
  { jam: 24, label: "24 jam" },
  { jam: 24 * 7, label: "7 hari" },
  { jam: 24 * 30, label: "30 hari" },
];

const HASIL = {
  breach: { teks: "Breach", cls: "bg-crit-soft text-crit" },
  diatasi: { teks: "Diatasi", cls: "bg-ok-soft text-ok" },
  terbuka: { teks: "Terbuka", cls: "bg-warn-soft text-warn" },
  ditutup: { teks: "Ditutup", cls: "bg-offline-soft text-offline" },
};

export default function KerugianPage() {
  const [jam, setJam] = useState(24 * 30);
  const k = useFleet<DataKerugian>(`/api/v1/fleet/losses?jam=${jam}`);
  const ins = useFleet<Insiden[]>("/api/v1/incidents?jenis=kondisi&limit=500");
  const r = k.data?.ringkasan;
  const leads = (k.data?.insiden ?? []).map((x) => x.lead_time_min).filter((x): x is number => x != null);
  const rataLead = leads.length ? leads.reduce((a, b) => a + b, 0) / leads.length : null;

  // kerugian per jenis masalah: label insiden dari /incidents, nilai dari /fleet/losses
  const label = new Map((ins.data ?? []).map((i) => [i.id, i.failure_label]));
  const perJenis = new Map<string, { terjadi: number; diatasi: number; n: number }>();
  for (const x of k.data?.insiden ?? []) {
    const l = label.get(x.incident_id) ?? "tidak_diketahui";
    const v = perJenis.get(l) ?? { terjadi: 0, diatasi: 0, n: 0 };
    perJenis.set(l, { terjadi: v.terjadi + x.kerugian_terjadi_idr, diatasi: v.diatasi + x.berhasil_diatasi_idr, n: v.n + 1 });
  }
  const jenis = Array.from(perJenis.entries()).sort((a, b) => b[1].terjadi + b[1].diatasi - (a[1].terjadi + a[1].diatasi));
  const maxJenis = Math.max(1, ...jenis.map(([, v]) => v.terjadi + v.diatasi));

  return (
    <>
      <PageHeader title="Estimasi kerugian" subtitle="Nilai muatan berisiko, kerugian yang terjadi, dan yang berhasil diatasi" />
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Rentang waktu">
        {RENTANG.map((x) => (
          <button
            key={x.jam} type="button" aria-pressed={jam === x.jam} onClick={() => setJam(x.jam)}
            className={cn("rounded-full border px-3 py-1 text-[12px] font-medium", jam === x.jam ? "border-[var(--chart-actual)] bg-[var(--chart-actual)] text-white" : "bg-surface hover:bg-surface-muted")}
          >
            {x.label}
          </button>
        ))}
      </div>
      {k.error && <Galat pesan={k.error} onRetry={k.reload} />}
      {!r ? (
        !k.error && <Muat tinggi={140} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Kpi label="Nilai berisiko" value={rupiah(r.nilai_berisiko_idr)} icon={Warning} tone="warn" note="Muatan × indeks risiko, insiden terbuka" />
          <Kpi label="Kerugian terjadi" value={rupiah(r.kerugian_terjadi_idr)} icon={XCircle} tone="crit" note={`${r.n_breach} insiden melewati ambang`} />
          <Kpi label="Berhasil diatasi" value={rupiah(r.berhasil_diatasi_idr)} icon={ShieldCheck} tone="ok" note={`${r.n_diatasi} insiden selesai sebelum breach`} />
          <Kpi
            label="Rata-rata lead time" icon={Clock}
            value={rataLead == null ? "—" : `${angka(rataLead)} mnt`}
            note={rataLead == null ? "Belum ada breach pada rentang ini" : `Deteksi → breach · median ${angka(r.lead_time_median_min ?? 0)} mnt`}
          />
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_1.2fr_1fr]">
        <Card title="Kerugian per jenis masalah">
          {!k.data ? (
            <Muat tinggi={220} />
          ) : jenis.length === 0 ? (
            <Kosong>Tidak ada insiden pada rentang ini.</Kosong>
          ) : (
            <ul className="flex flex-col gap-3">
              {jenis.map(([l, v]) => (
                <li key={l}>
                  <div className="flex justify-between text-[13px]">
                    <span>{l === "tidak_diketahui" ? "Tanpa label" : diagnosisText(l)} <span className="text-muted">({v.n})</span></span>
                    <span className="num font-semibold">{rupiah(v.terjadi + v.diatasi)}</span>
                  </div>
                  <div className="mt-1.5 flex h-2 overflow-hidden rounded-full bg-[#e9edf5]" aria-hidden>
                    <div style={{ width: `${(v.terjadi / maxJenis) * 100}%`, background: "var(--crit)" }} />
                    <div style={{ width: `${(v.diatasi / maxJenis) * 100}%`, background: "var(--ok)" }} />
                  </div>
                </li>
              ))}
              <li className="flex gap-4 text-[11px] text-muted">
                <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-crit" />Terjadi</span>
                <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-ok" />Diatasi</span>
              </li>
            </ul>
          )}
        </Card>
        <Card title="Insiden terbaru">
          {!k.data ? (
            <Muat tinggi={220} />
          ) : k.data.insiden.length === 0 ? (
            <Kosong>Belum ada insiden.</Kosong>
          ) : (
            <ul className="flex max-h-[360px] flex-col divide-y overflow-y-auto">
              {k.data.insiden.slice(0, 30).map((x) => (
                <li key={x.incident_id} className="flex items-center justify-between gap-2 py-2">
                  <Link href={trukPath(x.truck_id)} className="min-w-0 hover:underline">
                    <span className="block text-[13px] font-semibold">{x.truck_id}</span>
                    <span className="block text-[11px] text-muted">
                      {tanggalJam(x.detected_at)}
                      {x.lead_time_min != null && ` · lead time ${angka(x.lead_time_min)} mnt`}
                    </span>
                  </Link>
                  <span className="flex items-center gap-2">
                    <span className="num text-[12px]">{rupiah(x.kerugian_terjadi_idr || x.berhasil_diatasi_idr || x.nilai_berisiko_idr || x.nilai_muatan_idr)}</span>
                    <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", HASIL[x.hasil].cls)}>{HASIL[x.hasil].teks}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Cara menghitung">
          <dl className="flex flex-col gap-3 text-[12px]">
            <div><dt className="font-semibold">Nilai berisiko</dt><dd className="text-muted">Nilai muatan × indeks risiko saat ini, untuk insiden yang masih terbuka tanpa breach.</dd></div>
            <div><dt className="font-semibold">Kerugian terjadi</dt><dd className="text-muted">Nilai muatan penuh bila suhu muatan (estimasi) melewati batas. Ini batas atas; sebagian muatan mungkin masih dapat diselamatkan.</dd></div>
            <div><dt className="font-semibold">Berhasil diatasi</dt><dd className="text-muted">Nilai muatan insiden yang selesai atau kembali AMAN sebelum breach. Tidak membuktikan tindakan operator yang mencegahnya.</dd></div>
            <div><dt className="font-semibold">Lead time</dt><dd className="text-muted">Waktu dari deteksi sampai breach. 0 berarti terdeteksi saat sudah melewati batas.</dd></div>
            <div><dt className="font-semibold">Nilai muatan</dt><dd className="text-muted">Massa × harga per kg [ASUMSI] (docs/fleet_assumptions.md), bukan harga pasar resmi.</dd></div>
          </dl>
        </Card>
      </div>
    </>
  );
}
