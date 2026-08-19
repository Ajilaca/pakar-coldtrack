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
          className="flex items-center gap-2 glass glass-interactive rounded-xl px-3 py-2 t-body font-medium text-ink disabled:opacity-50"
        >
          <Icon name="upload" size={18} tone="gray" />
          {fileName ? fileName : "Impor CSV"}
        </button>
      </>
    );
  }

  return (
    <div className="rounded-2xl bg-secondary/60 p-3">
      {input}
      <p className="t-card-title mb-1">Impor data CSV</p>
      <p className="t-meta mb-2.5">
        Gunakan bacaan sensor truk kamu sendiri untuk dianalisis AI.
      </p>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={disabled}
        className="flex w-full items-center justify-center gap-2 grad-brand rounded-xl px-3 py-2 t-body font-medium text-white disabled:opacity-50"
      >
        <Icon name="upload" size={16} tone="white" />
        {fileName ? fileName : "Pilih file .csv"}
      </button>
    </div>
  );
}
