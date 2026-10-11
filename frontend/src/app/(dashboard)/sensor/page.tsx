"use client";

import Link from "next/link";
import {
  ArrowsClockwise, BatteryWarning, CheckCircle, Pulse, Thermometer, Warning, WifiSlash, Wrench, XCircle,
} from "@phosphor-icons/react/dist/ssr";
import { PageHeader } from "@/components/fleet/notifications";
import { Bar, Card, Galat, Kpi, Muat } from "@/components/fleet/ui";
import { trukPath } from "@/lib/fleet-api";
import { DataSensor, Temuan } from "@/lib/fleet-types";
import { angka } from "@/lib/format";
import { useFleet } from "@/lib/use-fleet";
import { cn } from "@/lib/utils";

const GRADE: Record<string, { pill: string; bar: string }> = {
  Sehat: { pill: "bg-ok-soft text-ok", bar: "var(--ok)" },
  "Perlu cek": { pill: "bg-warn-soft text-warn", bar: "var(--warn)" },
  Ganti: { pill: "bg-crit-soft text-crit", bar: "var(--crit)" },
};

const GRUP: Record<string, { judul: string; Icon: typeof Wrench }> = {
  sensor: { judul: "Ganti sensor suhu", Icon: Thermometer },
  baterai: { judul: "Ganti baterai logger", Icon: BatteryWarning },
  kalibrasi: { judul: "Kalibrasi ulang", Icon: Wrench },
  offline_lama: { judul: "Perangkat offline lama", Icon: WifiSlash },
  firmware_usang: { judul: "Perbarui firmware", Icon: ArrowsClockwise },
  gateway_usang: { judul: "Perbarui agen gateway", Icon: ArrowsClockwise },
};

