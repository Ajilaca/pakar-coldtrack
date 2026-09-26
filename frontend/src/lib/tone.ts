import { CheckCircle, Warning, WarningOctagon } from "@phosphor-icons/react/dist/ssr";
import { ShipmentStatus } from "./types";

export const STATUS_TONE: Record<
  ShipmentStatus,
  { word: string; text: string; soft: string; bar: string; border: string; lborder: string; Icon: typeof CheckCircle }
> = {
  AMAN: { word: "AMAN", text: "text-ok", soft: "bg-ok-soft", bar: "bg-ok", border: "border-ok", lborder: "border-l-ok", Icon: CheckCircle },
  WASPADA: { word: "WASPADA", text: "text-warn", soft: "bg-warn-soft", bar: "bg-warn", border: "border-warn", lborder: "border-l-warn", Icon: Warning },
  KRITIS: { word: "KRITIS", text: "text-crit", soft: "bg-crit-soft", bar: "bg-crit", border: "border-crit", lborder: "border-l-crit", Icon: WarningOctagon },
};
