"use client";

import { useRef } from "react";
import { Icon } from "@/components/icon";

interface CsvImportProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
  fileName?: string | null;
  variant?: "card" | "bar";
}

export function CsvImport({ onFileSelected, disabled, fileName, variant = "card" }: CsvImportProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onFileSelected(file);
  }

  const input = (
    <input
      ref={inputRef}
      type="file"
      accept=".csv,text/csv"
      className="hidden"
      onChange={handleChange}
      disabled={disabled}
    />
  );

  if (variant === "bar") {
    return (
      <>
        {input}
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={disabled}
          className="flex items-center gap-2 rounded-xl border border-border bg-card px-3.5 py-2 text-sm font-medium text-ink shadow-frost hover:bg-secondary disabled:opacity-50"
        >
          <Icon size={18} tone="gray" />
          {fileName ? fileName : "Impor CSV"}
        </button>
      </>
    );
  }

  return (
    <div className="rounded-2xl border-2 border-dashed border-border p-3.5">
      {input}
      <p className="text-xs font-semibold mb-1 text-ink">Impor data CSV</p>
      <p className="text-[11px] text-muted-foreground mb-2.5 leading-snug">
        Gunakan bacaan sensor truk kamu sendiri untuk dianalisis AI.
      </p>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-brand px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        <Icon size={16} tone="white" />
        {fileName ? fileName : "Pilih file .csv"}
      </button>
    </div>
  );
}