export default function SensorPage() {
  const s = useFleet<DataSensor>("/api/v1/fleet/sensors");
  const d = s.data;
  const skor = (d?.perangkat ?? []).map((p) => p.sensor_health?.score).filter((x): x is number => x != null);
  const rata = skor.length ? Math.round(skor.reduce((a, b) => a + b, 0) / skor.length) : null;
  const g = d?.per_grade ?? {};
  const urut = [...(d?.perangkat ?? [])].sort((a, b) => (a.sensor_health?.score ?? 101) - (b.sensor_health?.score ?? 101));

  return (
    <>
      <PageHeader title="Kesehatan sensor" subtitle="Health check logger suhu per truk dan perangkat yang perlu diperbarui" />
      {s.error && <Galat pesan={s.error} onRetry={s.reload} />}
      {!d ? (
        !s.error && <Muat tinggi={140} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <Kpi label="Skor rata-rata" value={rata == null ? "—" : <>{rata} <span className="text-[18px] text-muted">/ 100</span></>} icon={Pulse} note="Seluruh sensor yang sudah dinilai" />
          <Kpi label="Sehat" value={g["Sehat"] ?? 0} icon={CheckCircle} tone="ok" note="Tidak perlu tindakan" />
          <Kpi label="Perlu cek" value={g["Perlu cek"] ?? 0} icon={Warning} tone="warn" note="Verifikasi manual" />
          <Kpi label="Ganti" value={g["Ganti"] ?? 0} icon={XCircle} tone="crit" note={g["Data kurang"] ? `${g["Data kurang"]} perangkat datanya belum cukup` : "Jadwalkan penggantian"} />
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.8fr_1fr]">
        <Card title="Health check sensor per truk" aside={<span className="text-[12px] text-muted">Jendela 3 jam terakhir</span>}>
          {!d ? (
            <Muat tinggi={360} />
          ) : (
            <div className="-mx-5 overflow-x-auto px-5">
              <table className="w-full min-w-[600px] text-left text-[13px]">
                <thead className="text-[11px] uppercase tracking-[0.04em] text-muted">
                  <tr className="border-b">
                    <th className="py-2 font-medium">Truk</th>
                    <th className="py-2 font-medium">Skor</th>
                    <th className="py-2 font-medium">Grade</th>
                    <th className="py-2 font-medium">Alasan</th>
                    <th className="py-2 text-right font-medium">Baterai</th>
                  </tr>
                </thead>
                <tbody>
                  {urut.map((p) => {
                    const h = p.sensor_health;
                    const gr = GRADE[h?.grade ?? ""];
                    return (
                      <tr key={p.id} className="border-b last:border-0">
                        <td className="py-2.5 font-semibold"><Link href={trukPath(p.truck_id)} className="hover:underline">{p.truck_id}</Link></td>
                        <td className="py-2.5">
                          <span className="flex items-center gap-2">
                            <Bar value={h?.score ?? 0} max={100} color={gr?.bar ?? "var(--offline)"} className="w-14" />
                            <span className="num w-6">{h?.score ?? "—"}</span>
                          </span>
                        </td>
                        <td className="py-2.5">
                          <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", gr?.pill ?? "bg-offline-soft text-offline")}>{h?.grade ?? "Belum dinilai"}</span>
                        </td>
                        <td className="max-w-[280px] py-2.5 text-muted">{h?.alasan?.[0] ?? "—"}</td>
                        <td className={cn("num py-2.5 text-right", p.battery_v != null && p.battery_v < 2.6 && "font-semibold text-warn", p.battery_v != null && p.battery_v < 2.4 && "text-crit")}>
                          {p.battery_v != null ? `${angka(p.battery_v, 2)} V` : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <div className="flex flex-col gap-4">
          <Card title="Perlu diperbarui">{d ? <PerluDiperbarui temuan={d.perlu_diperbarui} /> : <Muat tinggi={260} />}</Card>
          <p className="rounded-2xl border bg-surface p-4 text-[12px] text-muted">
            Skor 0–100 dihitung dari penalti: menit curiga/rusak, flatline terpanjang, derau vs baseline Intel 0,073 °C,
            lompatan &gt; 5 °C, dan baterai. Bobot penalti bersifat desain, bukan hasil pelatihan. Model Berkeley belum
            lolos evaluasi (G4), jadi aturan v0 tetap dipakai.
          </p>
        </div>
      </div>
    </>
  );
}

function PerluDiperbarui({ temuan }: { temuan: Temuan[] }) {
  const grup = new Map<string, Temuan[]>();
  for (const t of temuan) grup.set(t.kode, [...(grup.get(t.kode) ?? []), t]);
  const bagian = (jenis: "hardware" | "software") => Array.from(grup.entries()).filter(([, xs]) => xs[0].jenis === jenis);
  if (temuan.length === 0) return <p className="text-[13px] text-muted">Semua perangkat mutakhir.</p>;
  return (
    <div className="flex flex-col gap-4">
      {(["hardware", "software"] as const).map((jenis) =>
        bagian(jenis).length ? (
          <div key={jenis}>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-muted">{jenis}</p>
            <ul className="flex flex-col gap-3">
              {bagian(jenis).map(([kode, xs]) => {
                const G = GRUP[kode] ?? { judul: kode, Icon: Wrench };
                const truk = Array.from(new Set(xs.map((x) => x.truck_id).filter(Boolean)));
                return (
                  <li key={kode} className="flex items-start gap-3">
                    <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg", xs.some((x) => x.tingkat === "kritis") ? "bg-crit-soft text-crit" : "bg-[#e8edfb] text-[#2b3f87]")}>
                      <G.Icon size={16} aria-hidden />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-[13px] font-medium">{G.judul}</span>
                      <span className="block text-[12px] text-muted">
                        {xs.length === 1 ? xs[0].pesan : `${xs.length} perangkat: ${truk.slice(0, 3).join(", ")}${truk.length > 3 ? ", …" : ""}`}
                      </span>
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null
      )}
    </div>
  );
}
