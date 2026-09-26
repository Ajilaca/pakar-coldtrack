"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppHeader } from "@/components/app-header";
import { ConditionForm, validateCondition } from "@/components/condition-form";
import { ActionBanner } from "@/components/action-banner";
import { VehicleStatus } from "@/components/vehicle-status";
import { TruckVisual } from "@/components/truck-visual";
import { DiagnosisCard } from "@/components/diagnosis-card";
import { LiveConditions } from "@/components/live-conditions";
import { TemperatureChart } from "@/components/temperature-chart";
import { ActionSteps } from "@/components/action-steps";
import { DriverList } from "@/components/driver-list";
import { ResultEmpty, ResultError, ResultSkeleton } from "@/components/panel-states";
import { ApiError, analyzeShipment } from "@/lib/api";
import { profileById } from "@/lib/profiles";
import { buildWindow } from "@/lib/window";
import { AnalyzeResponse, ConditionInput, TelemetryReading } from "@/lib/types";
import { cn } from "@/lib/utils";

const DEBOUNCE_MS = 600;

const INITIAL: ConditionInput = {
  shipmentId: "TRK-JKT-0417",
  cargoProfile: "vaksin_2_8C",
  massKg: 1000,
  tempNow: 5,
  temp60Ago: 4.5,
  ambient: 31,
  humidity: 75,
  doorOpen: false,
  doorMinutes: 10,
  moving: true,
  stoppedMinutes: 10,
};

interface Analysis {
  result: AnalyzeResponse;
  readings: TelemetryReading[];
  input: ConditionInput;
}

export default function Home() {
  const [input, setInput] = useState<ConditionInput>(INITIAL);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const inFlight = useRef<AbortController | null>(null);

  const errors = useMemo(() => validateCondition(input), [input]);
  const valid = Object.keys(errors).length === 0;

  const run = useCallback(async (c: ConditionInput) => {
    inFlight.current?.abort();
    const ctrl = new AbortController();
    inFlight.current = ctrl;
    const readings = buildWindow(c, new Date());
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeShipment(
        { shipment_id: c.shipmentId.trim(), cargo_profile: c.cargoProfile, mass_kg: c.massKg, readings },
        ctrl.signal
      );
      setAnalysis({ result, readings, input: c });
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setError(e instanceof ApiError ? e.message : "Terjadi kesalahan yang tidak diketahui.");
    } finally {
      if (inFlight.current === ctrl) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!valid) return;
    const t = setTimeout(() => run(input), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [input, valid, retry, run]);

  const a = analysis;
  const profile = profileById((a?.input ?? input).cargoProfile);

  return (
    <div className="flex min-h-dvh flex-col">
      <AppHeader model={analysis?.result.model_version} />

      <main className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col gap-5 p-4 lg:p-6">
        {error && <ResultError message={error} onRetry={() => setRetry((n) => n + 1)} />}
        {a && <ActionBanner result={a.result} />}

        <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
          {/* Left: vehicle status + cargo input */}
          <div className="flex flex-col gap-5 xl:col-span-3">
            {a && (
              <div className="card p-5">
                <VehicleStatus result={a.result} />
              </div>
            )}
            <ConditionForm value={input} errors={errors} onChange={setInput} />
          </div>

          {/* Center + right: results */}
          {!a ? (
            <div className="xl:col-span-9">
              {loading ? <ResultSkeleton /> : !error && (
                <ResultEmpty message="Lengkapi detail muatan untuk melihat analisis." />
              )}
            </div>
          ) : (
            <div className={cn("grid grid-cols-1 gap-5 transition-opacity duration-150 lg:grid-cols-2 xl:col-span-9 xl:grid-cols-9", loading && "opacity-60")}>
              <div className="flex flex-col gap-5 xl:col-span-5">
                <div className="card flex flex-1 flex-col justify-center p-5">
                  <TruckVisual result={a.result} input={a.input} />
                </div>
                <DiagnosisCard result={a.result} />
              </div>
              <div className="flex flex-col gap-5 xl:col-span-4">
                <LiveConditions result={a.result} input={a.input} />
                <TemperatureChart readings={a.readings} forecast={a.result.forecast} profile={profile} />
              </div>
              <div className="lg:col-span-2 xl:col-span-9 grid grid-cols-1 gap-5 lg:grid-cols-2">
                <ActionSteps actions={a.result.actions} />
                <DriverList drivers={a.result.drivers} />
              </div>
            </div>
          )}
        </div>
      </main>

      <footer className="border-t px-4 py-3 text-[12px] text-muted lg:px-6">
        {a && (
          <span className="num">
            {a.result.model_version} · {a.result.inference_ms} ms ·{" "}
          </span>
        )}
        Alat bantu keputusan, bukan pengganti penilaian operator.
      </footer>
    </div>
  );
}
