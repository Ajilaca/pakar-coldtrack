import { ChartLine, Drop, Gauge, Timer } from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";
import { ReactNode } from "react";
import { AnalyzeResponse, ConditionInput } from "@/lib/types";
import { isSensorFault } from "@/lib/labels";
import { STATUS_TONE } from "@/lib/tone";
import { cn } from "@/lib/utils";
import { CardTitle } from "./card-title";
import { Ring } from "./ring";

const RING_COLOR = { AMAN: "var(--ok)", WASPADA: "var(--warn)", KRITIS: "var(--crit)" };

export function LiveConditions({ result, input }: { result: AnalyzeResponse; input: ConditionInput }) {
  const tone = STATUS_TONE[result.status];
  const sensor = isSensorFault(result.failure_mode.label);
  const ttb = sensor ? null : result.time_to_breach_min;
  const rate = input.tempNow - input.temp60Ago;

  const ttbLabel = sensor ? "—" : ttb === null ? "60+" : String(Math.round(ttb));
  const ttbValue = ttb === null ? (sensor ? 0 : 1) : ttb / 60;

  return (
    <section className="card flex flex-col gap-5 p-5">
      <CardTitle
        icon={ChartLine}
        aside={
          <span className="flex items-center gap-1.5 text-[12px] text-muted">
            <span className="size-2 rounded-full bg-ok" aria-hidden />
            Diperbarui otomatis
          </span>
        }
      >
        Kondisi terkini
      </CardTitle>

      <div className="grid grid-cols-3 divide-x">
        <Metric ring={<Ring value={ttbValue} label={ttbLabel} color={RING_COLOR[result.status]} />} icon={Timer} title="Waktu tersisa">
          {sensor ? "Sensor bermasalah" : ttb === null ? "Aman > 60 menit" : ttb < 1 ? "Batas terlampaui" : "menit sebelum batas"}
          {result.status !== "AMAN" && (
            <span className={cn("mt-2 inline-block rounded-md px-2 py-0.5 text-[11px] font-bold uppercase", tone.soft, tone.text)}>
              Perlu tindakan
            </span>
          )}
        </Metric>
        <Metric ring={<Ring value={result.risk_index} label={`${Math.round(result.risk_index * 100)}%`} />} icon={Gauge} title="Indeks risiko">
          Laju suhu <span className="num">{rate >= 0 ? "+" : ""}{rate.toFixed(1)}</span> °C/jam
        </Metric>
        <Metric ring={<Ring value={input.humidity / 100} label={`${input.humidity}%`} />} icon={Drop} title="Kelembapan luar">
          Suhu luar <span className="num">{input.ambient}</span> °C
        </Metric>
      </div>
      {!sensor && result.ttb_model_min != null && (
        <p className="-mt-2 text-[12px] text-muted">
          Estimasi model machine learning: <span className="num">{Math.round(result.ttb_model_min)}</span> menit
        </p>
      )}
    </section>
  );
}

function Metric({ ring, icon: I, title, children }: { ring: ReactNode; icon: Icon; title: string; children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 px-2 text-center">
      {ring}
      <div>
        <p className="flex items-center justify-center gap-1.5 text-[13px] font-semibold text-brand-strong">
          <I size={16} weight="bold" className="text-accent" aria-hidden />
          {title}
        </p>
        <p className="mt-0.5 text-[12px] text-muted">{children}</p>
      </div>
    </div>
  );
}
