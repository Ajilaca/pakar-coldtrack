"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Clock, UserCircle } from "@phosphor-icons/react/dist/ssr";
import { PageHeader } from "@/components/fleet/notifications";
import { Card, Galat, Muat } from "@/components/fleet/ui";
import { patchInsiden, trukPath } from "@/lib/fleet-api";
import { EventInsiden, Insiden, Phase } from "@/lib/fleet-types";
import { jam, rupiah } from "@/lib/format";
import { diagnosisText } from "@/lib/labels";
import { useFleet, useFleetCtx } from "@/lib/use-fleet";
import { cn } from "@/lib/utils";

const KOLOM: { phase: Phase; judul: string; oleh: string; dot: string }[] = [
  { phase: "TERDETEKSI", judul: "Terdeteksi", oleh: "Diisi sistem", dot: "var(--warn)" },
  { phase: "DITUGASKAN", judul: "Ditugaskan", oleh: "Diubah operator", dot: "var(--chart-actual)" },
  { phase: "DITANGANI", judul: "Ditangani", oleh: "Diubah operator", dot: "var(--chart-actual)" },
  { phase: "SELESAI", judul: "Selesai", oleh: "Diubah operator", dot: "var(--ok)" },
  { phase: "GAGAL", judul: "Gagal", oleh: "Diisi sistem", dot: "var(--crit)" },
];
const BATAS_KOLOM = 12;              // per kolom: insiden terbaru saja (insiden trip lama bisa menumpuk)
const KUNCI_NAMA = "coldtrack.operator";

