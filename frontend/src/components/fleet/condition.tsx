"use client";

// Komponen kondisi satu truk (frame Kondisi / Detail truk / Simulasi): banner status, grafik suhu kargo
// aktual + prediksi (+15/+30/+60, kontrak model), 3 faktor pendorong, tindakan yang disarankan.

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { WarningCircle } from "@phosphor-icons/react/dist/ssr";
import { ActionStep, Driver } from "@/lib/types";
import { Riwayat } from "@/lib/fleet-types";
import { tone } from "@/lib/fleet-status";
import { driverText, diagnosisText, visibleDrivers } from "@/lib/labels";
import { suhu } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Bar, Card } from "./ui";

export function StatusBanner({ status, subjudul, ttb, label, confidence, dataLengkap, catatan }: {
  status: string; subjudul: string; ttb: number | null | undefined; label: string | null | undefined;
  confidence: number | null | undefined; dataLengkap?: boolean | null; catatan?: string | null;
}) {
  const t = tone(status);
  const pct = Math.round((confidence ?? 0) * 100);
  const adaModel = !["TIDAK_ADA_DATA", "MENUNGGU_DATA", "TANPA_TRIP"].includes(status);
  const ttbTeks = !adaModel ? "—" : ttb == null ? "60+" : String(Math.max(0, Math.round(ttb)));
  return (
    <section className={cn("rounded-2xl p-5 text-white", t.banner)}>
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-[1.1fr_auto_0.9fr_auto_1.4fr] sm:items-center">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-white/80">Status perjalanan</p>
          <p className="mt-1 flex items-center gap-2 text-[30px] font-bold leading-tight lg:text-[34px]">
            <t.Icon size={32} weight="bold" aria-hidden />
            {t.word}
          </p>
          <p className="text-[12px] text-white/85">{subjudul}</p>
        </div>
        <div className="hidden h-16 w-px bg-white/30 sm:block" aria-hidden />
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-white/80">Time-to-breach</p>
          <p className="mt-1">
            <span className="num text-[34px] font-bold leading-none">{ttbTeks}</span>{" "}
            {adaModel && <span className="text-[14px]">menit</span>}
          </p>
          <p className="text-[12px] text-white/85">{adaModel ? "Sisa waktu sebelum ambang" : "Tidak dapat dinilai"}</p>
        </div>
        <div className="hidden h-16 w-px bg-white/30 sm:block" aria-hidden />
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-white/80">Diagnosis penyebab</p>
          <p className="mt-1 text-[18px] font-semibold">{adaModel ? diagnosisText(label) : "Belum tersedia"}</p>
          {adaModel && (
            <>
              {/* data tidak lengkap (Figma): bar keyakinan diredupkan + catatan di dalam banner */}
              <div className={cn("mt-2 h-1.5 overflow-hidden rounded-full", dataLengkap === false ? "bg-white" : "bg-white/25")} aria-hidden>
                <div className={cn("h-full rounded-full", dataLengkap === false ? "bg-slate-500" : "bg-white")} style={{ width: `${pct}%` }} />
              </div>
              <p className="mt-1 text-[12px] text-white/85">Keyakinan model <span className="num">{pct}%</span></p>
              {dataLengkap === false && (
                <p className="mt-1 flex items-center gap-1.5 text-[12px] text-white/90" title={catatan ?? undefined}>
                  <span className="size-3 rounded-full border-[1.5px] border-white/90" aria-hidden />
                  Diagnosis kurang andal · data tidak lengkap
                </p>
              )}
            </>
          )}
        </div>
      </div>
      {catatan && dataLengkap !== false && (
        <p className="mt-4 flex items-start gap-2 rounded-lg bg-black/15 px-3 py-2 text-[12px]">
          <WarningCircle size={16} className="mt-px shrink-0" aria-hidden />
          {catatan}
        </p>
      )}
    </section>
  );
}

const HORIZON = [15, 30, 60];

