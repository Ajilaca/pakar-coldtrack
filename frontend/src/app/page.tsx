"use client";

import { useEffect, useState } from "react";
import { Sidebar } from "@/components/sidebar";
import { TopBar } from "@/components/top-bar";
import { OverviewPanel } from "@/components/panels/overview-panel";
import { ShipmentPanel } from "@/components/panels/shipment-panel";
import { MonitoringPanel } from "@/components/panels/monitoring-panel";
import { RoutePanel } from "@/components/panels/route-panel";
import { AnalyticsPanel } from "@/components/panels/analytics-panel";
import { PredictionPanel } from "@/components/panels/prediction-panel";
import { analyzeShipment, AnalyzeError } from "@/lib/api";
import { parseReadingsCsv } from "@/lib/csv";
import { SCENARIOS, SCENARIO_READINGS } from "@/lib/scenario-data";
import { getVehicleLabel } from "@/lib/dashboard-data";
import { AnalyzeResponse, CargoThreshold, SensorReading } from "@/lib/types";
import { Section } from "@/lib/section";

const DEFAULT_THRESHOLD: CargoThreshold = { min: 2, max: 8, label: "Vaksin 2\u20138\u00b0C" };

export default function Home() {
  const [activeSection, setActiveSection] = useState<Section>("overview");
  const [scenarioId, setScenarioId] = useState<string | null>(SCENARIOS[0].id);
  const [csvFileName, setCsvFileName] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [readings, setReadings] = useState<SensorReading[] | null>(null);
  const [threshold, setThreshold] = useState<CargoThreshold | null>(null);

  useEffect(() => {
    runAnalysis({ scenarioId: SCENARIOS[0].id });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runAnalysis(args: { scenarioId?: string; csvFile?: File }) {
    setLoading(true);
    setError(null);

    try {
      let activeReadings: SensorReading[];
      let activeThreshold: CargoThreshold;
      let cargoProfile: string;

      if (args.csvFile) {
        const text = await args.csvFile.text();
        activeReadings = parseReadingsCsv(text);
        activeThreshold = DEFAULT_THRESHOLD;
        cargoProfile = "custom_upload";
      } else {
        const preset = SCENARIOS.find((s) => s.id === args.scenarioId) ?? SCENARIOS[0];
        activeReadings = SCENARIO_READINGS[preset.id];
        activeThreshold = preset.threshold;
        cargoProfile = preset.cargoProfile;
      }

      if (activeReadings.length === 0) {
        throw new Error("CSV tidak berisi bacaan yang valid.");
      }

      const response = await analyzeShipment(
        {
          shipment_id: `demo-${Date.now()}`,
          cargo_profile: cargoProfile,
          readings: activeReadings.map((r) => ({
            temperature_c: r.temperature_c,
            ambient_temp_c: r.ambient_temp_c,
            door_open: r.door_open,
          })),
        },
        args.scenarioId
      );

      setReadings(activeReadings);
      setThreshold(activeThreshold);
      setResult(response);
    } catch (e) {
      setResult(null);
      setReadings(null);
      setThreshold(null);
      if (e instanceof AnalyzeError) setError(e.message);
      else if (e instanceof Error) setError(e.message);
      else setError("Terjadi kesalahan yang tidak diketahui.");
    } finally {
      setLoading(false);
    }
  }

  function handleSelectScenario(id: string) {
    setScenarioId(id);
    setCsvFileName(null);
    runAnalysis({ scenarioId: id });
  }

  function handleCsvUpload(file: File) {
    setScenarioId(null);
    setCsvFileName(file.name);
    runAnalysis({ csvFile: file });
  }

  const vehicleLabel = csvFileName ? "CUSTOM-01" : getVehicleLabel(scenarioId);

  return (
    <main className="coldship-bg min-h-screen p-4 lg:p-6">
      <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-4 lg:h-[calc(100vh-3rem)]">
        <TopBar
          scenarios={SCENARIOS}
          scenarioId={scenarioId}
          csvFileName={csvFileName}
          vehicleLabel={vehicleLabel}
          onSelectScenario={handleSelectScenario}
          onCsvUpload={handleCsvUpload}
          loading={loading}
        />

        <div className="grid flex-1 grid-cols-[260px_1fr] gap-4 overflow-hidden">
          <Sidebar activeSection={activeSection} onSectionChange={setActiveSection} />

          <div className="overflow-y-auto rounded-3xl p-1">
            <div className="h-full p-4">
              {activeSection === "overview" && (
                <OverviewPanel
                  loading={loading}
                  error={error}
                  result={result}
                  readings={readings}
                  threshold={threshold}
                  scenarioId={scenarioId}
                />
              )}
              {activeSection === "shipment" && (
                <ShipmentPanel loading={loading} error={error} result={result} readings={readings} threshold={threshold} scenarioId={scenarioId} />
              )}
              {activeSection === "monitoring" && (
                <MonitoringPanel loading={loading} error={error} result={result} readings={readings} threshold={threshold} scenarioId={scenarioId} />
              )}
              {activeSection === "route" && (
                <RoutePanel loading={loading} error={error} result={result} readings={readings} threshold={threshold} scenarioId={scenarioId} />
              )}
              {activeSection === "analytics" && (
                <AnalyticsPanel loading={loading} error={error} result={result} readings={readings} threshold={threshold} scenarioId={scenarioId} />
              )}
              {activeSection === "prediction" && (
                <PredictionPanel loading={loading} error={error} result={result} readings={readings} threshold={threshold} scenarioId={scenarioId} />
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
