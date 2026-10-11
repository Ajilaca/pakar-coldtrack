import { Info, WarningCircle } from "@phosphor-icons/react/dist/ssr";
import { AnalyzeResponse } from "@/lib/types";
import { diagnosisIcon, diagnosisText } from "@/lib/labels";
import { CardTitle } from "./card-title";

const TOP_N = 3;

export function DiagnosisCard({ result }: { result: AnalyzeResponse }) {
  const fm = result.failure_mode;
  const pct = Math.round((fm?.confidence ?? 0) * 100);
  const I = diagnosisIcon(fm?.label);
  // v3 returns a probability per class; checkpoint2 / fallback return null. Only shown when the label
  // itself comes from the model: a rule-derived label (sensor rules, never-normal-when-alerting)
  // next to a model ranking that says "Normal" would contradict itself.
  const fromModel = !!fm?.probabilities && fm.label in fm.probabilities;
  // Sensor faults come only from the backend's rule layer, so the model's own sensor score is not
  // listed unless the label itself is the sensor fault.
  const top = Object.entries(fromModel ? fm.probabilities ?? {} : {})
    .filter(([label]) => label !== "masalah_sensor" || fm?.label === "masalah_sensor")
    .sort((a, b) => b[1] - a[1])
    .slice(0, TOP_N);
  const incomplete = result.data_lengkap === false;
  return (
    <section className="card flex flex-col gap-4 p-5">
      <CardTitle icon={Info}>Diagnosis masalah</CardTitle>
      {incomplete && (
        <div role="status" className="tile flex items-start gap-2 p-3 text-[13px] text-brand-strong">
          <WarningCircle size={18} weight="bold" aria-hidden className="mt-0.5 shrink-0" />
          <p>
            <span className="font-semibold">Diagnosis kurang andal (data tidak lengkap).</span>{" "}
            {result.catatan_data ?? "Ada bacaan yang hilang dalam 60 menit terakhir."}
          </p>
        </div>
      )}
      <div className="tile flex items-center gap-4 p-4">
        <span className="icon-dot size-12">
          <I size={24} weight="bold" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-brand-strong">{diagnosisText(fm?.label)}</p>
          <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-tint" aria-hidden>
            <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
          </div>
        </div>
        <div className="text-right">
          <p className="num text-[30px] font-extrabold leading-none tracking-[-0.03em] text-accent">{pct}%</p>
          <p className="eyebrow mt-1">Keyakinan</p>
        </div>
      </div>
      {top.length > 0 && (
        <ul className="flex flex-col gap-1.5" aria-label="Kemungkinan lain menurut model">
          {top.map(([label, p]) => (
            <li key={label} className="flex items-center justify-between text-[13px]">
              <span className="text-brand-strong">{diagnosisText(label)}</span>
              <span className="num tabular-nums">{Math.round(p * 100)}%</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