export function SuhuChart({ riwayat, tHi }: { riwayat: Riwayat | null; tHi: number | null | undefined }) {
  const akt = riwayat?.aktual ?? [];
  if (akt.length === 0) {
    return (
      <Card title="Suhu kargo: aktual dan prediksi">
        <p className="py-16 text-center text-[13px] text-muted">Belum ada bacaan pada trip ini.</p>
      </Card>
    );
  }
  const akhir = new Date(akt[akt.length - 1].ts).getTime();
  const menit = (ts: string) => Math.round((new Date(ts).getTime() - akhir) / 60000);
  // grid per menit -60..0: menit tanpa bacaan = null sehingga garis terputus (data tidak lengkap terlihat)
  const peta = new Map(akt.map((r) => [menit(r.ts), r.temp_c]));
  const data: { t: number; aktual?: number | null; prediksi?: number }[] = [];
  for (let m = -60; m <= 0; m++) data.push({ t: m, aktual: peta.has(m) ? peta.get(m)! : null });
  const garis = riwayat?.garis_prediksi;
  if (garis) {
    data[data.length - 1].prediksi = akt[akt.length - 1].temp_c;
    for (const g of garis) data.push({ t: g.horizon_min, prediksi: g.temp_c });
  }
  const nilai = [...data.flatMap((d) => [d.aktual, d.prediksi]).filter((v): v is number => v != null), ...(tHi != null ? [tHi] : [])];
  const lo = Math.floor(Math.min(...nilai) - 1);
  const hi = Math.ceil(Math.max(...nilai) + 1);
  // menit hilang dihitung sejak bacaan pertama (trip yang baru mulai tidak dianggap berlubang)
  const awal = Math.max(-60, Math.min(...Array.from(peta.keys())));
  const hilang = data.filter((d) => d.t >= awal && d.t <= 0 && d.aktual == null).length;
  const ringkas = `Suhu kargo terakhir ${suhu(akt[akt.length - 1].temp_c)}${garis ? `; prediksi ${garis.map((g) => `+${g.horizon_min} menit ${suhu(g.temp_c)}`).join(", ")}` : ""}${tHi != null ? `; ambang ${suhu(tHi)}` : ""}.`;

  return (
    <Card
      title="Suhu kargo: aktual dan prediksi"
      aside={
        <ul className="flex gap-4 text-[12px] text-muted">
          <li className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-[var(--chart-actual)]" />Aktual</li>
          <li className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-[var(--chart-forecast)]" />Prediksi T+15/30/60</li>
        </ul>
      }
    >
      <p className="sr-only">{ringkas}</p>
      <div className="h-[240px] w-full" aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#edf0f5" vertical={false} />
            <XAxis
              dataKey="t" type="number" domain={[-60, 60]} ticks={[-60, -30, 0, 15, 30, 60]}
              tickFormatter={(v: number) => (v === 0 ? "Sekarang" : v === -60 ? "−60 mnt" : v < 0 ? `−${-v}` : `+${v}`)}
              tick={{ fontSize: 11, fill: "var(--text-muted)" }} stroke="#e2e8f0"
            />
            <YAxis domain={[lo, hi]} width={52} tickFormatter={(v: number) => `${v} °C`} tick={{ fontSize: 11, fill: "var(--text-muted)" }} stroke="#e2e8f0" />
            {tHi != null && (
              <ReferenceLine
                y={tHi} stroke="var(--chart-forecast)" strokeWidth={1.5}
                label={{ value: `Ambang ${tHi} °C`, position: "insideTopLeft", fontSize: 11, fill: "var(--chart-forecast)", fontWeight: 600 }}
              />
            )}
            <ReferenceLine x={0} stroke="#94a3b8" />
            <Tooltip
              contentStyle={{ borderRadius: 8, border: "1px solid var(--border)", fontSize: 12 }}
              labelFormatter={(v) => (Number(v) === 0 ? "Sekarang" : `${Number(v) > 0 ? "+" : ""}${v} menit`)}
              formatter={(v, name) => [suhu(Number(v)), name === "aktual" ? "Aktual" : "Prediksi"]}
            />
            <Line dataKey="aktual" stroke="var(--chart-actual)" strokeWidth={2.5} dot={false} connectNulls={false} isAnimationActive={false} />
            <Line dataKey="prediksi" stroke="var(--chart-forecast)" strokeWidth={2} strokeDasharray="6 5" dot={{ r: 3, strokeWidth: 0, fill: "var(--chart-forecast)" }} connectNulls isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      {hilang > 0 && (
        <p className="mt-2 text-[12px] text-muted">
          Garis terputus: <span className="num">{hilang}</span> menit tanpa bacaan dalam 60 menit terakhir.
        </p>
      )}
      {!garis && <p className="mt-2 text-[12px] text-muted">Prediksi belum tersedia (model butuh 60 menit data).</p>}
      <p className="sr-only">Horizon prediksi: {HORIZON.join(", ")} menit.</p>
    </Card>
  );
}

export function FaktorCard({ drivers }: { drivers: Driver[] }) {
  const top = visibleDrivers(drivers).slice(0, 3);
  return (
    <Card title="3 faktor pendorong utama">
      {top.length === 0 ? (
        <p className="text-[13px] text-muted">Belum ada data.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {top.map((d) => (
            <li key={d.feature}>
              <div className="flex justify-between text-[13px]">
                <span>{driverText(d.feature)}</span>
                <span className="num font-semibold">{Math.round(d.contribution * 100)}%</span>
              </div>
              <Bar value={d.contribution} className="mt-1.5 h-2" />
            </li>
          ))}
        </ul>
      )}
      <p className="mt-4 text-[11px] text-muted">Atribusi heuristik, bukan SHAP.</p>
    </Card>
  );
}

export function TindakanCard({ actions }: { actions: ActionStep[] }) {
  const urut = [...actions].sort((a, b) => a.priority - b.priority);
  return (
    <Card title="Tindakan yang disarankan">
      {urut.length === 0 ? (
        <p className="text-[13px] text-muted">Tidak ada tindakan selama status belum dapat dinilai.</p>
      ) : (
        <ol className="flex flex-col gap-3">
          {urut.map((a, i) => (
            <li key={a.priority} className="flex gap-3">
              <span className="num flex size-7 shrink-0 items-center justify-center rounded-full bg-[var(--chart-actual)] text-[13px] font-bold text-white">{a.priority}</span>
              <div>
                <p className="text-[13px] font-medium">{a.text}</p>
                <p className="text-[12px] text-muted">
                  {i === 0 ? "Sekarang" : ""}
                  {a.eta_min != null && a.eta_min > 0 ? `${i === 0 ? " · " : ""}±${a.eta_min} mnt` : i === 0 ? "" : "Setelah stabil"}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
