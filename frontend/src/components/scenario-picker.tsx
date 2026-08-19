"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/icon";
import { CsvImport } from "@/components/csv-import";
import { ScenarioPreset } from "@/lib/types";
import { cn } from "@/lib/utils";

interface ScenarioPickerProps {
  scenarios: ScenarioPreset[];
  scenarioId: string | null;
  csvFileName: string | null;
  loading: boolean;
  onSelectScenario: (id: string) => void;
  onCsvUpload: (file: File) => void;
  onAnalyze: () => void;
}

/**
 * Zona input — satu-satunya tempat pengguna memberi masukan, sesuai
 * "satu alur interaksi inti" di role/context-r4-frontend.md.
 * Dropdown 5 skenario + unggah CSV + SATU tombol jalankan.
 */
export function ScenarioPicker({
  scenarios,
  scenarioId,
  csvFileName,
  loading,
  onSelectScenario,
  onCsvUpload,
  onAnalyze,
}: ScenarioPickerProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const active = scenarios.find((s) => s.id === scenarioId);
  const primary = csvFileName ?? active?.label ?? "Pilih skenario";
  const secondary = csvFileName ? "Data unggahan" : active?.description ?? "";

  return (
    <div className="card card-p flex flex-col gap-2.5 lg:flex-row lg:items-center">
      {/* dropdown skenario */}
      <div className="relative min-w-0 flex-1" ref={ref}>
        <p className="t-label mb-1">Skenario demo</p>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          disabled={loading}
          className="glass glass-interactive flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left disabled:opacity-50"
        >
          <Icon name="shipment" size={18} tone="gray" />
          <span className="min-w-0 flex-1">
            <span className="t-body block truncate font-semibold text-ink">{primary}</span>
            <span className="t-meta block truncate">{secondary}</span>
          </span>
          <svg width="12" height="8" viewBox="0 0 12 8" className={cn("shrink-0 transition-transform", open && "rotate-180")}>
            <path d="M1 1.5 6 6.5 11 1.5" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>

        {open && (
          <div className="absolute left-0 right-0 z-30 mt-2 rounded-2xl bg-card p-2 shadow-[0_18px_44px_-14px_hsl(var(--ocean-deep)/0.28)]">
            {scenarios.map((s) => {
              const isActive = !csvFileName && s.id === scenarioId;
              return (
                <button
                  key={s.id}
                  type="button"
                  disabled={loading}
                  onClick={() => {
                    onSelectScenario(s.id);
                    setOpen(false);
                  }}
                  className={cn(
                    "block w-full rounded-xl px-2.5 py-2 text-left disabled:opacity-50",
                    isActive ? "bg-brand-soft" : "hover:bg-secondary"
                  )}
                >
                  <span className="t-body block font-medium text-ink">{s.label}</span>
                  <span className="t-meta block">{s.description}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* unggah CSV */}
      <div className="shrink-0">
        <p className="t-label mb-1">Data sendiri</p>
        <CsvImport variant="bar" onFileSelected={onCsvUpload} disabled={loading} fileName={null} />
      </div>

      {/* tombol tunggal */}
      <div className="shrink-0 lg:self-end">
        <button
          type="button"
          onClick={onAnalyze}
          disabled={loading || (!scenarioId && !csvFileName)}
          className="grad-brand glass-interactive flex w-full items-center justify-center gap-2 rounded-xl px-5 py-2.5 t-body font-bold text-white disabled:opacity-50 lg:w-auto"
        >
          {loading ? (
            <>
              <span className="size-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
              Menganalisis…
            </>
          ) : (
            <>
              <Icon name="ai" size={15} className="text-white" />
              Analisis Perjalanan
            </>
          )}
        </button>
      </div>
    </div>
  );
}
