"use client";

import Link from "next/link";
import { CheckCircle, Info, ShieldCheck, Truck, Warning, XCircle } from "@phosphor-icons/react/dist/ssr";
import { PageHeader } from "@/components/fleet/notifications";
import { Bar, Card, Galat, Kpi, Muat, StatusPill } from "@/components/fleet/ui";
import { FleetMap, LegendaPeta } from "@/components/fleet/map-legend";
import { trukPath } from "@/lib/fleet-api";
import { DataKerugian, Peta, Ringkasan, Truk } from "@/lib/fleet-types";
import { FLEET_TONE, muatan } from "@/lib/fleet-status";
import { persen, rupiah } from "@/lib/format";
import { KELAS_V3, diagnosisText } from "@/lib/labels";
import { useFleet } from "@/lib/use-fleet";
import { cn } from "@/lib/utils";

const BAR_STATUS = ["KRITIS", "WASPADA", "AMAN", "DATA_TIDAK_LENGKAP", "MENUNGGU_DATA", "TIDAK_ADA_DATA"] as const;

export default function RingkasanPage() {
  const s = useFleet<Ringkasan>("/api/v1/fleet/summary");
  const truk = useFleet<Truk[]>("/api/v1/fleet/trucks");
  const peta = useFleet<Peta>("/api/v1/fleet/map");
  const rugi = useFleet<DataKerugian>("/api/v1/fleet/losses?jam=720");

  const r = s.data;
  const offline = r?.per_status.TIDAK_ADA_DATA ?? 0;
  const aktif = r?.n_trip_aktif ?? 0;

  return (
    <>
      <PageHeader title="Ringkasan armada" subtitle={`Kondisi ${r?.n_truk ?? "…"} truk berpendingin secara real-time`} />
      {s.error && <Galat pesan={s.error} onRetry={s.reload} />}
      {!r ? (
        !s.error && <Muat tinggi={140} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Kpi label="Total armada" value={r.n_truk} icon={Truck} note={`${r.n_truk - offline} online · ${offline} offline`} />
          <Kpi label="Kritis" value={r.per_status.KRITIS} icon={XCircle} tone="crit" note="Perlu tindakan sekarang" />
          <Kpi label="Waspada" value={r.per_status.WASPADA} icon={Warning} tone="warn" note="Pantau dan verifikasi" />
          <Kpi
            label="Kerugian berhasil diatasi" icon={ShieldCheck} tone="ok"
            value={rugi.data ? rupiah(rugi.data.ringkasan.berhasil_diatasi_idr) : "…"}
            note={rugi.data ? `30 hari terakhir · ${rugi.data.ringkasan.n_diatasi} insiden tanpa breach` : undefined}
          />
        </div>
      )}

      {r && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Card title="Truk kritis vs tidak kritis">
            <div className="flex gap-10">
              <div>
                <p className="num text-[36px] font-bold leading-none text-crit">{r.kritis_vs_tidak.kritis}</p>
                <p className="mt-1 text-[12px] text-muted">Kritis ({persen(r.kritis_vs_tidak.kritis, aktif)})</p>
              </div>
              <div>
                <p className="num text-[36px] font-bold leading-none text-ok">{r.kritis_vs_tidak.tidak_kritis}</p>
                <p className="mt-1 text-[12px] text-muted">Tidak kritis ({persen(r.kritis_vs_tidak.tidak_kritis, aktif)})</p>
              </div>
            </div>
            <div className="mt-5 flex h-3 overflow-hidden rounded-full bg-[#e9edf5]" role="img" aria-label="Komposisi status armada">
              {BAR_STATUS.map((st) =>
                r.per_status[st] ? (
                  <div key={st} style={{ width: `${(r.per_status[st] / Math.max(1, r.n_truk)) * 100}%`, background: FLEET_TONE[st].dot }} />
                ) : null
              )}
            </div>
            <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-muted">
              {BAR_STATUS.filter((st) => r.per_status[st]).map((st) => (
                <li key={st} className="flex items-center gap-1.5">
                  <span className="size-2 rounded-full" style={{ background: FLEET_TONE[st].dot }} />
                  {FLEET_TONE[st].short} <span className="num">{r.per_status[st]}</span>
                </li>
              ))}
            </ul>
          </Card>
          <Card title="Truk per diagnosis">
            <ul className="flex flex-col gap-2.5">
              {KELAS_V3.map((k) => {
                const n = r.per_diagnosis[k] ?? 0;
                const max = Math.max(1, ...Object.values(r.per_diagnosis));
                return (
                  <li key={k} className="grid grid-cols-[150px_1fr_24px] items-center gap-3 text-[13px]">
                    <span className="truncate">{diagnosisText(k)}</span>
                    <Bar value={n} max={max} className="h-2" />
                    <span className="num text-right font-semibold">{n}</span>
                  </li>
                );
              })}
            </ul>
            {Object.keys(r.per_diagnosis).some((k) => !KELAS_V3.includes(k)) && (
              <p className="mt-3 text-[11px] text-muted">
                Label aturan (mis. {Object.keys(r.per_diagnosis).filter((k) => !KELAS_V3.includes(k)).map(diagnosisText).join(", ")}) tidak termasuk 7 kelas model.
              </p>
            )}
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.7fr_1fr]">
        <Card title="Armada diurutkan menurut risiko" aside={<Link href="/kondisi" className="text-[13px] font-medium text-accent hover:underline">Lihat semua →</Link>}>
          {truk.error && <Galat pesan={truk.error} onRetry={truk.reload} />}
          {!truk.data ? (
            !truk.error && <Muat tinggi={280} />
          ) : (
            <div className="-mx-5 overflow-x-auto px-5">
              <table className="w-full min-w-[560px] text-left text-[13px]">
                <thead className="text-[11px] uppercase tracking-[0.04em] text-muted">
                  <tr className="border-b">
                    <th className="py-2 font-medium">Truk</th>
                    <th className="py-2 font-medium">Muatan</th>
                    <th className="py-2 font-medium">Status</th>
                    <th className="py-2 font-medium">TTB</th>
                    <th className="py-2 font-medium">Diagnosis</th>
                  </tr>
                </thead>
                <tbody>
                  {truk.data.slice(0, 8).map((t) => {
                    const ttb = t.kondisi?.time_to_breach_min;
                    const fm = t.kondisi?.failure_mode;
                    return (
                      <tr key={t.truck_id} className="border-b last:border-0">
                        <td className="py-2.5 font-semibold"><Link href={trukPath(t.truck_id)} className="hover:underline">{t.truck_id}</Link></td>
                        <td className="py-2.5">{muatan(t.trip?.profil?.id)}</td>
                        <td className="py-2.5"><StatusPill status={t.status} /></td>
                        <td className={cn("num py-2.5", t.status === "KRITIS" && "font-semibold text-crit")}>{ttb != null ? `${Math.round(ttb)} mnt` : "—"}</td>
                        <td className="py-2.5">
                          <span className="inline-flex items-center gap-1">
                            {t.status === "TIDAK_ADA_DATA" ? "Tidak ada data" : fm ? diagnosisText(fm.label) : "—"}
                            {t.kondisi?.data_lengkap === false && fm && (
                              <span title="Data tidak lengkap" aria-label="Data tidak lengkap" className="text-muted"><Info size={14} aria-hidden /></span>
                            )}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <Card title="Posisi armada">
          <div className="h-[260px]">{peta.data ? <FleetMap peta={peta.data} mini /> : <Muat tinggi={260} />}</div>
          <LegendaPeta />
        </Card>
      </div>
      {r && r.per_status.AMAN === r.n_truk && (
        <p className="flex items-center gap-2 text-[13px] text-ok"><CheckCircle size={16} aria-hidden /> Semua truk aman.</p>
      )}
    </>
  );
}
