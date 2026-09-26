import { AnalyzeResponse } from "@/lib/types";
import { diagnosisText } from "@/lib/labels";
import { STATUS_TONE } from "@/lib/tone";
import { cn } from "@/lib/utils";

export function VehicleStatus({ result }: { result: AnalyzeResponse }) {
  const tone = STATUS_TONE[result.status];
  return (
    <div className="flex flex-col gap-4">
      <div>
        <p className="eyebrow">Status kendaraan</p>
        <p className={cn("mt-1 text-[44px] font-extrabold leading-none tracking-[-0.04em]", tone.text)}>{tone.word}</p>
      </div>
      <div className={cn("flex items-center gap-3 rounded-xl px-4 py-3", tone.soft)}>
        <tone.Icon size={28} weight="bold" className={cn("shrink-0", tone.text)} aria-hidden />
        <div className="min-w-0">
          <p className={cn("text-[15px] font-semibold", tone.text)}>{diagnosisText(result.failure_mode.label)}</p>
          <p className="text-[13px] text-muted">
            Indeks risiko <span className="num font-medium text-ink">{result.risk_index.toFixed(2)}</span>
          </p>
        </div>
      </div>
    </div>
  );
}
