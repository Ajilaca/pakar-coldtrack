"use client";

import { ReactNode, useId } from "react";
import { CARGO_PROFILES, profileById } from "@/lib/profiles";
import { WINDOW_MINUTES } from "@/lib/window";
import { ConditionInput } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { Icon } from "@phosphor-icons/react";
import { Package, Thermometer, SunDim, Truck } from "@phosphor-icons/react/dist/ssr";
import { CardTitle } from "./card-title";

export type FormErrors = Partial<Record<keyof ConditionInput, string>>;

export function validateCondition(c: ConditionInput): FormErrors {
  const e: FormErrors = {};
  const finite = (n: number) => Number.isFinite(n);
  if (!c.shipmentId.trim()) e.shipmentId = "ID pengiriman wajib diisi.";
  if (!finite(c.massKg) || c.massKg <= 0) e.massKg = "Massa harus lebih dari 0 kg.";
  if (!finite(c.tempNow) || c.tempNow < -40 || c.tempNow > 60) e.tempNow = "Isi suhu antara −40 dan 60°C.";
  if (!finite(c.temp60Ago) || c.temp60Ago < -40 || c.temp60Ago > 60) e.temp60Ago = "Isi suhu antara −40 dan 60°C.";
  if (!finite(c.ambient) || c.ambient < -20 || c.ambient > 60) e.ambient = "Isi suhu antara −20 dan 60°C.";
  if (!finite(c.humidity) || c.humidity < 0 || c.humidity > 100) e.humidity = "Isi kelembapan 0–100%.";
  if (c.doorOpen && (!finite(c.doorMinutes) || c.doorMinutes < 1 || c.doorMinutes > WINDOW_MINUTES))
    e.doorMinutes = `Isi 1–${WINDOW_MINUTES} menit.`;
  if (!c.moving && (!finite(c.stoppedMinutes) || c.stoppedMinutes < 1 || c.stoppedMinutes > WINDOW_MINUTES))
    e.stoppedMinutes = `Isi 1–${WINDOW_MINUTES} menit.`;
  return e;
}

interface Props {
  value: ConditionInput;
  errors: FormErrors;
  onChange: (next: ConditionInput) => void;
}

