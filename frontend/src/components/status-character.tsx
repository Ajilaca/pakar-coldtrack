import { Icon, IconName } from "@/components/icon";
import { ShipmentStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const CONFIG: Record<ShipmentStatus, { label: string; grad: string; icon: IconName }> = {
  AMAN: { label: "AMAN", grad: "grad-safe", icon: "safe" },
  WASPADA: { label: "WASPADA", grad: "grad-warn", icon: "warning" },
  KRITIS: { label: "KRITIS", grad: "grad-crit", icon: "critical" },
};

/**
 * Gradien blok status untuk kartu hasil. Isinya SELALU teks putih —
 * pemanggil cukup menambahkan `text-white` pada wadahnya.
 */
export const STATUS_GRADIENT: Record<ShipmentStatus, string> = {
  AMAN: CONFIG.AMAN.grad,
  WASPADA: CONFIG.WASPADA.grad,
  KRITIS: CONFIG.KRITIS.grad,
};

interface StatusCharacterProps {
  status: ShipmentStatus;
  size?: number;
  /** "row" = lingkaran di kiri kata; "stack" = lingkaran di atas kata */
  orientation?: "row" | "stack";
}

/**
 * Lampu status + kata statusnya, dirender untuk DIPASANG DI ATAS GRADIEN:
 * lingkaran ikon memakai putih transparan, teksnya mewarisi warna putih
 * dari wadah. Label bidang ("Status perjalanan") dirender oleh pemanggil.
 */
export function StatusCharacter({ status, size = 64, orientation = "row" }: StatusCharacterProps) {
  const cfg = CONFIG[status];
  return (
    <div
      className={cn(
        "flex items-center",
        orientation === "stack" ? "flex-col justify-center gap-2.5" : "gap-3"
      )}
    >
      <div
        className="flex shrink-0 items-center justify-center rounded-full bg-white/20 ring-1 ring-white/35"
        style={{ width: size, height: size }}
      >
        <Icon name={cfg.icon} size={Math.round(size * 0.5)} tone="white" />
      </div>
      <p className="t-status">{cfg.label}</p>
    </div>
  );
}
