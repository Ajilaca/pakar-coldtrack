import { Info } from "@phosphor-icons/react/dist/ssr";
import { AnalyzeResponse } from "@/lib/types";
import { diagnosisIcon, diagnosisText } from "@/lib/labels";
import { CardTitle } from "./card-title";

export function DiagnosisCard({ result }: { result: AnalyzeResponse }) {
  const pct = Math.round(result.failure_mode.confidence * 100);
  const I = diagnosisIcon(result.failure_mode.label);
  return (
    <section className="card flex flex-col gap-4 p-5">
      <CardTitle icon={Info}>Diagnosis masalah</CardTitle>
      <div className="tile flex items-center gap-4 p-4">
        <span className="icon-dot size-12">
          <I size={24} weight="bold" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-brand-strong">{diagnosisText(result.failure_mode.label)}</p>
          <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-tint" aria-hidden>
            <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
          </div>
        </div>
        <div className="text-right">
          <p className="num text-[30px] font-extrabold leading-none tracking-[-0.03em] text-accent">{pct}%</p>
          <p className="eyebrow mt-1">Keyakinan</p>
        </div>
      </div>
    </section>
  );
}
