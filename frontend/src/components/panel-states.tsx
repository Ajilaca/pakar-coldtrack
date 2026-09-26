import { Snowflake, WarningCircle } from "@phosphor-icons/react/dist/ssr";

export function ResultEmpty({ message }: { message: string }) {
  return (
    <div className="card flex min-h-[320px] flex-col items-center justify-center gap-3 p-6 text-center">
      <Snowflake size={32} className="text-accent-soft" aria-hidden />
      <p className="max-w-xs text-muted">{message}</p>
    </div>
  );
}

export function ResultError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="card flex items-start gap-3 border-l-[3px] border-l-crit p-4">
      <WarningCircle size={20} className="mt-0.5 shrink-0 text-crit" aria-hidden />
      <div className="flex flex-col gap-2">
        <p className="font-semibold text-ink">Analisis gagal</p>
        <p className="text-muted">{message}</p>
        <button
          type="button"
          onClick={onRetry}
          className="w-fit cursor-pointer rounded-md bg-brand px-3 py-1.5 text-[13px] font-medium text-brand-on transition-opacity duration-150 hover:opacity-90"
        >
          Coba lagi
        </button>
      </div>
    </div>
  );
}

export function ResultSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-busy="true" aria-label="Memuat analisis">
      <div className="h-[220px] animate-pulse rounded-lg bg-surface-muted" />
      <div className="h-[300px] animate-pulse rounded-lg bg-surface-muted" />
    </div>
  );
}
