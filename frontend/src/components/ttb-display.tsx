import { ShipmentStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TtbDisplayProps {
  status: ShipmentStatus;
  minutes: number | null;
}

export function TtbDisplay({ status, minutes }: TtbDisplayProps) {
  if (status === "AMAN" || minutes === null) {
    return (
      <div className="space-y-1">
        <p className="text-sm text-muted-foreground">Time-to-Breach</p>
        <p className="text-2xl font-bold text-emerald-500">Tidak ada risiko breach terdeteksi</p>
      </div>
    );
  }

  const colorClass = status === "KRITIS" ? "text-red-500" : "text-amber-500";

  return (
    <div className="space-y-1">
      <p className="text-sm text-muted-foreground">Time-to-Breach</p>
      <p className={cn("font-extrabold tracking-tight leading-none text-5xl sm:text-6xl", colorClass)}>
        {minutes.toFixed(1)}
        <span className="text-2xl sm:text-3xl font-bold ml-1">menit</span>
      </p>
      <p className="text-sm text-muted-foreground">
        Muatan aman <span className="font-semibold text-foreground">{minutes.toFixed(0)} menit</span> lagi sebelum ambang suhu terlampaui.
      </p>
    </div>
  );
}