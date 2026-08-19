import { StatusCharacter, STATUS_GRADIENT } from "@/components/status-character";
import { TtbDisplay } from "@/components/ttb-display";
import { DriverList } from "@/components/driver-list";
import { ActionSteps } from "@/components/action-steps";
import { AiRecommendedBadge } from "@/components/ai-badge";
import { AnalyzeResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Kartu hasil — "bintang demo" menurut role/context-r4-frontend.md baris 43.
 * Merender SELURUH isi AnalyzeResponse, dalam urutan baca yang disengaja:
 * status → TTB → diagnosis → mengapa → tindakan.
 */
export function ResultCard({ result }: { result: AnalyzeResponse }) {
  return (
    <div className="glass-glow overflow-hidden rounded-2xl p-4">
      <div className="grid grid-cols-1 items-stretch gap-4 lg:grid-cols-[0.8fr_1fr_1.15fr]">
        {/* Kolom 1 — lampu status + angka raksasa TTB */}
        <div
          className={cn(
            "on-gradient flex h-full flex-col items-center justify-center gap-4 rounded-2xl px-4 py-5 text-center shadow-[0_12px_28px_-14px_hsl(var(--ocean-deep)/0.45)]",
            STATUS_GRADIENT[result.status]
          )}
        >
          <div className="space-y-2">
            <p className="t-label">Status perjalanan</p>
            <StatusCharacter status={result.status} size={60} orientation="stack" />
          </div>
          <div className="h-px w-14 bg-white/30" />
          <TtbDisplay status={result.status} minutes={result.time_to_breach_min} centered />
        </div>

        {/* Kolom 2 — diagnosis + "mengapa AI berpikir begini" */}
        <div className="flex flex-col gap-5 py-1">
          <div className="space-y-1.5">
            <p className="t-label flex h-5 items-center">Diagnosis mode kegagalan</p>
            <p className="t-metric leading-snug">{result.failure_mode.label}</p>
            <div className="flex items-center gap-2">
              <div className="h-1.5 w-20 shrink-0 overflow-hidden rounded-full bg-secondary">
                <div
                  className="grad-brand h-full rounded-full"
                  style={{ width: `${Math.round(result.failure_mode.confidence * 100)}%` }}
                />
              </div>
              <span className="t-meta tabular">
                keyakinan {Math.round(result.failure_mode.confidence * 100)}%
              </span>
            </div>
          </div>

          <div className="space-y-1.5">
            <p className="t-label flex h-5 items-center">Mengapa AI berpikir begini</p>
            <DriverList drivers={result.drivers} />
          </div>
        </div>

        {/* Kolom 3 — langkah tindakan */}
        <div className="flex flex-col gap-1.5 py-1 lg:pl-2">
          <div className="flex h-5 items-center justify-between gap-2">
            <p className="t-label">Tindakan yang disarankan</p>
            <AiRecommendedBadge />
          </div>
          <ActionSteps actions={result.actions} />
        </div>
      </div>

      {/* jejak teknis — memperkuat kesan sistem nyata di depan juri */}
      {(result.model_version || result.inference_ms !== undefined) && (
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-border pt-2.5">
          {result.model_version && (
            <span className="t-meta">
              model <span className="font-mono text-ink">{result.model_version}</span>
            </span>
          )}
          {result.inference_ms !== undefined && (
            <span className="t-meta">
              inferensi <span className="font-mono text-ink">{result.inference_ms} ms</span>
            </span>
          )}
          {result.risk_index !== undefined && (
            <span className="t-meta">
              indeks risiko <span className="font-mono text-ink">{result.risk_index.toFixed(2)}</span>
            </span>
          )}
        </div>
      )}
    </div>
  );
}