export function ConditionForm({ value, errors, onChange }: Props) {
  const set = <K extends keyof ConditionInput>(key: K, v: ConditionInput[K]) => onChange({ ...value, [key]: v });
  const num = (key: keyof ConditionInput) => (ev: React.ChangeEvent<HTMLInputElement>) =>
    set(key, (ev.target.value === "" ? NaN : Number(ev.target.value)) as never);
  const profile = profileById(value.cargoProfile);

  return (
    <form className="card flex flex-col gap-3 p-5" onSubmit={(e) => e.preventDefault()} noValidate aria-label="Detail muatan">
      <CardTitle icon={Package}>Detail muatan</CardTitle>
      <div className="h-1" />
      <Group title="Pengiriman" icon={Package}>
        <Field label="ID pengiriman" error={errors.shipmentId}>
          {(id, err) => (
            <input id={id} className="field" value={value.shipmentId} aria-invalid={err}
              onChange={(e) => set("shipmentId", e.target.value)} autoComplete="off" />
          )}
        </Field>
        <Field label="Jenis muatan" hint={`Batas aman ${profile.min} s/d ${profile.max}°C`}>
          {(id) => (
            <select id={id} className="field" value={value.cargoProfile}
              onChange={(e) => set("cargoProfile", e.target.value)}>
              {CARGO_PROFILES.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Massa muatan" unit="kg" error={errors.massKg}>
          {(id, err) => (
            <input id={id} type="number" inputMode="decimal" min={1} step={50} className="field num"
              value={Number.isNaN(value.massKg) ? "" : value.massKg} onChange={num("massKg")} aria-invalid={err} />
          )}
        </Field>
      </Group>

      <Group title="Suhu muatan" icon={Thermometer}>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Sekarang" unit="°C" error={errors.tempNow}>
            {(id, err) => (
              <input id={id} type="number" inputMode="decimal" step={0.1} className="field num"
                value={Number.isNaN(value.tempNow) ? "" : value.tempNow} onChange={num("tempNow")} aria-invalid={err} />
            )}
          </Field>
          <Field label="1 jam lalu" unit="°C" error={errors.temp60Ago}>
            {(id, err) => (
              <input id={id} type="number" inputMode="decimal" step={0.1} className="field num"
                value={Number.isNaN(value.temp60Ago) ? "" : value.temp60Ago} onChange={num("temp60Ago")} aria-invalid={err} />
            )}
          </Field>
        </div>
      </Group>

      <Group title="Lingkungan" icon={SunDim}>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Suhu luar" unit="°C" error={errors.ambient}>
            {(id, err) => (
              <input id={id} type="number" inputMode="decimal" step={0.5} className="field num"
                value={Number.isNaN(value.ambient) ? "" : value.ambient} onChange={num("ambient")} aria-invalid={err} />
            )}
          </Field>
          <Field label="Kelembapan" unit="%" error={errors.humidity}>
            {(id, err) => (
              <input id={id} type="number" inputMode="numeric" min={0} max={100} className="field num"
                value={Number.isNaN(value.humidity) ? "" : value.humidity} onChange={num("humidity")} aria-invalid={err} />
            )}
          </Field>
        </div>
      </Group>

      <Group title="Kondisi truk" icon={Truck}>
        <Toggle label="Pintu kargo" options={["Tertutup", "Terbuka"]} active={value.doorOpen ? 1 : 0}
          onSelect={(i) => set("doorOpen", i === 1)} />
        {value.doorOpen && (
          <Field label="Terbuka sejak" unit="menit" error={errors.doorMinutes}>
            {(id, err) => (
              <input id={id} type="number" inputMode="numeric" min={1} max={WINDOW_MINUTES} className="field num"
                value={Number.isNaN(value.doorMinutes) ? "" : value.doorMinutes} onChange={num("doorMinutes")} aria-invalid={err} />
            )}
          </Field>
        )}
        <Toggle label="Truk" options={["Bergerak", "Berhenti"]} active={value.moving ? 0 : 1}
          onSelect={(i) => set("moving", i === 0)} />
        {!value.moving && (
          <Field label="Berhenti sejak" unit="menit" error={errors.stoppedMinutes}>
            {(id, err) => (
              <input id={id} type="number" inputMode="numeric" min={1} max={WINDOW_MINUTES} className="field num"
                value={Number.isNaN(value.stoppedMinutes) ? "" : value.stoppedMinutes} onChange={num("stoppedMinutes")} aria-invalid={err} />
            )}
          </Field>
        )}
      </Group>

      <p className="px-1 pt-1 text-[12px] text-muted">
        Data {WINDOW_MINUTES} menit terakhir disusun otomatis dari kondisi di atas. Analisis berjalan setiap kali isian berubah.
      </p>
    </form>
  );
}

function Group({ title, icon: I, children }: { title: string; icon: Icon; children: ReactNode }) {
  const id = useId();
  return (
    <div role="group" aria-labelledby={id} className="tile flex gap-3 p-4">
      <span className="icon-dot size-10" aria-hidden>
        <I size={20} weight="bold" />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <p id={id} className="eyebrow">{title}</p>
        {children}
      </div>
    </div>
  );
}

function Field({
  label, unit, hint, error, children,
}: {
  label: string;
  unit?: string;
  hint?: string;
  error?: string;
  children: (id: string, invalid: boolean) => ReactNode;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="label">
        {label}
        {unit && <span className="font-normal"> ({unit})</span>}
      </label>
      {children(id, Boolean(error))}
      {error ? (
        <p className="text-[12px] text-crit" role="alert">{error}</p>
      ) : (
        hint && <p className="text-[12px] text-muted">{hint}</p>
      )}
    </div>
  );
}

function Toggle({
  label, options, active, onSelect,
}: {
  label: string;
  options: [string, string];
  active: 0 | 1;
  onSelect: (i: 0 | 1) => void;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <span className="label" id={id}>{label}</span>
      <div role="radiogroup" aria-labelledby={id} className="grid grid-cols-2 gap-1 rounded-md bg-surface-muted p-1">
        {options.map((o, i) => (
          <button
            key={o}
            type="button"
            role="radio"
            aria-checked={active === i}
            onClick={() => onSelect(i as 0 | 1)}
            className={cn(
              "h-8 cursor-pointer rounded-[4px] text-[13px] font-medium transition-colors duration-150",
              active === i ? "bg-surface text-brand shadow-sm" : "text-muted hover:text-ink"
            )}
          >
            {o}
          </button>
        ))}
      </div>
    </div>
  );
}
