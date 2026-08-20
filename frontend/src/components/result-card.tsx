import { Icon, IconName } from "@/components/icon";
import { StatusCharacter, STATUS_GRADIENT } from "@/components/status-character";
import { TtbDisplay } from "@/components/ttb-display";
import { DriverList } from "@/components/driver-list";
import { ActionSteps } from "@/components/action-steps";
import { AiRecommendedBadge } from "@/components/ai-badge";
import { AnalyzeResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Ikon diagnosis dipilih dari kata kunci pada label, bukan dari daftar kelas
 * yang kaku — backend bisa mengirim nama kelas mentah (A0, A1, A7) maupun
 * nama panjang seperti "pintu_terbuka_lama", dan keduanya harus tertangani.
 */
function diagnosisIcon(label: string): IconName {
  const s = label.toLowerCase();
  if (s.includes("pintu")) return "door";
  if (s.includes("sensor")) return "sensor";
  if (s.includes("ambien")) return "ambient";
  if (s.includes("reefer") || s.includes("pendingin") || s.includes("kompresor") || s.includes("degradasi"))
    return "repair";
  if (s.includes("normal") || s.includes("sehat")) return "safe";
  return "warning";
}

/**
 * Kartu hasil — "bintang demo" menurut role/context-r4-frontend.md baris 43.
 *
 * Sengaja dipecah jadi beberapa kotak berdiri sendiri, bukan satu kartu besar
 * berisi tiga kolom. Urutan bacanya tetap seperti di konsep:
 * status -> TTB -> diagnosis -> mengapa -> tindakan.
 */
export function ResultCard({ result }: { result: AnalyzeResponse }) {
  const confidencePct = Math.round(result.failure_mode.confidence * 100);

  return (
    <div className="space-y-3">
      {/* ---- Baris 1: status + diagnosis ---- */}
      <div className="grid grid-cols-1 items-stretch gap-3 lg:grid-cols-[0.85fr_1.15fr]">
        {/* Status — satu-satunya blok bergradien, biar jadi titik jatuh mata */}
        <div
          className={cn(
            "on-gradient flex flex-col items-center justify-center gap-4 rounded-2xl px-4 py-6 text-center shadow-[0_12px_28px_-14px_hsl(var(--ocean-deep)/0.45)]",
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

        {/* Diagnosis — keyakinan ditampilkan sebagai angka besar */}
        <div className="card glass-interactive flex flex-col justify-center gap-3 p-5">
          <p className="t-label">Diagnosis mode kegagalan</p>

          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <span className="grad-ocean flex size-11 shrink-0 items-center justify-center rounded-xl shadow-[0_6px_16px_-8px_hsl(var(--ocean-deep)/0.7)]">
                <Icon name={diagnosisIcon(result.failure_mode.label)} size={22} tone="white" />
              </span>
              <p className="t-panel-title min-w-0 leading-snug">{result.failure_mode.label}</p>
            </div>

            <div className="shrink-0 text-right">
              <p className="t-hero grad-text tabular leading-none">{confidencePct}%</p>
              <p className="t-label mt-1">Keyakinan model</p>
            </div>
          </div>

          {/* bilah tipis sebagai penguat visual angka di atasnya */}
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
            <div
              className="grad-brand h-full rounded-full transition-[width] duration-700 ease-out"
              style={{ width: `${confidencePct}%` }}
            />
          </div>
        </div>
      </div>

      {/* ---- Baris 2: mengapa AI berpikir begini ---- */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2 px-1">
          <span className="flex size-6 shrink-0 items-center justify-center rounded-lg bg-brand-soft">
            <Icon name="prediction" size={13} className="text-brand" />
          </span>
          <p className="t-label">Mengapa AI berpikir begini</p>
          <span className="t-meta">— tiga faktor paling berpengaruh</span>
        </div>
        <DriverList drivers={result.drivers} />
      </div>

      {/* ---- Baris 3: tindakan, kotaknya sendiri ---- */}
      <div className="card p-5">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-lg bg-brand-soft">
              <Icon name="steps" size={13} className="text-brand" />
            </span>
            <p className="t-label">Tindakan yang disarankan</p>
          </div>
          <AiRecommendedBadge />
        </div>
        <ActionSteps actions={result.actions} />
      </div>

      {/* jejak teknis — memperkuat kesan sistem nyata di depan juri */}
      {(result.model_version || result.inference_ms !== undefined) && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-1">
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
