"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { AppHeader } from "@/components/app-header";
import { Icon } from "@/components/icon";
import { ScenarioPicker } from "@/components/scenario-picker";
import { ResultCard } from "@/components/result-card";
import { TemperatureChart } from "@/components/temperature-chart";
import { ChartLoading, PanelError, PanelEmpty, PanelLoading } from "@/components/panel-states";
import {
  ApiError,
  analyzeShipment,
  fetchScenarioReadings,
  fetchScenarios,
  thresholdFor,
  toChartPoints,
  usingMock,
} from "@/lib/api";
import { MIN_READINGS, parseReadingsCsv } from "@/lib/csv";
import { AnalyzeResponse, CargoThreshold, ChartPoint, ScenarioPreset, TelemetryReading } from "@/lib/types";

// Leaflet menyentuh `window`, jadi tidak boleh dirender di server.
const RouteMap = dynamic(() => import("@/components/route-map"), {
  ssr: false,
  loading: () => <ChartLoading />,
});

export default function Home() {
  const [scenarios, setScenarios] = useState<ScenarioPreset[]>([]);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [csvReadings, setCsvReadings] = useState<TelemetryReading[] | null>(null);
  const [csvFileName, setCsvFileName] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [points, setPoints] = useState<ChartPoint[] | null>(null);
  const [threshold, setThreshold] = useState<CargoThreshold | null>(null);

  // Muat daftar skenario sekali di awal.
  useEffect(() => {
    let cancelled = false;
    fetchScenarios()
      .then((list) => {
        if (cancelled) return;
        setScenarios(list);
        setScenarioId((current) => current ?? list[0]?.id ?? null);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Gagal memuat skenario.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const runAnalysis = useCallback(
    async (args: { scenarioId?: string | null; readings?: TelemetryReading[]; fileName?: string | null }) => {
      setLoading(true);
      setError(null);

      try {
        let readings: TelemetryReading[];
        let cargoProfile: string;
        let activeScenarioId: string | undefined;

        if (args.readings) {
          readings = args.readings;
          cargoProfile = "vaksin_2_8C";
        } else {
          const id = args.scenarioId ?? scenarioId;
          if (!id) throw new Error("Pilih skenario dulu, atau unggah CSV.");
          const preset = scenarios.find((s) => s.id === id);
          // Bacaan diambil dari backend lalu dikirim balik APA ADANYA —
          // inilah yang menghilangkan risiko nama field meleset.
          readings = await fetchScenarioReadings(id);
          cargoProfile = preset?.cargoProfile ?? "vaksin_2_8C";
          activeScenarioId = id;
        }

        if (readings.length < MIN_READINGS) {
          throw new Error(
            `Backend memerlukan minimal ${MIN_READINGS} bacaan untuk inferensi yang andal; data ini hanya ${readings.length}.`
          );
        }

        const response = await analyzeShipment(
          {
            shipment_id: `demo-${Date.now()}`,
            cargo_profile: cargoProfile,
            readings,
          },
          activeScenarioId
        );

        setPoints(toChartPoints(readings));
        setThreshold(thresholdFor(cargoProfile));
        setResult(response);
      } catch (e) {
        setResult(null);
        setPoints(null);
        setThreshold(null);
        if (e instanceof ApiError || e instanceof Error) setError(e.message);
        else setError("Terjadi kesalahan yang tidak diketahui.");
      } finally {
        setLoading(false);
      }
    },
    [scenarioId, scenarios]
  );

  function handleSelectScenario(id: string) {
    setScenarioId(id);
    setCsvReadings(null);
    setCsvFileName(null);
    // Memilih skenario TIDAK langsung menganalisis — konsep meminta satu
    // tombol eksplisit, karena jeda "klik → skeleton → hasil" itu bagian
    // dari momen demonya.
    setResult(null);
    setPoints(null);
    setError(null);
  }

  async function handleCsvUpload(file: File) {
    setError(null);
    try {
      const text = await file.text();
      const parsed = parseReadingsCsv(text);
      if (parsed.length === 0) throw new Error("CSV tidak berisi bacaan yang valid.");
      setCsvReadings(parsed);
      setCsvFileName(file.name);
      setScenarioId(null);
      setResult(null);
      setPoints(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal membaca CSV.");
    }
  }

  function handleAnalyze() {
    if (csvReadings) runAnalysis({ readings: csvReadings, fileName: csvFileName });
    else runAnalysis({ scenarioId });
  }

  const hasInput = Boolean(scenarioId || csvReadings);
  const lastPoint = useMemo(() => (points ? points[points.length - 1] : null), [points]);

  return (
    <main className="coldship-bg min-h-screen p-4 lg:p-6">
      <div className="mx-auto flex w-full max-w-[1280px] flex-col gap-4">
        {/* 1 — header */}
        <AppHeader usingMock={usingMock} />

        {/* 2 & 3 — zona input + tombol tunggal */}
        <div className="relative z-30">
          <ScenarioPicker
            scenarios={scenarios}
            scenarioId={scenarioId}
            csvFileName={csvFileName}
            loading={loading}
            onSelectScenario={handleSelectScenario}
            onCsvUpload={handleCsvUpload}
            onAnalyze={handleAnalyze}
          />
        </div>

        {/* 4–8 — kartu hasil */}
        <div className="relative z-0">
          {loading && (
            <div className="card p-4">
              <PanelLoading rows={2} />
            </div>
          )}
          {!loading && error && (
            <div className="card p-4">
              <PanelError message={error} />
            </div>
          )}
          {!loading && !error && !result && (
            <div className="card p-4">
              <PanelEmpty
                message={
                  hasInput
                    ? 'Tekan "Analisis Perjalanan" untuk menjalankan model.'
                    : "Pilih salah satu skenario demo atau unggah CSV telemetri kamu."
                }
              />
            </div>
          )}
          {!loading && !error && result && <ResultCard result={result} />}
        </div>

        {/* 9 — grafik suhu + peta rute */}
        {!loading && !error && result && points && threshold && (
          <div className="grid min-h-[320px] grid-cols-1 gap-4 lg:grid-cols-[1.25fr_1fr]">
            <div className="card card-p flex min-h-[320px] flex-col">
              <div className="mb-1.5 flex shrink-0 flex-wrap items-baseline justify-between gap-x-3">
                <p className="t-card-title flex items-center gap-2">
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-lg bg-brand-soft">
                    <Icon name="analytics" size={13} className="text-brand" />
                  </span>
                  Suhu kargo — aktual vs prediksi
                </p>
                <p className="t-meta">
                  garis penuh = aktual · putus-putus = prediksi · pita = {threshold.label}
                </p>
              </div>
              <div className="min-h-0 flex-1">
                <TemperatureChart
                  readings={points}
                  forecast={result.forecast}
                  threshold={threshold}
                  showAmbient
                  compact
                />
              </div>
            </div>

            <div className="card card-p flex min-h-[320px] flex-col">
              <div className="mb-1.5 flex shrink-0 items-baseline justify-between gap-2">
                <p className="t-card-title flex items-center gap-2">
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-lg bg-brand-soft">
                    <Icon name="route" size={13} className="text-brand" />
                  </span>
                  Rute perjalanan
                </p>
                {lastPoint?.lat != null && lastPoint?.lon != null && (
                  <p className="t-meta font-mono">
                    {lastPoint.lat.toFixed(4)}, {lastPoint.lon.toFixed(4)}
                  </p>
                )}
              </div>
              <div className="min-h-0 flex-1">
                <RouteMap points={points} status={result.status} />
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
