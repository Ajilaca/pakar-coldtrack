import { ActionStep } from "@/lib/types";

export function ActionSteps({ actions }: { actions: ActionStep[] }) {
  const sorted = [...actions].sort((a, b) => a.priority - b.priority);

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground">Tindakan yang disarankan</p>
      <ol className="space-y-2">
        {sorted.map((action) => (
          <li key={action.priority} className="flex items-start gap-3 rounded-lg border border-border/50 bg-muted/30 px-3 py-2">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs font-bold">
              {action.priority}
            </span>
            <div className="flex-1">
              <p className="text-sm leading-snug">{action.text}</p>
              <p className="text-xs text-muted-foreground mt-0.5">≈ {action.eta_min} menit</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}