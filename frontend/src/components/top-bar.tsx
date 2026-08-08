"use client";

import { useState, useRef, useEffect } from "react";
import { Icon } from "@/components/icon";
import { CsvImport } from "@/components/csv-import";
import { ScenarioPreset } from "@/lib/types";
import { getVehicleLabel } from "@/lib/dashboard-data";
import { cn } from "@/lib/utils";

interface TopBarProps {
  scenarios: ScenarioPreset[];
  scenarioId: string | null;
  csvFileName: string | null;
  vehicleLabel: string;
  onSelectScenario: (id: string) => void;
  onCsvUpload: (file: File) => void;
  loading: boolean;
}

export function TopBar({
  scenarios,
  scenarioId,
  csvFileName,
  vehicleLabel,
  onSelectScenario,
  onCsvUpload,
  loading,
}: TopBarProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const activeScenario = scenarios.find((s) => s.id === scenarioId);
  const subtitle = csvFileName ? `Data unggahan (${csvFileName})` : activeScenario?.label ?? "\u2014";

  return (
    <div className="flex items-center justify-between gap-4 rounded-2xl border border-border bg-card px-5 py-3.5 shadow-frost">
      <div>
        <h1 className="font-display text-xl font-extrabold text-ink">ColdTrack AI</h1>
        <p className="text-xs text-muted-foreground">Peringatan dini kegagalan cold chain</p>
      </div>

      <div className="flex items-center gap-3">
        <CsvImport variant="bar" onFileSelected={onCsvUpload} disabled={loading} fileName={null} />

        <div className="relative" ref={ref}>
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-3 rounded-xl border border-border bg-background px-3.5 py-2 hover:bg-secondary"
          >
            <Icon size={22} tone="gray" />
            <div className="text-left">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Vehicle ID</p>
              <p className="font-mono text-sm font-semibold leading-tight text-ink">{vehicleLabel}</p>
              <p className="text-[11px] text-muted-foreground leading-tight truncate max-w-[9rem]">{subtitle}</p>
            </div>
            <svg width="12" height="8" viewBox="0 0 12 8" className={cn("ml-1 transition-transform", open && "rotate-180")}>
              <path d="M1 1.5 6 6.5 11 1.5" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>

          {open && (
            <div className="absolute right-0 z-20 mt-2 w-72 rounded-2xl border border-border bg-card p-2 shadow-frost-lg">
              <p className="px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Pilih skenario demo
              </p>
              {scenarios.map((s) => {
                const active = !csvFileName && s.id === scenarioId;
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
                      "flex w-full items-center justify-between gap-2 rounded-xl px-2.5 py-2 text-left disabled:opacity-50",
                      active ? "bg-brand-soft" : "hover:bg-secondary"
                    )}
                  >
                    <div>
                      <p className="text-sm font-medium text-ink">{s.label}</p>
                      <p className="text-[11px] text-muted-foreground leading-snug">{s.description}</p>
                    </div>
                    <span className="shrink-0 font-mono text-[11px] text-muted-foreground">{getVehicleLabel(s.id)}</span>
                  </button>
                );
              })}
              {csvFileName && (
                <div className="mt-1 rounded-xl bg-brand-soft px-2.5 py-2">
                  <p className="text-sm font-medium text-ink">Data unggahan aktif</p>
                  <p className="text-[11px] text-muted-foreground truncate">{csvFileName}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
