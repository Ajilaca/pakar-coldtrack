"use client";

// Estimasi kerugian (frame Figma "Kerugian"). Semua nilai rupiah = massa x harga per kg [ASUMSI].

import Link from "next/link";
import { Clock, ShieldCheck, Warning, XCircle } from "@phosphor-icons/react/dist/ssr";
import { PageHeader } from "@/components/fleet/notifications";
import { Card, Galat, Kosong, Kpi, Muat } from "@/components/fleet/ui";
import { trukPath } from "@/lib/fleet-api";
import { DataKerugian, Phase } from "@/lib/fleet-types";
import { angka, rupiah } from "@/lib/format";
import { diagnosisText } from "@/lib/labels";
import { useFleet } from "@/lib/use-fleet";
import { cn } from "@/lib/utils";

const JAM = 24 * 30;
// Urutan jenis masalah mengikuti Figma; label lain yang muncul di data (mis. label aturan) ditambahkan di bawahnya.
const JENIS = ["pintu_terbuka_lama", "degradasi_bertahap", "kejutan_ambien_ekstrem", "masalah_sensor", "reefer_mati_total", "prapendinginan_buruk"];
const SERI = [
  { kunci: "berisiko", label: "Berisiko", warna: "#2b3f87" },
  { kunci: "terjadi", label: "Terjadi", warna: "#1c2a5c" },
  { kunci: "diatasi", label: "Berhasil diatasi", warna: "#64748b" },
] as const;
const FASE: Record<Phase, { teks: string; cls: string }> = {
  TERDETEKSI: { teks: "Terdeteksi", cls: "bg-warn-soft text-warn" },
  DITUGASKAN: { teks: "Ditugaskan", cls: "bg-[#e8edfb] text-[#2b3f87]" },
  DITANGANI: { teks: "Ditangani", cls: "bg-[#e8edfb] text-[#2b3f87]" },
  SELESAI: { teks: "Selesai", cls: "bg-ok-soft text-ok" },
  GAGAL: { teks: "Gagal", cls: "bg-crit-soft text-crit" },
};
const juta = (n: number) => Math.round(n / 1e6);

type Agg = { berisiko: number; terjadi: number; diatasi: number; leads: number[] };

