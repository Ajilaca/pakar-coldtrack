"use client";

// Simulasi (frame Simulasi): kirim bacaan skenario demo atau isian manual ke POST /api/v1/analyze.
// Tidak menulis apa pun ke data armada.

import { useEffect, useMemo, useState } from "react";
import { FaktorCard, StatusBanner, TindakanCard } from "@/components/fleet/condition";
import { PageHeader } from "@/components/fleet/notifications";
import { Card, Galat } from "@/components/fleet/ui";
import { ConditionForm, validateCondition } from "@/components/condition-form";
import { ApiError, analyzeShipment } from "@/lib/api";
import { fleetGet } from "@/lib/fleet-api";
import { muatan } from "@/lib/fleet-status";
import { suhu } from "@/lib/format";
import { AnalyzeResponse, ConditionInput, TelemetryReading } from "@/lib/types";
import { buildWindow } from "@/lib/window";

interface Skenario {
  id: string;
  title: string;
  description: string;
  cargo_profile: string;
  expected_status: string;
  reading_count: number;
}

const MANUAL = "manual";
const AWAL: ConditionInput = {
  shipmentId: "SIM-0001", cargoProfile: "vaksin_2_8C", massKg: 1000, tempNow: 5, temp60Ago: 4.5, ambient: 31,
  humidity: 75, doorOpen: false, doorMinutes: 10, moving: true, stoppedMinutes: 10,
};

export default function SimulasiPage() {
  const [daftar, setDaftar] = useState<Skenario[]>([]);
  const [pilih, setPilih] = useState<string>("");
  const [manual, setManual] = useState<ConditionInput>(AWAL);
  const [reefer, setReefer] = useState(true);
  const [hasil, setHasil] = useState<{ r: AnalyzeResponse; profil: string; id: string } | null>(null);
  const [galat, setGalat] = useState<string | null>(null);
  const [sibuk, setSibuk] = useState(false);
  const [skenarioReefer, setSkenarioReefer] = useState<boolean | null>(null);

  useEffect(() => {
    fleetGet<Skenario[]>("/api/v1/scenarios")
      .then((s) => {
        setDaftar(s);
        setPilih((p) => p || s[0]?.id || MANUAL);
      })
      .catch(() => setPilih(MANUAL));
  }, []);

  const errors = useMemo(() => validateCondition(manual), [manual]);
  const sk = daftar.find((s) => s.id === pilih);

  async function analisis() {
    setSibuk(true);
    setGalat(null);
    try {
      let readings: TelemetryReading[];
      let profil: string;
      let id: string;
      if (pilih === MANUAL) {
        readings = buildWindow(manual, new Date()).map((r) => ({ ...r, reefer_on: reefer }));
        profil = manual.cargoProfile;
        id = manual.shipmentId;
      } else {
        const d = await fleetGet<{ readings: TelemetryReading[]; cargo_profile: string; shipment_id?: string }>(`/api/v1/scenarios/${pilih}`);
        readings = d.readings;
        profil = d.cargo_profile;
        id = d.shipment_id ?? pilih;
        setSkenarioReefer(readings[readings.length - 1]?.reefer_on ?? null);
      }
      const r = await analyzeShipment({ shipment_id: id, cargo_profile: profil, mass_kg: pilih === MANUAL ? manual.massKg : undefined, readings });
      setHasil({ r, profil, id });
    } catch (e) {
      setGalat(e instanceof ApiError ? e.message : "Analisis gagal.");
    } finally {
      setSibuk(false);
    }
  }

  return (
    <>
      <PageHeader title="Simulasi" subtitle="Uji skenario tanpa mengubah data armada" />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[360px_1fr]">
        <Card title="Masukan skenario">
          <label className="flex flex-col gap-1.5 text-[13px]">
            <span className="text-muted">Skenario demo</span>
            <select value={pilih} onChange={(e) => { setPilih(e.target.value); setHasil(null); }} className="h-10 rounded-lg border bg-surface px-3">
              {daftar.map((s) => <option key={s.id} value={s.id}>{s.title.replace(/^Skenario \d+:\s*/, "")}</option>)}
              <option value={MANUAL}>Isian manual</option>
            </select>
          </label>
          {sk && (
            <p className="mt-2 text-[12px] text-muted">
              {sk.description} Muatan: {muatan(sk.cargo_profile)} · {sk.reading_count} bacaan.
            </p>
          )}
          {pilih === MANUAL && <div className="mt-4"><ConditionForm value={manual} errors={errors} onChange={setManual} /></div>}
          <label className="mt-4 flex items-center justify-between gap-3 text-[13px]">
            <span>Unit pendingin (reefer) menyala</span>
            <input
              type="checkbox" role="switch" className="size-5 accent-[var(--chart-actual)]"
              checked={pilih === MANUAL ? reefer : skenarioReefer ?? true}
              disabled={pilih !== MANUAL}
              onChange={(e) => setReefer(e.target.checked)}
            />
          </label>
          {pilih !== MANUAL && <p className="mt-1 text-[11px] text-muted">Mengikuti data skenario; ubah lewat Isian manual.</p>}
          <button
            type="button" onClick={analisis} disabled={sibuk || (pilih === MANUAL && Object.keys(errors).length > 0)}
            className="mt-4 h-11 w-full rounded-lg bg-[var(--chart-actual)] font-semibold text-white hover:opacity-90 disabled:opacity-50"
          >
            {sibuk ? "Menganalisis…" : "Analisis perjalanan"}
          </button>
          <p className="mt-2 text-[11px] text-muted">
            Mengirim {pilih === MANUAL ? "60" : sk?.reading_count ?? "…"} bacaan ke POST /api/v1/analyze. Tidak mengubah data armada.
          </p>
        </Card>
        <div className="flex min-w-0 flex-col gap-4">
          {galat && <Galat pesan={galat} />}
          {!hasil ? (
            <p className="rounded-2xl border border-dashed bg-surface p-10 text-center text-[13px] text-muted">
              Pilih skenario lalu klik <b>Analisis perjalanan</b>.
            </p>
          ) : (
            <>
              <StatusBanner
                status={hasil.r.status} subjudul={`${hasil.id} · ${muatan(hasil.profil)}`} ttb={hasil.r.time_to_breach_min}
                label={hasil.r.failure_mode?.label} confidence={hasil.r.failure_mode?.confidence}
                dataLengkap={hasil.r.data_lengkap} catatan={hasil.r.data_lengkap === false ? hasil.r.catatan_data : null}
              />
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <FaktorCard drivers={hasil.r.drivers} />
                <TindakanCard actions={hasil.r.actions} />
              </div>
              <p className="text-[11px] text-muted">
                {hasil.r.model_version} · {hasil.r.inference_ms} ms · prediksi suhu {suhu(hasil.r.forecast.t15)} / {suhu(hasil.r.forecast.t30)} / {suhu(hasil.r.forecast.t60)} (+15/+30/+60 mnt)
              </p>
            </>
          )}
        </div>
      </div>
    </>
  );
}
