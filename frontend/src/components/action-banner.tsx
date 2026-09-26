import { ArrowRight } from "@phosphor-icons/react/dist/ssr";
import { AnalyzeResponse } from "@/lib/types";
import { diagnosisText } from "@/lib/labels";
import { STATUS_TONE } from "@/lib/tone";
import { cn } from "@/lib/utils";

const BTN = { AMAN: "bg-ok", WASPADA: "bg-warn", KRITIS: "bg-crit" };

export function ActionBanner({ result }: { result: AnalyzeResponse }) {
  const tone = STATUS_TONE[result.status];
  const top = [...result.actions].sort((a, b) => a.priority - b.priority)[0];
  if (!top) return null;

  return (
    <section
      aria-live="polite"
      className={cn("flex flex-col gap-4 rounded-2xl border p-5 sm:flex-row sm:items-center sm:gap-6 sm:p-6", tone.soft)}
    >
      <span className={cn("flex size-16 shrink-0 items-center justify-center rounded-full bg-surface", tone.text)}>
        <tone.Icon size={34} weight="bold" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className={cn("eyebrow", tone.text)}>Tindakan yang disarankan</p>
        <p className="mt-1 text-[24px] font-bold leading-tight tracking-[-0.02em] text-brand-strong">{top.text}</p>
        <p className="mt-1 text-[15px] text-muted">
          {diagnosisText(result.failure_mode.label)}
          {top.eta_min != null && top.eta_min > 0 && <> · perkiraan <span className="num">± {top.eta_min}</span> menit</>}
        </p>
      </div>
      <a
        href="#tindakan"
        className={cn(
          "inline-flex h-12 shrink-0 cursor-pointer items-center justify-center gap-2 rounded-full px-6 text-[15px] font-semibold text-white transition-opacity duration-150 hover:opacity-90",
          BTN[result.status]
        )}
      >
        Lihat detail
        <ArrowRight size={18} weight="bold" aria-hidden />
      </a>
    </section>
  );
}