export default function KerugianPage() {
  const k = useFleet<DataKerugian>(`/api/v1/fleet/losses?jam=${JAM}`);
  const r = k.data?.ringkasan;
  const ins = k.data?.insiden ?? [];

  const per = new Map<string, Agg>();
  for (const l of JENIS) per.set(l, { berisiko: 0, terjadi: 0, diatasi: 0, leads: [] });
  for (const x of ins) {
    const l = x.failure_label ?? "tidak_diketahui";
    const v = per.get(l) ?? { berisiko: 0, terjadi: 0, diatasi: 0, leads: [] };
    v.berisiko += x.nilai_berisiko_idr;
    v.terjadi += x.kerugian_terjadi_idr;
    v.diatasi += x.berhasil_diatasi_idr;
    if (x.lead_time_min != null) v.leads.push(x.lead_time_min);
    per.set(l, v);
  }
  const baris = Array.from(per.entries());
  const maks = Math.max(1, ...baris.flatMap(([, v]) => [v.berisiko, v.terjadi, v.diatasi]));

  return (
    <>
      <PageHeader title="Estimasi kerugian" subtitle="Nilai muatan berisiko, kerugian yang terjadi, dan yang berhasil diatasi" />
      {k.error && <Galat pesan={k.error} onRetry={k.reload} />}
      {!r ? (
        !k.error && <Muat tinggi={140} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Kpi label="Nilai berisiko" value={rupiah(r.nilai_berisiko_idr)} icon={Warning} tone="warn" note="Muatan × indeks risiko, 30 hari terakhir" />
          <Kpi label="Kerugian terjadi" value={rupiah(r.kerugian_terjadi_idr)} icon={XCircle} tone="crit" note={`${r.n_breach} insiden melewati ambang`} />
          <Kpi label="Berhasil diatasi" value={rupiah(r.berhasil_diatasi_idr)} icon={ShieldCheck} tone="ok" note={`${r.n_diatasi} insiden selesai sebelum breach`} />
          <Kpi label="Rata-rata lead time" icon={Clock} value={r.lead_time_rata_min == null ? "—" : `${angka(r.lead_time_rata_min)} mnt`} note="Deteksi → perkiraan breach" />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.45fr_1fr]">
        <Card
          title="Kerugian per jenis masalah (Rp juta)"
          aside={
            <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-muted">
              {SERI.map((s) => (
                <li key={s.kunci} className="flex items-center gap-1.5"><span className="size-2.5 rounded-full" style={{ background: s.warna }} />{s.label}</li>
              ))}
            </ul>
          }
        >
          {!k.data ? (
            <Muat tinggi={420} />
          ) : (
            <ul className="flex flex-col gap-5">
              {baris.map(([l, v]) => (
                <li key={l}>
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-[14px]">{l === "tidak_diketahui" ? "Tanpa label" : diagnosisText(l)}</span>
                    <span className="text-[12px] text-muted">
                      Lead time rata-rata {v.leads.length ? `${angka(v.leads.reduce((a, b) => a + b, 0) / v.leads.length)} mnt` : "—"}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-col gap-1.5">
                    {SERI.map((s) => (
                      <div key={s.kunci} className="grid grid-cols-[1fr_48px] items-center gap-3" title={`${s.label}: ${rupiah(v[s.kunci])}`}>
                        <div className="h-2 overflow-hidden rounded-full bg-[#e9edf5]">
                          <div className="h-full rounded-full" style={{ width: `${(v[s.kunci] / maks) * 100}%`, background: s.warna }} />
                        </div>
                        <span className="num text-[13px] font-semibold">{angka(juta(v[s.kunci]))}</span>
                      </div>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Cara menghitung">
          <dl className="flex flex-col gap-3 text-[13px]">
            <div><dt className="font-semibold">Nilai berisiko</dt><dd className="text-muted">Nilai muatan × risk index (insiden terbuka tanpa breach)</dd></div>
            <div><dt className="font-semibold">Kerugian terjadi</dt><dd className="text-muted">Nilai penuh muatan bila suhu melewati ambang (breach)</dd></div>
            <div><dt className="font-semibold">Berhasil diatasi</dt><dd className="text-muted">Insiden selesai sebelum breach, atau kembali AMAN tanpa breach</dd></div>
            <div><dt className="font-semibold">Lead time</dt><dd className="text-muted">Waktu perkiraan breach dikurangi waktu terdeteksi (TTB saat terdeteksi). Bila breach terjadi: waktu breach dikurangi waktu terdeteksi; 0 berarti terdeteksi saat sudah melewati batas.</dd></div>
          </dl>
          <p className="mt-4 text-[12px] text-muted">Harga per kg di sini adalah perkiraan, bukan harga dari data Anda. &quot;Berhasil diatasi&quot; berarti masalah selesai sebelum suhu melewati batas, belum tentu karena tindakan operator.</p>
        </Card>
      </div>

      <Card title="Insiden terbaru">
        {!k.data ? (
          <Muat tinggi={240} />
        ) : ins.length === 0 ? (
          <Kosong>Belum ada insiden dalam 30 hari terakhir.</Kosong>
        ) : (
          <div className="-mx-5 overflow-x-auto px-5">
            <table className="w-full min-w-[760px] text-left text-[14px]">
              <thead className="text-[11px] uppercase tracking-[0.04em] text-muted">
                <tr className="border-b">
                  <th className="py-2 font-medium">Truk</th>
                  <th className="py-2 font-medium">Masalah</th>
                  <th className="py-2 font-medium">Nilai muatan</th>
                  <th className="py-2 font-medium">Fase</th>
                  <th className="py-2 font-medium">Lead time</th>
                  <th className="py-2 font-medium">Hasil</th>
                </tr>
              </thead>
              <tbody>
                {ins.slice(0, 12).map((x) => (
                  <tr key={x.incident_id} className="border-b last:border-0">
                    <td className="py-3 font-semibold"><Link href={trukPath(x.truck_id)} className="hover:underline">{x.truck_id}</Link></td>
                    <td className="py-3">{diagnosisText(x.failure_label)}</td>
                    <td className="num py-3">{rupiah(x.nilai_muatan_idr)}</td>
                    <td className="py-3"><span className={cn("rounded-full px-2.5 py-1 text-[12px] font-semibold", FASE[x.phase].cls)}>{FASE[x.phase].teks}</span></td>
                    <td className="num py-3">{x.lead_time_min == null ? "—" : `${angka(x.lead_time_min)} mnt`}</td>
                    <td className="py-3">
                      {x.hasil === "breach" ? `Kerugian ${rupiah(x.kerugian_terjadi_idr)}` : x.hasil === "diatasi" ? `Diatasi ${rupiah(x.berhasil_diatasi_idr)}` : x.hasil === "terbuka" ? "Berlangsung" : "Ditutup"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  );
}