export default function TindakanPage() {
  const ins = useFleet<Insiden[]>("/api/v1/incidents?jenis=kondisi&limit=300");
  const ev = useFleet<EventInsiden[]>("/api/v1/incidents/events?limit=15");
  const { refresh } = useFleetCtx();
  const [operator, setOperator] = useState("");
  const [galat, setGalat] = useState<string | null>(null);

  useEffect(() => {
    try {
      setOperator(localStorage.getItem(KUNCI_NAMA) ?? "");
    } catch {}
  }, []);
  const simpanNama = (v: string) => {
    setOperator(v);
    try {
      localStorage.setItem(KUNCI_NAMA, v);
    } catch {}
  };

  async function ubah(i: Insiden, body: { phase?: string; assignee?: string; note?: string }) {
    if (!operator.trim()) {
      setGalat("Isi nama operator dulu; setiap perubahan fase dicatat di audit trail.");
      return;
    }
    setGalat(null);
    try {
      await patchInsiden(i.id, { ...body, actor: operator.trim() });
      ins.reload();
      ev.reload();
      refresh();
    } catch (e) {
      setGalat(e instanceof Error ? e.message : "Gagal mengubah insiden.");
    }
  }

  return (
    <>
      <PageHeader title="Tindakan" subtitle="Alur penanganan insiden kondisi muatan" />
      <div className="flex flex-col gap-3 rounded-2xl border bg-[#f3f6ff] px-4 py-3 text-[13px] sm:flex-row sm:items-center sm:justify-between">
        <p className="flex items-center gap-2 text-[#2b3f87]">
          <UserCircle size={18} aria-hidden />
          Hanya fase Terdeteksi dan Gagal diisi otomatis oleh sistem. Fase lain diubah operator dan tercatat di audit trail.
        </p>
        <label className="flex items-center gap-2">
          <span className="whitespace-nowrap text-muted">Nama operator</span>
          <input
            value={operator} onChange={(e) => simpanNama(e.target.value)} placeholder="mis. Sari (dispatcher)"
            className="h-8 w-48 rounded-md border bg-surface px-2 text-[13px]" maxLength={120}
          />
        </label>
      </div>
      {galat && <p role="alert" className="rounded-xl bg-crit-soft px-4 py-2 text-[13px] text-crit">{galat}</p>}
      {ins.error && <Galat pesan={ins.error} onRetry={ins.reload} />}
      {!ins.data ? (
        !ins.error && <Muat tinggi={420} />
      ) : (
        <div className="-mx-4 overflow-x-auto px-4 pb-2">
          <div className="grid min-w-[1050px] grid-cols-5 gap-3">
            {KOLOM.map((k) => {
              let xs = ins.data!.filter((i) => i.phase === k.phase);
              const total = xs.length;
              xs = xs.slice(0, BATAS_KOLOM);
              return (
                <section key={k.phase} className="flex flex-col gap-2 rounded-2xl bg-[#eef1f6] p-3">
                  <div className="flex items-center justify-between">
                    <h2 className="flex items-center gap-2 text-[13px] font-semibold">
                      <span className="size-2 rounded-full" style={{ background: k.dot }} />
                      {k.judul}
                    </h2>
                    <span className="num rounded-full bg-surface px-2 text-[12px] font-semibold">{total}</span>
                  </div>
                  <p className="-mt-1 text-[11px] text-muted">{k.oleh}{total > xs.length && ` · ${xs.length} terbaru`}</p>
                  {xs.map((i) => <KartuInsiden key={i.id} i={i} onUbah={ubah} />)}
                </section>
              );
            })}
          </div>
        </div>
      )}
      <Card title="Riwayat perubahan fase (audit trail)">
        {!ev.data ? (
          <Muat tinggi={160} />
        ) : (
          <ul className="flex flex-col divide-y text-[13px]">
            {ev.data.map((e) => (
              <li key={e.id} className="grid grid-cols-[56px_140px_100px_1fr] gap-3 py-2.5 max-sm:grid-cols-[48px_1fr]">
                <span className="num text-muted">{jam(e.at)}</span>
                <span className="font-semibold">{e.actor}</span>
                <span className="font-semibold max-sm:col-start-2">{e.truck_id}</span>
                <span className="text-muted max-sm:col-start-2">
                  {e.from_phase === e.to_phase
                    ? e.note
                    : <>
                        {e.from_phase ? `${e.from_phase} → ${e.to_phase}` : `→ ${e.to_phase}`}
                        {e.to_phase === "GAGAL" && " (breach terjadi)"}
                      </>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}

function KartuInsiden({ i, onUbah }: { i: Insiden; onUbah: (i: Insiden, body: { phase?: string; assignee?: string; note?: string }) => Promise<void> }) {
  const [tugaskan, setTugaskan] = useState(false);
  const [nama, setNama] = useState("");
  const [sibuk, setSibuk] = useState(false);
  const jalan = async (body: { phase?: string; assignee?: string; note?: string }) => {
    setSibuk(true);
    await onUbah(i, body);
    setSibuk(false);
  };
  const ttb = i.ttb_now_min;
  const info =
    i.phase === "GAGAL" ? (
      <span className="text-crit">Kerugian {rupiah(i.loss?.kerugian_terjadi_idr ?? i.cargo_value_idr)}</span>
    ) : i.phase === "SELESAI" ? (
      i.loss?.berhasil_diatasi_idr ? <span className="text-ok">Diatasi {rupiah(i.loss.berhasil_diatasi_idr)}</span> : <span>Ditutup</span>
    ) : i.recovered_at ? (
      <span className="text-ok">Sudah kembali AMAN</span>
    ) : ttb != null ? (
      <span>TTB {Math.round(ttb)} mnt</span>
    ) : (
      <span>{i.failure_label === "masalah_sensor" ? "Verifikasi manual" : "Pantau"}</span>
    );
  const btn = "w-full rounded-lg bg-[#e8edfb] py-1.5 text-[12px] font-semibold text-[#2b3f87] hover:bg-[#dbe3fa] disabled:opacity-50";
  return (
    <article className="flex flex-col gap-1.5 rounded-xl border bg-surface p-3">
      <Link href={trukPath(i.truck_id)} className="text-[13px] font-bold hover:underline">{i.truck_id}</Link>
      <p className="text-[12px]">{diagnosisText(i.failure_label)}</p>
      <p className="flex items-center gap-1 text-[12px] text-muted"><Clock size={13} aria-hidden />{info}</p>
      <p className="border-t pt-1.5 text-[11px] text-muted">
        {i.phase === "GAGAL" && i.breach_at ? `Breach ${jam(i.breach_at)}` : i.assignee && i.phase !== "TERDETEKSI" ? i.assignee : i.last_event ? `${i.last_event.actor} · ${jam(i.last_event.at)}` : `Sistem · ${jam(i.detected_at)}`}
      </p>
      {i.phase === "TERDETEKSI" && (
        tugaskan ? (
          <form className="flex flex-col gap-1.5" onSubmit={(e) => { e.preventDefault(); if (nama.trim()) jalan({ phase: "DITUGASKAN", assignee: nama.trim() }); }}>
            <input autoFocus value={nama} onChange={(e) => setNama(e.target.value)} placeholder="Ditugaskan ke…" className="h-8 rounded-md border px-2 text-[12px]" maxLength={120} />
            <div className="flex gap-1.5">
              <button type="submit" disabled={sibuk || !nama.trim()} className={btn}>Simpan</button>
              <button type="button" onClick={() => setTugaskan(false)} className="w-full rounded-lg border py-1.5 text-[12px]">Batal</button>
            </div>
          </form>
        ) : (
          <button type="button" className={btn} onClick={() => setTugaskan(true)}>Tugaskan →</button>
        )
      )}
      {i.phase === "DITUGASKAN" && <button type="button" disabled={sibuk} className={btn} onClick={() => jalan({ phase: "DITANGANI" })}>Mulai tangani →</button>}
      {i.phase === "DITANGANI" && <button type="button" disabled={sibuk} className={cn(btn, "bg-ok-soft text-ok hover:bg-ok-soft")} onClick={() => jalan({ phase: "SELESAI" })}>Tandai selesai →</button>}
    </article>
  );
}
