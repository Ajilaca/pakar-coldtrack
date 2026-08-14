import { Icon } from "@/components/icon";
import { ShipmentStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const CONFIG: Record<ShipmentStatus, { label: string; bg: string; ring: string; text: string }> = {
  AMAN: { label: "AMAN", bg: "bg-mint", ring: "ring-mint/30", text: "text-mint" },
  WASPADA: { label: "WASPADA", bg: "bg-amberwarn", ring: "ring-amberwarn/30", text: "text-amberwarn" },
  KRITIS: { label: "KRITIS", bg: "bg-critical", ring: "ring-critical/30", text: "text-critical" },
};

export function StatusCharacter({ status, size = 88 }: { status: ShipmentStatus; size?: number }) {
  const cfg = CONFIG[status];
  return (
    <div className="flex items-center gap-4">
      <div
        className={cn("flex shrink-0 items-center justify-center rounded-full ring-8", cfg.bg, cfg.ring)}
        style={{ width: size, height: size }}
      >
        <Icon size={Math.round(size * 0.5)} tone="white" />
      </div>
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Status perjalanan</p>
        <p className={cn("font-display text-4xl font-extrabold tracking-tight", cfg.text)}>{cfg.label}</p>
      </div>
    </div>
  );
}
