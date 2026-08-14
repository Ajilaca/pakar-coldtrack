import { Icon } from "@/components/icon";
import { cn } from "@/lib/utils";

export type KpiAccent = "blue" | "mint" | "coral" | "amber" | "critical";

interface KpiCardProps {
  accent?: KpiAccent;
  label: string;
  value: string;
  note?: string;
  noteTone?: "muted" | "mint" | "amber" | "critical";
}

const ACCENT_BG: Record<KpiAccent, string> = {
  blue: "bg-brand-soft",
  mint: "bg-mint-soft",
  coral: "bg-coral-soft",
  amber: "bg-amberwarn-soft",
  critical: "bg-critical-soft",
};
const NOTE_TONE: Record<string, string> = {
  muted: "text-muted-foreground",
  mint: "text-mint",
  amber: "text-amberwarn",
  critical: "text-critical",
};

export function KpiCard({ accent = "blue", label, value, note, noteTone = "muted" }: KpiCardProps) {
  return (
    <div className="flex items-center gap-2.5 rounded-2xl border border-border bg-card px-3 py-2.5 shadow-frost">
      <div className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg", ACCENT_BG[accent])}>
        <Icon size={15} tone="gray" />
      </div>
      <div className="min-w-0 leading-tight">
        <p className="truncate text-[11px] text-muted-foreground">{label}</p>
        <div className="flex items-baseline gap-1.5">
          <span className="font-display text-lg font-bold tracking-tight text-ink tabular">{value}</span>
          {note && <span className={cn("truncate text-[10px]", NOTE_TONE[noteTone])}>{note}</span>}
        </div>
      </div>
    </div>
  );
}
